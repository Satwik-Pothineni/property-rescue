"""Link Switch agent discussion in Mattermost to investigation records, read-only.

The human posts the investigation brief (INV_START <run id>) in the private Switch
room; agents reply in that thread through Switch. Sync finds that thread, imports
posts that mention the run, and records them on the request timeline. Message
text is untrusted agent output: stored and displayed as data, never executed.
"""

from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from property_rescue.config import mattermost_origin, mattermost_token
from property_rescue.investigation import get_investigation
from property_rescue.messaging import IntegrationError, MattermostReader
from property_rescue.models import CollaborationMessage, Investigation, TimelineEvent
from property_rescue.service import DomainError, lock_request, record_event

LEADING_TAG = re.compile(r"^(?:@[\w.-]+\s+)*(INV_[A-Z_]+)\b")
POST_ID = r"^[a-z0-9]{26}$"


class ChannelReader(Protocol):
    def channel_posts(self, channel_id: str) -> dict[str, Any]: ...
    def thread(self, root_id: str) -> dict[str, Any]: ...
    def user_by_id(self, user_id: str) -> dict[str, Any]: ...


class Collaboration:
    """Configured reader plus the default investigation channel, if any."""
    def __init__(self, reader: ChannelReader | None, channel_id: str | None = None) -> None:
        self.reader, self.channel_id = reader, channel_id

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Collaboration":
        if not env.get("MATTERMOST_URL") and not env.get("MATTERMOST_TOKEN"):
            return cls(None)
        channel = env.get("MATTERMOST_INVESTIGATION_CHANNEL") or None
        if channel is not None and not re.fullmatch(POST_ID, channel):
            raise ValueError("MATTERMOST_INVESTIGATION_CHANNEL must be a Mattermost channel ID")
        return cls(MattermostReader(mattermost_origin(env), mattermost_token(env)), channel)


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel_id: str | None = Field(default=None, pattern=POST_ID)


def message_view(m: CollaborationMessage) -> dict:
    return {"post_id": m.post_id, "channel_id": m.channel_id, "root_post_id": m.root_post_id,
            "sender": m.sender, "sender_is_bot": m.sender_is_bot, "tag": m.tag, "message": m.message,
            "edited": m.edited, "posted_at": m.posted_at.isoformat()}


def messages(db: Session, run_id: UUID) -> list[CollaborationMessage]:
    return list(db.scalars(select(CollaborationMessage).where(CollaborationMessage.investigation_id == run_id)
                           .order_by(CollaborationMessage.posted_at, CollaborationMessage.post_id)))


def agent_review(db: Session, run_id: UUID) -> str:
    """Whether an agent report arrived. Imported text is not machine-certified."""
    tags = set(db.scalars(select(CollaborationMessage.tag).where(
        CollaborationMessage.investigation_id == run_id, CollaborationMessage.sender_is_bot.is_(True))))
    if "INV_REPORT" in tags:
        return "report_received"
    if "INV_BLOCKED" in tags:
        return "blocked"
    return "in_discussion" if tags else "not_verified"


def sync(db: Session, user, run_id: UUID, body: SyncRequest, collaboration: Collaboration) -> list[CollaborationMessage]:
    run: Investigation = get_investigation(db, user, run_id)
    if collaboration.reader is None:
        raise DomainError(503, "Mattermost collaboration is not configured")
    # A chat-started run is bound to the room its human command was posted in.
    started = db.scalar(select(TimelineEvent).where(
        TimelineEvent.request_id == run.request_id, TimelineEvent.kind == "investigation.chat_started",
        TimelineEvent.details["investigation_id"].astext == str(run.id)))
    channel_id = body.channel_id or (started.details.get("channel_id") if started else None) or collaboration.channel_id
    if channel_id is None:
        raise DomainError(422, "Provide the investigation channel_id")
    reader, users = collaboration.reader, {}

    def sender(user_id: str) -> dict:
        if user_id not in users:
            users[user_id] = reader.user_by_id(user_id)
        return users[user_id]

    binding = db.scalar(select(TimelineEvent).where(
        TimelineEvent.request_id == run.request_id, TimelineEvent.kind == "investigation.chat_started",
        TimelineEvent.details["investigation_id"].astext == str(run.id),
        TimelineEvent.details["channel_id"].astext == channel_id))
    bound_root = binding.details["root_post_id"] if binding else None
    marker = f"INV_START {run.id}"
    try:
        channel = reader.channel_posts(channel_id)
        if not isinstance(channel.get("posts"), dict):
            raise DomainError(502, "Mattermost returned an unexpected response shape")
        roots = sorted((p for p in channel["posts"].values()
                        if not p.get("root_id") and not p.get("delete_at") and (p["id"] == bound_root if bound_root else marker in p.get("message", ""))
                        and p.get("channel_id") == channel_id),
                       key=lambda p: p.get("create_at", 0))
        root = next((p for p in roots if not sender(p["user_id"]).get("is_bot")), None)
        if root is None:
            # A successful complete channel scan can invalidate a removed kickoff.
            lock_request(db, run.request_id)
            old = [m for m in messages(db, run.id) if m.channel_id == channel_id]
            if not old:
                raise DomainError(404, "No human INV_START post for this investigation in that channel")
            for m in old:
                db.delete(m)
                record_event(db, run.request_id, "collaboration.removed", None,
                             investigation_id=str(run.id), post_id=m.post_id)
            db.commit()
            return messages(db, run.id)
        response = reader.thread(root["id"])
        thread = response.get("posts")
        if (not isinstance(thread, dict) or root["id"] not in thread
                or response.get("has_next") or response.get("has_prev")):
            raise DomainError(502, "Mattermost returned an incomplete thread")
        for post in thread.values():
            sender(post["user_id"])
    except IntegrationError as error:
        raise DomainError(502, str(error)) from None
    except (KeyError, TypeError, AttributeError):
        raise DomainError(502, "Mattermost returned an unexpected response shape") from None

    lock_request(db, run.request_id)
    known = {m.post_id: m for m in messages(db, run.id) if m.channel_id == channel_id}
    seen: set[str] = set()
    for post in sorted(thread.values(), key=lambda p: p.get("create_at", 0)):
        text = post.get("message", "")
        if (post.get("delete_at") or post.get("channel_id") != channel_id or (str(run.id) not in text and post.get("id") != bound_root)
                or not re.fullmatch(POST_ID, post.get("id", ""))
                or (post["id"] != root["id"] and post.get("root_id") != root["id"])):
            continue  # Agent status posts never mention the run; deleted posts are not evidence.
        match = LEADING_TAG.match(text)
        author = users[post["user_id"]]
        seen.add(post["id"])
        existing = known.get(post["id"])
        tag = match.group(1) if match else None
        if existing is not None:
            updated = (text[:20000], bool(post.get("edit_at")), tag)
            if (existing.message, existing.edited, existing.tag) != updated:
                existing.message, existing.edited, existing.tag = updated
                record_event(db, run.request_id, "collaboration.updated", None,
                             investigation_id=str(run.id), post_id=post["id"], tag=tag)
            continue
        db.add(CollaborationMessage(
            post_id=post["id"], investigation_id=run.id, request_id=run.request_id, channel_id=channel_id,
            root_post_id=root["id"], sender=str(author.get("username", "unknown"))[:64],
            sender_is_bot=bool(author.get("is_bot")), tag=match.group(1) if match else None,
            message=text[:20000], edited=bool(post.get("edit_at")),
            posted_at=datetime.fromtimestamp(post.get("create_at", 0) / 1000, timezone.utc)))
        db.flush()
        record_event(db, run.request_id, "collaboration.message", None, investigation_id=str(run.id),
                     post_id=post["id"], sender=author.get("username"), sender_is_bot=bool(author.get("is_bot")),
                     tag=match.group(1) if match else None)
    for post_id, existing in known.items():
        if post_id not in seen:
            db.delete(existing)
            record_event(db, run.request_id, "collaboration.removed", None,
                         investigation_id=str(run.id), post_id=post_id)
    db.commit()
    return messages(db, run.id)
