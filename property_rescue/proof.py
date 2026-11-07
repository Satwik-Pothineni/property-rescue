"""Validate a live thread without posting messages or running an agent runtime."""

from collections.abc import Mapping
import json
import os
import re
import sys
from typing import Any, Protocol

from property_rescue.config import ConfigurationError, Settings
from property_rescue.messaging import IntegrationError, MattermostReader


class Reader(Protocol):
    def user(self, username: str) -> dict[str, Any]: ...
    def thread(self, root_id: str) -> dict[str, Any]: ...


class ProofError(ValueError):
    """The retrieved conversation does not demonstrate the expected exchange."""


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]{26}", value):
        raise ProofError("Missing or malformed Mattermost identifier")
    return value


def verify(settings: Settings, reader: Reader) -> dict[str, Any]:
    identities: dict[str, str] = {}
    for role, username in (("human", settings.human), ("coordinator", settings.coordinator), ("worker", settings.worker)):
        user = reader.user(username)
        if user.get("username") != username or user.get("delete_at", 0) != 0:
            raise ProofError("Unexpected or inactive proof participant")
        is_bot = user.get("is_bot", False)
        if not isinstance(is_bot, bool) or is_bot != (role != "human"):
            raise ProofError("Expected one human and two bot accounts")
        identities[role] = identifier(user.get("id"))
    if len(set(identities.values())) != 3:
        raise ProofError("Proof participants must have distinct identities")

    thread = reader.thread(settings.root_id)
    posts = thread.get("posts")
    if not isinstance(posts, Mapping) or settings.root_id not in posts:
        raise ProofError("Thread is missing its root post")
    root = posts[settings.root_id]
    if not isinstance(root, dict):
        raise ProofError("Malformed root post")
    channel_id = identifier(root.get("channel_id"))
    stages = (("PR_CONNECT", "human"), ("PR_ACK", "coordinator"), ("PR_TASK", "coordinator"), ("PR_RESULT", "worker"), ("PR_DONE", "coordinator"))
    found: dict[str, dict[str, Any]] = {}
    pattern = re.compile(r"(?<!\S)(PR_CONNECT|PR_ACK|PR_TASK|PR_RESULT|PR_DONE) " + re.escape(settings.run_id) + r"(?!\S)")
    for key, post in posts.items():
        if not isinstance(post, dict) or not isinstance(post.get("message"), str):
            raise ProofError("Malformed thread post")
        matches = pattern.findall(post["message"])
        if not matches:
            continue
        if len(matches) != 1 or matches[0] in found:
            raise ProofError("Duplicate or ambiguous proof stage; start a fresh run")
        stage = matches[0]
        expected_role = dict(stages)[stage]
        recipient = {"PR_CONNECT": settings.coordinator, "PR_TASK": settings.worker, "PR_RESULT": settings.coordinator}.get(stage)
        if recipient and not re.search(r"(?<!\S)@" + re.escape(recipient) + r"(?![a-z0-9._-])", post["message"]):
            raise ProofError("Proof handoff is missing its intended recipient")
        post_id = identifier(post.get("id"))
        if (
            key != post_id
            or post.get("user_id") != identities[expected_role]
            or post.get("channel_id") != channel_id
            or post.get("delete_at", 0) != 0
            or post.get("edit_at", 0) != 0
            or post.get("type", "") != ""
            or (stage == "PR_CONNECT" and (post_id != settings.root_id or post.get("root_id", "") != ""))
            or (stage != "PR_CONNECT" and post.get("root_id") != settings.root_id)
        ):
            raise ProofError("Proof stage has an unexpected sender, thread, or edited/deleted post")
        timestamp = post.get("create_at")
        if type(timestamp) is not int or timestamp <= 0:
            raise ProofError("Proof post has no valid timestamp")
        found[stage] = {"stage": stage, "post_id": post_id, "sender_id": identities[expected_role], "created_at_ms": timestamp}
    if set(found) != {stage for stage, _ in stages}:
        raise ProofError("Exchange incomplete: all five proof stages are required")
    evidence = [found[stage] for stage, _ in stages]
    if any(left["created_at_ms"] >= right["created_at_ms"] for left, right in zip(evidence, evidence[1:])):
        raise ProofError("Proof stages are not in a verifiable chronological order")
    # This is transcript evidence only. Switch runtime provenance still needs
    # matching room/session evidence; a bot can post without going through Switch.
    return {"status": "mattermost_transcript_verified", "switch_runtime_verified": False,
            "run_id": settings.run_id, "channel_id": channel_id,
            "root_id": settings.root_id, "messages": evidence}


def main() -> int:
    try:
        settings = Settings.from_env(os.environ)
        result = verify(settings, MattermostReader(settings.mattermost_url, settings.token))
    except (ConfigurationError, IntegrationError, ProofError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
