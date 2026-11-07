"""Real PostgreSQL integration tests; each test owns a disposable schema.

Run with APP_DATABASE_URL for the application database. No SQLite substitute.
The suite never drops an existing schema or touches the seeded public schema.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from property_rescue.api import create_app
from property_rescue.config import ConfigurationError
from property_rescue.database import database_url
from property_rescue.models import (Base, Credential, Incident, MaintenanceRequest, Membership,
                                   Property, Tenancy, User, Warranty)
from property_rescue.schemas import RequestCreate
from property_rescue.seed import PEOPLE, demo_id, seed
from property_rescue.service import DomainError, create_request, token_hash


class DatabaseConfigTests(unittest.TestCase):
    def test_rejects_missing_or_wrong_driver_without_echoing_secret(self):
        for url in ("", "postgresql://user:secret@localhost/db", "sqlite:///secret", "not-a-url"):
            with self.subTest(url=url), patch.dict(os.environ, {"APP_DATABASE_URL": url}):
                with self.assertRaises(ConfigurationError) as error:
                    database_url()
                self.assertNotIn("secret", str(error.exception))


@unittest.skipUnless(os.environ.get("APP_DATABASE_URL"), "PostgreSQL APP_DATABASE_URL required")
class PostgresTestCase(unittest.TestCase):
    def setUp(self):
        self.url = database_url()
        self.schema = "test_" + uuid4().hex
        self.admin = create_engine(self.url, hide_parameters=True)
        with self.admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.addCleanup(self.cleanup_schema)
        self.engine = create_engine(self.url, hide_parameters=True,
                                   connect_args={"options": f"-csearch_path={self.schema}"})
        self.migrate("head")
        self.tokens = {alias: "test-only-" + alias + "-" + "x" * 40 for alias in PEOPLE}
        with Session(self.engine) as db, db.begin():
            seed(db, self.tokens)
        self.client = TestClient(create_app(self.engine))
        self.addCleanup(self.client.close)

    def cleanup_schema(self):
        if hasattr(self, "engine"):
            self.engine.dispose()
        with self.admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.admin.dispose()

    def migrate(self, target, *, down=False):
        config = Config("alembic.ini")
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            (command.downgrade if down else command.upgrade)(config, target)

    def headers(self, alias="tenant", key=None):
        headers = {"Authorization": "Bearer " + self.tokens[alias]}
        if key:
            headers["Idempotency-Key"] = str(key)
        return headers

    def body(self, **changes):
        return {"property_id": str(demo_id("cottage")), "title": "Leaking tap",
                "description": "Cold tap keeps dripping overnight.", "category": "plumbing"} | changes


class MaintenanceTests(PostgresTestCase):
    def test_request_persists_across_app_instances(self):
        response = self.client.post("/requests", json=self.body(), headers=self.headers(key=uuid4()))
        self.assertEqual(response.status_code, 201, response.text)
        record = response.json()
        self.assertEqual(record["tenant_id"], str(demo_id("tenant")))
        self.assertEqual(record["status"], "submitted")
        with TestClient(create_app(self.engine)) as second:
            fetched = second.get("/requests/" + record["id"], headers=self.headers())
        self.assertEqual(fetched.json(), record)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MaintenanceRequest)), 5)

    def test_retries_return_one_record_and_changed_payload_conflicts(self):
        key = uuid4()
        first = self.client.post("/requests", json=self.body(), headers=self.headers(key=key))
        repeated = self.client.post("/requests", json=self.body(), headers=self.headers(key=key))
        changed = self.client.post("/requests", json=self.body(title="Different"), headers=self.headers(key=key))
        self.assertEqual((first.status_code, repeated.status_code, changed.status_code), (201, 200, 409))
        self.assertEqual(first.json()["id"], repeated.json()["id"])

    def test_concurrent_retries_commit_only_once(self):
        key = uuid4()
        body = RequestCreate(**self.body())
        def submit(_):
            with Session(self.engine, expire_on_commit=False) as db:
                user = db.get(User, demo_id("tenant"))
                row, created = create_request(db, user, body, key)
                return row.id, created
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(submit, range(4)))
        self.assertEqual(len({row_id for row_id, _ in results}), 1)
        self.assertEqual(sum(created for _, created in results), 1)

    def test_invalid_input_and_identity_injection_are_rejected(self):
        for changes in ({"title": "   "}, {"description": ""}, {"title": "x" * 201},
                        {"category": "unknown"}, {"property_id": "bad"},
                        {"tenant_id": str(demo_id("other_tenant"))}, {"status": "closed"},
                        {"incident_id": str(demo_id("incident"))}, {"role": "owner"}):
            with self.subTest(changes=changes):
                r = self.client.post("/requests", json=self.body(**changes), headers=self.headers(key=uuid4()))
                self.assertEqual(r.status_code, 422)
        for key in (None, "not-a-uuid"):
            r = self.client.post("/requests", json=self.body(), headers=self.headers(key=key))
            self.assertEqual(r.status_code, 422)

    def test_authentication_is_required_and_roles_cannot_be_spoofed(self):
        for headers in ({}, {"Authorization": "Bearer bad"}, {"X-User-ID": str(demo_id("owner"))},
                        {"Authorization": "Basic arbitrary"}):
            r = self.client.get("/requests", headers=headers)
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.headers["www-authenticate"], "Bearer")
        r = self.client.get("/me", headers=self.headers() | {"X-Role": "owner"})
        self.assertEqual(r.json()["role"], "tenant")
        self.assertNotIn("token_hash", r.text)
        with Session(self.engine) as db, db.begin():
            db.get(User, demo_id("tenant")).active = False
        self.assertEqual(self.client.get("/me", headers=self.headers()).status_code, 401)

    def test_revoked_token_cannot_authenticate(self):
        with Session(self.engine) as db, db.begin():
            db.delete(db.get(Credential, token_hash(self.tokens["tenant"])))
        self.assertEqual(self.client.get("/requests", headers=self.headers()).status_code, 401)

    def test_only_active_tenant_can_create_for_own_property(self):
        for alias in ("owner", "coordinator", "member"):
            self.assertEqual(self.client.post("/requests", json=self.body(), headers=self.headers(alias, uuid4())).status_code, 403)
        self.assertEqual(self.client.post("/requests", json=self.body(property_id=str(demo_id("other_property"))),
                                          headers=self.headers(key=uuid4())).status_code, 404)
        with Session(self.engine) as db, db.begin():
            db.get(Tenancy, (demo_id("cottage"), demo_id("tenant"))).active = False
        self.assertEqual(self.client.post("/requests", json=self.body(), headers=self.headers(key=uuid4())).status_code, 404)

    def test_read_scope_excludes_other_tenants_owners_and_teams(self):
        expected = {"tenant": 2, "tenant_two": 1, "other_tenant": 1,
                    "owner": 3, "other_owner": 1, "coordinator": 2, "member": 2, "outsider": 0}
        for alias, count in expected.items():
            with self.subTest(alias=alias):
                r = self.client.get("/requests", headers=self.headers(alias))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(len(r.json()), count)
        private = "/requests/" + str(demo_id("tap_request"))
        for alias in ("tenant_two", "other_owner", "coordinator", "outsider"):
            self.assertEqual(self.client.get(private, headers=self.headers(alias)).status_code, 404)

    def test_property_scope_and_pagination(self):
        for alias, count in (("tenant", 2), ("owner", 2), ("coordinator", 1), ("outsider", 0)):
            self.assertEqual(len(self.client.get("/properties", headers=self.headers(alias)).json()), count)
        pages = [self.client.get(f"/requests?limit=1&offset={offset}", headers=self.headers("owner")).json()
                 for offset in (0, 1, 2)]
        self.assertEqual(len({page[0]["id"] for page in pages}), 3)
        for query in ("limit=101", "limit=0", "offset=-1"):
            self.assertEqual(self.client.get("/requests?" + query, headers=self.headers()).status_code, 422)

    def test_history_warranties_vendors_and_incidents_are_scoped(self):
        root = "/properties/" + str(demo_id("apartments"))
        for resource in ("history", "warranties", "vendors", "incidents"):
            with self.subTest(resource=resource):
                for alias in ("owner", "coordinator", "member"):
                    r = self.client.get(root + "/" + resource, headers=self.headers(alias))
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(len(r.json()), 1)
                self.assertEqual(self.client.get(root + "/" + resource, headers=self.headers()).status_code, 403)
                self.assertEqual(self.client.get(root + "/" + resource, headers=self.headers("other_owner")).status_code, 404)
        history = self.client.get(root + "/history", headers=self.headers("owner")).json()[0]
        self.assertEqual(history["cost"], "185.00")

    def test_acknowledgement_is_authorized_idempotent_and_preserves_original(self):
        path = "/requests/" + str(demo_id("water_request_one"))
        original = self.client.get(path, headers=self.headers()).json()
        for alias, expected in (("tenant", 403), ("member", 403), ("outsider", 404)):
            self.assertEqual(self.client.put(path + "/acknowledgement", headers=self.headers(alias)).status_code, expected)
        for _ in range(2):
            r = self.client.put(path + "/acknowledgement", headers=self.headers("coordinator"))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), original | {"status": "acknowledged"})
        self.assertEqual(self.client.put("/requests/" + str(demo_id("tap_request")) + "/acknowledgement",
                                        headers=self.headers("owner")).status_code, 200)

    def test_database_protects_original_content_and_reverse_transition(self):
        for field, value in (("description", "rewritten"), ("title", "changed"),
                             ("tenant_id", demo_id("tenant_two")), ("category", "general")):
            with self.subTest(field=field), Session(self.engine) as db:
                with self.assertRaises(IntegrityError):
                    db.execute(update(MaintenanceRequest).where(MaintenanceRequest.id == demo_id("tap_request")).values(**{field: value}))
                    db.commit()
        with Session(self.engine) as db, db.begin():
            db.get(MaintenanceRequest, demo_id("tap_request")).status = "acknowledged"
        with Session(self.engine) as db:
            with self.assertRaises(IntegrityError):
                db.get(MaintenanceRequest, demo_id("tap_request")).status = "submitted"
                db.commit()

    def test_incident_link_preserves_original_and_rejects_other_property(self):
        with Session(self.engine) as db, db.begin():
            record = db.get(MaintenanceRequest, demo_id("water_request_one"))
            before = (record.id, record.tenant_id, record.title, record.description)
            record.incident_id = None
        with Session(self.engine) as db, db.begin():
            record = db.get(MaintenanceRequest, demo_id("water_request_one"))
            record.incident_id = demo_id("incident")
            self.assertEqual((record.id, record.tenant_id, record.title, record.description), before)
        with Session(self.engine) as db:
            with self.assertRaises(IntegrityError):
                db.get(MaintenanceRequest, demo_id("tap_request")).incident_id = demo_id("incident")
                db.commit()

    def test_relational_roles_coordinator_and_warranty_dates_are_enforced(self):
        cases = [
            Property(id=uuid4(), name="Invalid", address="Demo", owner_id=demo_id("tenant")),
            Tenancy(property_id=demo_id("cottage"), tenant_id=demo_id("owner")),
            Incident(id=uuid4(), property_id=demo_id("apartments"), team_id=demo_id("team"),
                     coordinator_id=demo_id("member"), title="Invalid"),
            Incident(id=uuid4(), property_id=demo_id("cottage"), team_id=demo_id("team"),
                     coordinator_id=demo_id("coordinator"), title="Invalid"),
            Warranty(id=uuid4(), property_id=demo_id("cottage"), asset="Demo", provider="Demo",
                     starts_on=date(2026, 2, 1), ends_on=date(2026, 1, 1), terms="Invalid"),
        ]
        for obj in cases:
            with self.subTest(model=type(obj).__name__), Session(self.engine) as db:
                with self.assertRaises(IntegrityError):
                    db.add(obj)
                    db.commit()

    def test_seed_repeated_without_duplicates_or_resetting_state(self):
        with Session(self.engine) as db, db.begin():
            db.get(MaintenanceRequest, demo_id("tap_request")).status = "acknowledged"
        with Session(self.engine) as db, db.begin():
            counts = {t.name: db.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
            seed(db, self.tokens)
            seed(db, self.tokens)
            self.assertEqual(counts, {t.name: db.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables})
            self.assertEqual(db.get(MaintenanceRequest, demo_id("tap_request")).status, "acknowledged")

    def test_migration_schema_matches_models_and_round_trips(self):
        with self.engine.connect() as conn:
            self.assertEqual(compare_metadata(MigrationContext.configure(conn), Base.metadata), [])
        self.migrate("base", down=True)
        self.migrate("head")
        with self.engine.connect() as conn:
            self.assertEqual(compare_metadata(MigrationContext.configure(conn), Base.metadata), [])

    def test_database_errors_and_validation_do_not_expose_secrets(self):
        with patch("property_rescue.service.authenticate", side_effect=OperationalError("secret-sql", {}, Exception("secret-password"))):
            r = self.client.get("/me", headers=self.headers())
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("secret", r.text)
        r = self.client.post("/requests", json=self.body(secret="do-not-echo"), headers=self.headers(key=uuid4()))
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("do-not-echo", r.text)


if __name__ == "__main__":
    unittest.main()
