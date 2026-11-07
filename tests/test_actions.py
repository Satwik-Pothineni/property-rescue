"""Real PostgreSQL approval-enforcement tests. RecordingExecutor is an explicit test double."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, InternalError
from sqlalchemy.orm import Session

from test_maintenance import PostgresTestCase
from property_rescue import actions
from property_rescue.api import create_app
from property_rescue.models import (ActionDecision, MaintenanceAction, MaintenanceRequest, TimelineEvent, User)
from property_rescue.seed import demo_id
from property_rescue.service import DomainError


class RecordingExecutor:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def execute(self, action, vendor, key):
        self.calls.append(key)
        if self.fail:
            raise RuntimeError("SECRET-TOKEN rejected by provider")
        return {"mode": "test_double", "vendor": vendor.name if vendor else None}


class ActionCase(PostgresTestCase):
    """Shared setup and HTTP helpers; holds no tests."""
    def setUp(self):
        super().setUp()
        self.executor = RecordingExecutor()
        self.client = TestClient(create_app(self.engine, executor=self.executor))
        self.addCleanup(self.client.close)

    def investigate(self, request="tap_request", alias="owner"):
        r = self.client.post(f"/requests/{demo_id(request)}/investigations", headers=self.headers(alias, uuid4()))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def propose(self, details=None, request="tap_request", alias="owner", run=None, key=None, **changes):
        prop = "apartments" if request.startswith("water") else "cottage"
        run = run or self.investigate(request, "owner")
        body = {"investigation_id": run["id"], "rationale": "Fictional: tap dripping per complaint.",
                "evidence_ids": [f"vendor:{demo_id(prop + '/vendor')}"],
                "details": details or {"kind": "contact_vendor", "vendor_id": str(demo_id(prop + "/vendor")),
                                       "message": "Fictional: please quote a dripping tap repair."}} | changes
        return self.client.post(f"/requests/{demo_id(request)}/actions", json=body, headers=self.headers(alias, key or uuid4()))

    def decide(self, action, decision="approved", alias="owner", **changes):
        body = {"decision": decision, "revision": action["revision"], "details_hash": action["details_hash"]} | changes
        return self.client.post(f"/actions/{action['id']}/decision", json=body, headers=self.headers(alias))

    def execute(self, action, alias="owner", key=None):
        return self.client.post(f"/actions/{action['id']}/execution", headers=self.headers(alias, key or uuid4()))

    def approved(self, details=None, request="tap_request", approver="owner"):
        action = self.propose(details, request).json()
        r = self.decide(action, alias=approver)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def timeline(self, request_id, alias="owner"):
        return self.client.get(f"/requests/{request_id}/timeline", headers=self.headers(alias)).json()

    def denials(self, request_id):
        return [e["details"]["reason"] for e in self.timeline(request_id) if e["kind"] == "action.denied"]


class ActionTests(ActionCase):
    def test_individual_owner_scenario_completes_once_with_ordered_timeline(self):
        created = self.client.post("/requests", json=self.body(), headers=self.headers("tenant", uuid4())).json()
        self.assertEqual(self.client.put(f"/requests/{created['id']}/acknowledgement", headers=self.headers("owner")).status_code, 200)
        run = self.client.post(f"/requests/{created['id']}/investigations", headers=self.headers("owner", uuid4())).json()
        body = {"investigation_id": run["id"], "rationale": "Fictional repair proposal.",
                "evidence_ids": [f"vendor:{demo_id('cottage/vendor')}"],
                "details": {"kind": "contact_vendor", "vendor_id": str(demo_id("cottage/vendor")), "message": "Fictional quote request."}}
        action = self.client.post(f"/requests/{created['id']}/actions", json=body, headers=self.headers("owner", uuid4())).json()
        self.assertEqual((action["status"], action["revision"]), ("proposed", 1))
        action = self.decide(action).json()
        self.assertEqual(action["current_decision"]["authority"], "owner")
        key = uuid4()
        done = self.execute(action, key=key)
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()["status"], "executed")
        self.assertEqual(done.json()["result"]["mode"], "test_double")
        self.assertEqual(self.execute(action, key=key).json(), done.json())
        self.assertEqual(self.execute(action).status_code, 409)
        self.assertEqual(len(self.executor.calls), 1)

        events = self.timeline(created["id"])
        self.assertEqual([e["sequence"] for e in events], list(range(1, len(events) + 1)))
        kinds = [e["kind"] for e in events]
        self.assertEqual(kinds[:3], ["request.submitted", "request.acknowledged", "investigation.started"])
        self.assertEqual(kinds[-5:], ["action.proposed", "action.approved", "action.execution_started",
                                      "action.executed", "action.denied"])
        self.assertEqual(events[-1]["details"]["reason"], "already_executed")
        self.assertEqual(self.client.get(f"/requests/{created['id']}/timeline", headers=self.headers("tenant")).status_code, 403)
        self.assertEqual(self.client.get(f"/requests/{created['id']}/timeline", headers=self.headers("other_owner")).status_code, 404)

    def test_unapproved_and_rejected_actions_cannot_execute(self):
        action = self.propose().json()
        self.assertEqual(self.execute(action).status_code, 409)
        rejected = self.decide(action, "rejected", reason="Need tenant details first").json()
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self.execute(rejected).status_code, 409)
        self.assertEqual(self.decide(rejected, "approved").status_code, 409)
        self.assertEqual(self.executor.calls, [])
        self.assertEqual(self.denials(demo_id("tap_request")), ["not_approved", "not_approved", "already_decided"])

    def test_role_policy_governs_proposal_decision_and_execution(self):
        for alias, status in (("tenant", 403), ("other_owner", 404), ("outsider", 404)):
            self.assertEqual(self.propose(request="water_request_one", alias=alias).status_code, status)
        contact = self.propose(request="water_request_one", alias="member").json()
        self.assertEqual(self.decide(contact, alias="member").status_code, 403)
        self.assertEqual(self.decide(contact, alias="coordinator").status_code, 200)
        self.assertEqual(self.execute(contact, alias="member").status_code, 403)
        self.assertEqual(self.execute(contact, alias="coordinator").json()["status"], "executed")

        def spend_of(amount):
            return self.propose({"kind": "authorize_spend", "vendor_id": str(demo_id("apartments/vendor")),
                                 "amount": amount, "currency": "USD"}, request="water_request_one").json()
        within = self.decide(spend_of("220.00"), alias="coordinator")  # Team limit is USD 500.00.
        self.assertEqual(within.status_code, 200)
        self.assertEqual(self.execute(within.json(), alias="coordinator").json()["status"], "executed")
        spend = spend_of("750.00")
        self.assertEqual(self.decide(spend, alias="coordinator").status_code, 403)
        spend = self.decide(spend, alias="owner").json()
        self.assertEqual(self.execute(spend, alias="coordinator").status_code, 403)
        self.assertEqual(self.execute(spend, alias="owner").json()["status"], "executed")
        self.assertEqual(self.denials(demo_id("water_request_one")),
                         ["unauthorized_decision", "unauthorized_execution", "unauthorized_decision", "unauthorized_execution"])
        self.assertEqual(self.client.get(f"/actions/{spend['id']}", headers=self.headers("other_owner")).status_code, 404)

    def test_changed_action_invalidates_approval(self):
        action = self.approved()
        revision = {"expected_revision": 1, "rationale": action["rationale"], "evidence_ids": action["evidence_ids"],
                    "details": action["details"] | {"message": "Fictional: also check the shower valve."}}
        changed = self.client.put(f"/actions/{action['id']}", json=revision, headers=self.headers("owner")).json()
        self.assertEqual((changed["status"], changed["revision"], changed["current_decision"]), ("proposed", 2, None))
        self.assertNotEqual(changed["details_hash"], action["details_hash"])
        retried = self.client.put(f"/actions/{action['id']}", json=revision, headers=self.headers("owner")).json()
        self.assertEqual(retried["revision"], 2)
        stale = self.client.put(f"/actions/{action['id']}", json=revision | {"rationale": "other"}, headers=self.headers("owner"))
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.execute(changed).status_code, 409)
        self.assertEqual(self.decide(action).status_code, 409)  # Old revision and hash.
        self.assertEqual(self.executor.calls, [])
        self.assertEqual(self.execute(self.decide(changed).json()).json()["status"], "executed")
        kinds = [e["kind"] for e in self.timeline(demo_id("tap_request"))]
        self.assertIn("action.approval_invalidated", kinds)
        self.assertEqual(self.denials(demo_id("tap_request")), ["stale_revision", "not_approved", "stale_decision"])

    def test_expired_approval_and_lost_approver_authority_block_execution(self):
        action = self.approved()
        later = datetime.now(timezone.utc) + actions.APPROVAL_LIFETIME + timedelta(minutes=1)
        with patch("property_rescue.actions.now", return_value=later):
            self.assertEqual(self.execute(action).status_code, 409)
        team_action = self.approved(request="water_request_one", approver="coordinator")
        with Session(self.engine) as db, db.begin():
            db.get(User, demo_id("coordinator")).active = False
        self.assertEqual(self.execute(team_action, alias="owner").status_code, 409)
        self.assertEqual(self.executor.calls, [])
        self.assertEqual(self.denials(demo_id("tap_request")), ["approval_expired"])
        self.assertEqual(self.denials(demo_id("water_request_one")), ["approver_lost_authority"])

    def test_concurrent_execution_with_different_keys_executes_once(self):
        action = self.approved()
        def attempt(_):
            with Session(self.engine) as db:
                try:
                    return actions.execute(db, db.get(User, demo_id("owner")), UUID(action["id"]), uuid4(), self.executor).status
                except DomainError as error:
                    return error.status
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(attempt, range(4)))
        self.assertEqual(sorted(results, key=str), [409, 409, 409, "executed"])
        self.assertEqual(len(self.executor.calls), 1)

    def test_execution_failure_is_sanitized_visible_and_retryable(self):
        action = self.approved()
        failing = RecordingExecutor(fail=True)
        key = uuid4()
        with TestClient(create_app(self.engine, executor=failing)) as client:
            failed = client.post(f"/actions/{action['id']}/execution", headers=self.headers("owner", key)).json()
            replay = client.post(f"/actions/{action['id']}/execution", headers=self.headers("owner", key)).json()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(replay, failed)
        self.assertEqual(len(failing.calls), 1)
        events = self.timeline(demo_id("tap_request"))
        self.assertIn("action.execution_failed", [e["kind"] for e in events])
        self.assertNotIn("SECRET", json.dumps(events) + json.dumps(failed))
        self.assertEqual(self.execute(action).json()["status"], "executed")
        # The earlier failed attempt's key still replays rather than executing again.
        self.assertEqual(self.execute(action, key=key).json()["status"], "executed")
        self.assertEqual(len(self.executor.calls), 1)

    def test_close_request_only_through_approved_execution(self):
        with Session(self.engine) as db:
            with self.assertRaises(IntegrityError):
                db.execute(update(MaintenanceRequest).where(MaintenanceRequest.id == demo_id("tap_request")).values(status="closed"))
                db.commit()
        close = self.approved({"kind": "close_request", "resolution": "Fictional: tenant confirmed repair."})
        executed = self.execute(close).json()
        self.assertEqual(executed["result"].get("request_status"), "closed", executed)
        self.assertEqual(self.executor.calls, [])  # Internal transition, no external adapter.
        tenant_view = self.client.get(f"/requests/{demo_id('tap_request')}", headers=self.headers("tenant")).json()
        self.assertEqual(tenant_view["status"], "closed")
        self.assertEqual(tenant_view["description"], "Original fictional tenant complaint: tap_request.")
        self.assertEqual(self.propose().status_code, 409)
        self.assertIn("request.closed", [e["kind"] for e in self.timeline(demo_id("tap_request"))])

    def test_database_refuses_bypass_and_audit_tampering(self):
        action = self.propose().json()
        def refused(statement, **params):
            with Session(self.engine) as db:
                with self.assertRaises((IntegrityError, InternalError)):
                    db.execute(text(statement), params)
                    db.commit()
        refused("UPDATE maintenance_actions SET status = 'executing', execution_key = gen_random_uuid() WHERE id = :id", id=action["id"])
        refused("UPDATE maintenance_actions SET status = 'approved' WHERE id = :id", id=action["id"])
        refused("UPDATE maintenance_actions SET details = '{}'::jsonb WHERE id = :id", id=action["id"])
        refused("INSERT INTO action_decisions VALUES (gen_random_uuid(), :id, 1, repeat('0', 64), 'approved', :u, 'owner', NULL, now(), now() + interval '1 hour')",
                id=action["id"], u=str(demo_id("owner")))
        with Session(self.engine) as db, db.begin():  # Expired approval written directly.
            db.execute(text("INSERT INTO action_decisions VALUES (gen_random_uuid(), :id, 1, :h, 'approved', :u, 'owner', NULL, now() - interval '2 days', now() - interval '1 day')"),
                       {"id": action["id"], "h": action["details_hash"], "u": str(demo_id("owner"))})
            db.execute(text("UPDATE maintenance_actions SET status = 'approved' WHERE id = :id"), {"id": action["id"]})
        refused("UPDATE maintenance_actions SET status = 'executing', execution_key = gen_random_uuid() WHERE id = :id", id=action["id"])
        refused("UPDATE action_decisions SET expires_at = now() + interval '1 day' WHERE action_id = :id", id=action["id"])
        refused("DELETE FROM action_decisions WHERE action_id = :id", id=action["id"])
        refused("UPDATE timeline_events SET kind = 'edited'")
        refused("DELETE FROM timeline_events")
        self.assertEqual(self.execute(action).status_code, 409)
        self.assertEqual(self.executor.calls, [])

    def test_proposal_validation_and_idempotency(self):
        run = self.investigate()
        key = uuid4()
        first = self.propose(run=run, key=key)
        self.assertEqual(first.status_code, 201)
        replay = self.propose(run=run, key=key)
        self.assertEqual((replay.status_code, replay.json()["id"]), (200, first.json()["id"]))
        self.assertEqual(self.propose(run=run, key=key, rationale="different").status_code, 409)
        other_vendor = {"kind": "contact_vendor", "vendor_id": str(demo_id("other_property/vendor")), "message": "x"}
        self.assertEqual(self.propose(other_vendor, run=run).status_code, 422)
        self.assertEqual(self.propose(run=run, evidence_ids=["vendor:invented"]).status_code, 422)
        foreign_run = self.investigate("water_request_one")
        self.assertEqual(self.propose(run=foreign_run).status_code, 422)
        for details in ({"kind": "schedule_visit", "vendor_id": str(demo_id("cottage/vendor")),
                         "window_start": "2026-11-10T09:00:00+00:00", "window_end": "2026-11-10T08:00:00+00:00"},
                        {"kind": "schedule_visit", "vendor_id": str(demo_id("cottage/vendor")),
                         "window_start": "2026-11-10T09:00:00", "window_end": "2026-11-10T10:00:00"},
                        {"kind": "authorize_spend", "vendor_id": str(demo_id("cottage/vendor")), "amount": "-5", "currency": "USD"},
                        {"kind": "close_request", "resolution": "done", "extra": True}):
            self.assertEqual(self.propose(details, run=run).status_code, 422, details)
        with Session(self.engine) as db:
            self.assertEqual(len(db.scalars(select(MaintenanceAction)).all()), 1)

    def test_timeline_stream_delivers_events_and_resumes(self):
        self.client.put(f"/requests/{demo_id('tap_request')}/acknowledgement", headers=self.headers("owner"))
        self.investigate()
        url = f"/requests/{demo_id('tap_request')}/timeline/stream?timeout=1"
        r = self.client.get(url, headers=self.headers("owner"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/event-stream"))
        self.assertIn("event: request.acknowledged", r.text)
        self.assertIn("id: 1\n", r.text)
        resumed = self.client.get(url, headers=self.headers("owner") | {"Last-Event-ID": "1"})
        self.assertNotIn("event: request.acknowledged", resumed.text)
        self.assertIn("event: investigation.completed", resumed.text)
        self.assertEqual(self.client.get(url, headers=self.headers("tenant")).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers("other_owner")).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 401)
