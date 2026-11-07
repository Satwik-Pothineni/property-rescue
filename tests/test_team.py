"""Real PostgreSQL team-mode tests. FakeMattermost is an explicit test double for the reader."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from test_actions import ActionCase
from property_rescue.api import create_app
from property_rescue.collaboration import Collaboration
from property_rescue.messaging import IntegrationError
from property_rescue.models import MaintenanceRequest, Team
from property_rescue.seed import demo_id

CHANNEL = "c" * 26
HUMAN, TRIAGE, VENDORS = "h" * 26, "t" * 26, "v" * 26


class FakeMattermost:
    """Shapes follow Mattermost API v4 channel posts, thread and user responses."""
    def __init__(self, run_id, *, fail=False, bot_kickoff=False):
        self.fail = fail
        def post(pid, user, message, at, root="", **extra):
            return {"id": pid * 26 if len(pid) == 1 else pid, "user_id": user, "channel_id": CHANNEL,
                    "root_id": root, "message": message, "create_at": at, "delete_at": 0, "edit_at": 0} | extra
        root = post("r", TRIAGE if bot_kickoff else HUMAN, f"@pr-triage INV_START {run_id}\nEvidence packet...", 1000)
        rid = root["id"]
        self.channel = {"order": [rid], "posts": {rid: root}}
        replies = [
            post("a", TRIAGE, f"INV_ACK {run_id} Packet matches.", 2000, rid),
            post("s", TRIAGE, "**Worked for 22s. 5 tool calls.**", 2100, rid, edit_at=2200),
            post("w", VENDORS, f"@pr-triage INV_VENDOR_RESULT {run_id} Candidate only.", 3000, rid),
            post("i", TRIAGE, f"Vendor review received for {run_id}. Waiting before INV_REPORT.", 3500, rid),
            post("d", VENDORS, f"INV_VENDOR_RESULT {run_id} retracted", 3600, rid, delete_at=3700),
            post("f", TRIAGE, f"INV_REPORT {run_id}\nNo external actions taken. Human review required.", 4000, rid),
        ]
        self.thread_posts = {p["id"]: p for p in [root, *replies]}
        self.users = {HUMAN: {"id": HUMAN, "username": "user", "is_bot": False},
                      TRIAGE: {"id": TRIAGE, "username": "pr-triage", "is_bot": True},
                      VENDORS: {"id": VENDORS, "username": "pr-vendors", "is_bot": True}}

    def channel_posts(self, channel_id):
        if self.fail:
            raise IntegrationError("Mattermost request rejected (HTTP 401)")
        return self.channel if channel_id == CHANNEL else {"order": [], "posts": {}}

    def thread(self, root_id):
        return {"order": list(self.thread_posts), "posts": self.thread_posts}

    def user_by_id(self, user_id):
        return self.users[user_id]


class TeamTests(ActionCase):
    def new_request(self, alias="tenant", title="Fictional: no hot water in unit 2"):
        r = self.client.post("/requests", headers=self.headers(alias, uuid4()), json={
            "property_id": str(demo_id("apartments")), "title": title,
            "description": "Fictional team-mode complaint.", "category": "plumbing"})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def create_incident(self, request_ids, alias="coordinator", key=None, **changes):
        body = {"property_id": str(demo_id("apartments")), "title": "Fictional boiler outage",
                "coordinator_id": str(demo_id("coordinator_two")), "request_ids": request_ids} | changes
        return self.client.post("/incidents", json=body, headers=self.headers(alias, key or uuid4()))

    def test_queue_is_role_scoped_and_shows_incident_context(self):
        rows = self.client.get("/queue", headers=self.headers("coordinator")).json()
        self.assertEqual({r["property"]["id"] for r in rows}, {str(demo_id("apartments"))})
        linked = next(r for r in rows if r["request"]["id"] == str(demo_id("water_request_one")))
        self.assertEqual(linked["incident"]["coordinator"]["name"], "Robin Demo")
        self.assertEqual(linked["tenant_name"], "Alex Demo")
        owner = self.client.get("/queue", headers=self.headers("owner")).json()
        self.assertEqual(len({r["property"]["id"] for r in owner}), 2)
        self.assertEqual(self.client.get("/queue", headers=self.headers("outsider")).json(), [])
        self.assertEqual(self.client.get("/queue", headers=self.headers("tenant")).status_code, 403)
        self.assertEqual(self.client.get("/queue?status=bogus", headers=self.headers("owner")).status_code, 422)

    def test_incident_groups_requests_without_changing_originals(self):
        first, second = self.new_request("tenant"), self.new_request("tenant_two", "Fictional: radiator cold")
        key = uuid4()
        r = self.create_incident([first["id"], second["id"]], key=key)
        self.assertEqual(r.status_code, 201, r.text)
        incident = r.json()
        self.assertEqual(incident["coordinator"]["name"], "Riley Demo")
        grouped = {q["id"]: q for q in incident["requests"]}
        for original in (first, second):
            kept = grouped[original["id"]]
            self.assertEqual((kept["title"], kept["description"], kept["tenant_id"]),
                             (original["title"], original["description"], original["tenant_id"]))
        self.assertEqual(self.create_incident([first["id"]], key=key).json()["id"], incident["id"])
        self.assertEqual(self.create_incident([first["id"]], key=key, title="Other").status_code, 409)
        kinds = [e["kind"] for e in self.timeline(first["id"])]
        self.assertEqual(kinds, ["request.submitted", "incident.linked"])
        # Tenants still see only their own original request.
        mine = self.client.get(f"/requests/{second['id']}", headers=self.headers("tenant_two")).json()
        self.assertEqual(mine["title"], "Fictional: radiator cold")

    def test_incident_management_rules(self):
        fresh = self.new_request()
        for alias, status in (("member", 403), ("other_owner", 404), ("outsider", 404), ("tenant", 403)):
            self.assertEqual(self.create_incident([fresh["id"]], alias=alias).status_code, status, alias)
        self.assertEqual(self.create_incident([fresh["id"]], coordinator_id=str(demo_id("member"))).status_code, 422)
        self.assertEqual(self.create_incident([str(demo_id("water_request_one"))]).status_code, 409)
        self.assertEqual(self.create_incident([str(demo_id("other_request"))]).status_code, 404)
        self.assertEqual(self.create_incident([str(demo_id("tap_request"))], alias="owner",
                                              property_id=str(demo_id("cottage"))).status_code, 422)
        incident = self.create_incident([fresh["id"]], alias="owner").json()
        url = f"/incidents/{incident['id']}/requests/{fresh['id']}"
        self.assertEqual(self.client.put(url, headers=self.headers("coordinator")).status_code, 200)  # Idempotent.
        self.assertEqual(self.client.delete(url, headers=self.headers("member")).status_code, 403)
        self.assertEqual(self.client.delete(url, headers=self.headers("coordinator")).json()["requests"], [])
        self.assertEqual(self.client.delete(url, headers=self.headers("coordinator")).status_code, 404)
        self.assertEqual(self.client.put(url, headers=self.headers("coordinator")).status_code, 200)
        kinds = [e["kind"] for e in self.timeline(fresh["id"])]
        self.assertEqual(kinds[1:], ["incident.linked", "incident.unlinked", "incident.linked"])
        with Session(self.engine) as db:
            self.assertEqual(db.get(MaintenanceRequest, demo_id("water_request_one")).incident_id, demo_id("incident"))

    def test_only_the_incident_coordinator_decides_and_reassignment_revokes_approvals(self):
        request = "water_request_one"  # Seeded incident coordinated by Robin (coordinator).
        approved = self.approved(request=request, approver="coordinator")
        pending = self.propose(request=request, alias="member").json()
        self.assertEqual(self.decide(pending, alias="coordinator_two").status_code, 403)
        url = f"/incidents/{demo_id('incident')}/coordinator"
        self.assertEqual(self.client.put(url, json={"coordinator_id": str(demo_id("member"))},
                                         headers=self.headers("coordinator")).status_code, 422)
        moved = self.client.put(url, json={"coordinator_id": str(demo_id("coordinator_two"))}, headers=self.headers("coordinator"))
        self.assertEqual(moved.json()["coordinator"]["name"], "Riley Demo")
        self.assertEqual(self.execute(approved, alias="owner").status_code, 409)
        self.assertEqual(self.decide(pending, alias="coordinator").status_code, 403)
        self.assertEqual(self.execute(self.decide(pending, alias="coordinator_two").json(), alias="coordinator_two").json()["status"], "executed")
        events = self.timeline(demo_id(request))
        self.assertIn("incident.coordinator_assigned", [e["kind"] for e in events])
        self.assertIn("approver_lost_authority", self.denials(demo_id(request)))
        self.assertEqual(len(self.executor.calls), 1)

    def test_unset_team_spend_limit_keeps_spending_owner_only(self):
        with Session(self.engine) as db, db.begin():
            db.get(Team, demo_id("team")).coordinator_spend_limit = None
        spend = self.propose({"kind": "authorize_spend", "vendor_id": str(demo_id("apartments/vendor")),
                              "amount": "1.00", "currency": "USD"}, request="water_request_one").json()
        self.assertEqual(self.decide(spend, alias="coordinator").status_code, 403)
        self.assertEqual(self.decide(spend, alias="owner").status_code, 200)

    def sync(self, run, reader, alias="owner", **body):
        with TestClient(create_app(self.engine, executor=self.executor, mattermost=Collaboration(reader, CHANNEL))) as client:
            return client.post(f"/investigations/{run['id']}/collaboration/sync", json=body, headers=self.headers(alias))

    def test_mattermost_sync_links_agent_discussion_to_records(self):
        run = self.investigate("water_request_one")
        reader = FakeMattermost(run["id"])
        r = self.sync(run, reader)
        self.assertEqual(r.status_code, 200, r.text)
        imported = r.json()
        self.assertEqual([(m["sender"], m["tag"]) for m in imported], [
            ("user", "INV_START"), ("pr-triage", "INV_ACK"), ("pr-vendors", "INV_VENDOR_RESULT"),
            ("pr-triage", None), ("pr-triage", "INV_REPORT")])
        self.assertEqual([m["sender_is_bot"] for m in imported], [False, True, True, True, True])
        self.assertEqual(self.sync(run, reader).json(), imported)  # No duplicates on resync.
        view = self.client.get(f"/investigations/{run['id']}", headers=self.headers("coordinator")).json()
        self.assertEqual(view["agent_review"], "report_received")
        collab = [e for e in self.timeline(demo_id("water_request_one")) if e["kind"] == "collaboration.message"]
        self.assertEqual(len(collab), 5)
        self.assertEqual(self.client.get(f"/investigations/{run['id']}/collaboration",
                                         headers=self.headers("tenant")).status_code, 403)

    def test_mattermost_sync_failures_are_explicit(self):
        run = self.investigate("water_request_one")
        self.assertEqual(self.sync(run, None).status_code, 503)
        failed = self.sync(run, FakeMattermost(run["id"], fail=True))
        self.assertEqual(failed.status_code, 502)
        self.assertNotIn("token", failed.text.lower())
        self.assertEqual(self.sync(run, FakeMattermost(run["id"], bot_kickoff=True)).status_code, 404)
        self.assertEqual(self.sync(run, FakeMattermost(run["id"]), channel_id="x" * 26).status_code, 404)
        self.assertEqual(self.sync(run, FakeMattermost(run["id"]), channel_id="not-an-id").status_code, 422)
        self.assertEqual(self.sync(run, FakeMattermost(run["id"]), alias="other_owner").status_code, 404)
        self.assertEqual(self.client.get(f"/investigations/{run['id']}", headers=self.headers("owner")).json()["agent_review"],
                         "not_verified")

    def test_sync_refreshes_edits_and_removes_retracted_report(self):
        run = self.investigate("water_request_one")
        reader = FakeMattermost(run["id"])
        self.assertEqual(self.sync(run, reader).status_code, 200)
        report = reader.thread_posts["f" * 26]
        report.update(message=f"INV_REPORT {run['id']} Corrected estimate; review needed.", edit_at=5000)
        refreshed = self.sync(run, reader).json()
        changed = next(m for m in refreshed if m["post_id"] == report["id"])
        self.assertTrue(changed["edited"])
        self.assertIn("Corrected estimate", changed["message"])
        del reader.thread_posts[report["id"]]  # Deleted posts are absent from normal API reads.
        self.assertNotIn(report["id"], [m["post_id"] for m in self.sync(run, reader).json()])
        view = self.client.get(f"/investigations/{run['id']}", headers=self.headers("owner")).json()
        self.assertEqual(view["agent_review"], "in_discussion")
        events = self.timeline(demo_id("water_request_one"))
        self.sync(run, reader)
        self.assertEqual(self.timeline(demo_id("water_request_one")), events)
        self.assertIn("collaboration.updated", [e["kind"] for e in events])
        self.assertIn("collaboration.removed", [e["kind"] for e in events])

    def test_failed_sync_preserves_imports_and_removed_kickoff_invalidates_them(self):
        run = self.investigate("water_request_one")
        reader = FakeMattermost(run["id"])
        original = self.sync(run, reader).json()
        reader.fail = True
        self.assertEqual(self.sync(run, reader).status_code, 502)
        current = self.client.get(f"/investigations/{run['id']}/collaboration", headers=self.headers("owner")).json()
        self.assertEqual(current, original)
        reader.fail = False
        reader.channel = {"posts": {}, "order": []}
        self.assertEqual(self.sync(run, reader).json(), [])
        view = self.client.get(f"/investigations/{run['id']}", headers=self.headers("owner")).json()
        self.assertEqual(view["agent_review"], "not_verified")
