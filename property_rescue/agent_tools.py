"""Scoped local MCP evidence tools; never exposes approval or execution operations.

Human authority comes from a verified Mattermost post and an operator-configured
identity mapping, not from tool arguments or an agent's assertions.
"""

import os
from pathlib import Path
import re
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from property_rescue import collaboration, investigation
from property_rescue.database import build_engine
from property_rescue.messaging import IntegrationError
from property_rescue.models import Investigation, TimelineEvent, User
from property_rescue.service import DomainError, lock_request, record_event


class AgentEvidenceTools:
    def __init__(self, engine: Engine, connection: collaboration.Collaboration,
                 human_id: str, actor_id: UUID) -> None:
        self.engine, self.connection = engine, connection
        self.human_id, self.actor_id = human_id, actor_id

    def kickoff(self, request_id: UUID) -> dict:
        reader, channel = self.connection.reader, self.connection.channel_id
        if reader is None or channel is None:
            raise DomainError(503, "Agent evidence tools require a configured Mattermost room")
        human = reader.user_by_id(self.human_id)
        if human.get("is_bot") or human.get("delete_at"):
            raise DomainError(403, "Configured sender must be an active human")
        # Authority is the verified human sender and room; the agent's mention name is not.
        command = re.compile(r"^@[\w.-]+\s+investigate\s+" + re.escape(str(request_id)) + r"(?:\s|$)", re.I)
        posts = reader.channel_posts(channel)["posts"].values()
        roots = [p for p in posts if p.get("user_id") == self.human_id
                 and p.get("channel_id") == channel and not p.get("root_id")
                 and not p.get("delete_at") and command.match(p.get("message", ""))]
        if not roots:
            raise DomainError(403, "No authorized human investigation command found in the configured room")
        return max(roots, key=lambda p: (p["create_at"], p["id"]))

    def actor(self, db: Session) -> User:
        actor = db.get(User, self.actor_id)
        if actor is None or not actor.active or actor.role not in ("owner", "staff"):
            raise DomainError(403, "Mapped app user is not an active manager")
        return actor

    def start(self, request_id: UUID) -> dict:
        root = self.kickoff(request_id)
        key = uuid5(NAMESPACE_URL, "property-rescue/mattermost/" + root["id"])
        with Session(self.engine, expire_on_commit=False) as db:
            actor = self.actor(db)
            investigation.authorize(db, actor, request_id)
            # Serialize duplicate tool calls, including the durable thread binding.
            lock_request(db, request_id)
            run = investigation.start(db, actor, request_id, key, investigation.default_tools())
            lock_request(db, request_id)
            binding = db.scalar(select(TimelineEvent).where(
                TimelineEvent.request_id == request_id, TimelineEvent.kind == "investigation.chat_started",
                TimelineEvent.details["investigation_id"].astext == str(run.id)))
            if binding is None:
                record_event(db, request_id, "investigation.chat_started", actor,
                             investigation_id=str(run.id), root_post_id=root["id"],
                             channel_id=self.connection.channel_id, human_id=self.human_id)
                db.commit()
            return {"investigation": investigation.view(run), "mattermost_root_post_id": root["id"],
                    "instructions": "Share this evidence packet in the initiating Switch thread, delegate to both specialists, then publish INV_REPORT and call sync_investigation. No external actions."}

    def sync(self, request_id: UUID) -> dict:
        root = self.kickoff(request_id)
        key = uuid5(NAMESPACE_URL, "property-rescue/mattermost/" + root["id"])
        with Session(self.engine, expire_on_commit=False) as db:
            actor = self.actor(db)
            investigation.authorize(db, actor, request_id)
            run = db.scalar(select(Investigation).where(Investigation.request_id == request_id,
                                                        Investigation.idempotency_key == key))
            if run is None:
                raise DomainError(404, "Call investigate_request first")
            posts = collaboration.sync(db, actor, run.id, collaboration.SyncRequest(), self.connection)
            return {"investigation_id": str(run.id), "imported_messages": len(posts),
                    "agent_review": collaboration.agent_review(db, run.id)}


def create_server(tools: AgentEvidenceTools):
    from mcp.server import MCPServer
    server = MCPServer("Property Rescue evidence")

    def invoke(operation, request_id: UUID) -> dict:
        try:
            return operation(request_id)
        except DomainError as error:
            return {"error": error.detail, "status": error.status}
        except IntegrationError:
            return {"error": "Mattermost unavailable or access rejected; retry after checking configuration", "status": 502}
        except Exception:
            return {"error": "Evidence service unavailable; no successful result confirmed", "status": 503}

    @server.tool()
    def investigate_request(request_id: UUID) -> dict:
        """Fetch a scoped evidence packet after a mapped human posts @pr-triage investigate REQUEST_UUID. Repeated calls for the same human message reuse one investigation. Does not approve or execute anything."""
        return invoke(tools.start, request_id)

    @server.tool()
    def sync_investigation(request_id: UUID) -> dict:
        """Import the real Switch conversation into the request timeline. Call after posting the evidence, specialist results, and final INV_REPORT. No agent-generated text is executed."""
        return invoke(tools.sync, request_id)

    return server


def main(argv: list[str] | None = None) -> None:
    """Stdio MCP server. The sender/actor mapping is operator configuration, never a tool input."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mattermost-user-id", default=os.environ.get("AGENT_MATTERMOST_USER_ID"),
                        help="Mattermost ID of the human allowed to start investigations")
    parser.add_argument("--app-user-id", type=UUID, default=os.environ.get("AGENT_APP_USER_ID"),
                        help="Property Rescue user whose access that human's commands use")
    parser.add_argument("--channel-id", help="Mattermost room to accept commands from (default: configured room)")
    args = parser.parse_args(argv)
    if not args.mattermost_user_id or not re.fullmatch(r"[a-z0-9]{26}", args.mattermost_user_id) or not args.app_user_id:
        parser.error("--mattermost-user-id (26-char Mattermost ID) and --app-user-id are required")
    # Read credentials only inside the trusted local tool process, never tool inputs/results.
    root = Path(__file__).resolve().parents[1]
    env = dict(line.split("=", 1) for line in (root / ".local/app/.env").read_text().splitlines()
               if "=" in line and not line.startswith("#"))
    if args.channel_id:
        if not re.fullmatch(r"[a-z0-9]{26}", args.channel_id):
            parser.error("--channel-id must be a Mattermost channel ID")
        env["MATTERMOST_INVESTIGATION_CHANNEL"] = args.channel_id
    os.environ.update(env)
    engine = build_engine()
    try:
        tools = AgentEvidenceTools(engine, collaboration.Collaboration.from_env(env),
                                   args.mattermost_user_id, UUID(str(args.app_user_id)))
        create_server(tools).run()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
