"""Real PostgreSQL services with explicit Mattermost fixtures; no fake live evidence."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_actions import ActionCase
from test_team import FakeMattermost, CHANNEL, HUMAN
from property_rescue.agent_tools import AgentEvidenceTools, create_server
from property_rescue.collaboration import Collaboration
from property_rescue.models import Investigation, MaintenanceAction, TimelineEvent, User
from property_rescue.seed import demo_id
from property_rescue.service import DomainError


class AgentToolTests(ActionCase):
    def setup_tools(self, actor="owner"):
        reader = FakeMattermost("unused")
        request_id = demo_id("tap_request")
        root = reader.channel["posts"]["r" * 26]
        root["message"] = f"@pr-triage investigate {request_id} It might be related to the earlier leak."
        tools = AgentEvidenceTools(self.engine, Collaboration(reader, CHANNEL), HUMAN, demo_id(actor))
        return tools, reader, request_id

    def test_human_command_fetches_evidence_and_replays_one_run(self):
        tools, reader, rid = self.setup_tools()
        result = tools.start(rid)
        run = result["investigation"]
        self.assertEqual(run["status"], "ready_for_review")
        self.assertEqual(tools.start(rid)["investigation"]["id"], run["id"])
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(Investigation)))), 1)
            self.assertEqual(len(list(db.scalars(select(MaintenanceAction)))), 0)
        reader.thread_posts = {"r" * 26: reader.channel["posts"]["r" * 26],
            "f" * 26: {"id": "f" * 26, "root_id": "r" * 26, "channel_id": CHANNEL,
                       "user_id": "t" * 26, "create_at": 2000, "message": f"INV_REPORT {run['id']} Fixture only."}}
        synced = tools.sync(rid)
        self.assertEqual(synced["agent_review"], "report_received")
        self.assertEqual(synced["imported_messages"], 2)
        self.assertEqual(tools.sync(rid), synced)
        with Session(self.engine) as db:
            bindings = list(db.scalars(select(TimelineEvent).where(TimelineEvent.kind == "investigation.chat_started")))
            self.assertEqual(len(bindings), 1)

    def test_bot_unmapped_deleted_wrong_room_and_wrong_request_commands_denied(self):
        for change in ({"user_id": "t" * 26}, {"delete_at": 1}, {"channel_id": "x" * 26},
                       {"root_id": "x" * 26}, {"message": "investigate a different request"}):
            with self.subTest(change=change):
                tools, reader, rid = self.setup_tools()
                reader.channel["posts"]["r" * 26].update(change)
                with self.assertRaises(DomainError) as caught:
                    tools.start(rid)
                self.assertEqual(caught.exception.status, 403)

    def test_property_scope_and_revocation_enforced(self):
        tools, reader, rid = self.setup_tools("other_owner")
        with self.assertRaises(DomainError) as caught:
            tools.start(rid)
        self.assertEqual(caught.exception.status, 404)
        tools, reader, rid = self.setup_tools()
        tools.start(rid)
        with Session(self.engine) as db:
            db.get(User, demo_id("owner")).active = False
            db.commit()
        with self.assertRaises(DomainError) as caught:
            tools.sync(rid)
        self.assertEqual(caught.exception.status, 403)

    def test_missing_start_never_creates_report(self):
        tools, reader, rid = self.setup_tools()
        with self.assertRaises(DomainError) as caught:
            tools.sync(rid)
        self.assertEqual(caught.exception.status, 404)

    def test_mcp_surface_is_evidence_only(self):
        import asyncio
        from mcp import Client
        tools, _, _ = self.setup_tools()

        async def names():
            async with Client(create_server(tools)) as client:
                return sorted(t.name for t in (await client.list_tools()).tools)
        self.assertEqual(asyncio.run(names()), ["investigate_request", "sync_investigation"])
