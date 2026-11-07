"""Idempotent, explicitly fictional local demo data and random development tokens."""

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import secrets
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.orm import Session

from property_rescue.database import build_engine
from property_rescue.models import (Credential, Incident, MaintenanceHistory, MaintenanceRequest,
                                   Membership, PlanningEstimate, Property, Team, Tenancy, User, Vendor, Warranty)
from property_rescue.service import token_hash


PEOPLE = {
    "owner": ("Morgan Demo", "owner"),
    "other_owner": ("Taylor Demo", "owner"),
    "tenant": ("Alex Demo", "tenant"),
    "tenant_two": ("Jamie Demo", "tenant"),
    "other_tenant": ("Casey Demo", "tenant"),
    "coordinator": ("Robin Demo", "staff"),
    "coordinator_two": ("Riley Demo", "staff"),
    "member": ("Drew Demo", "staff"),
    "outsider": ("Sky Demo", "staff"),
}


def demo_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, "property-rescue/fictional-demo/v1/" + name)


def seed(db: Session, tokens: dict[str, str]) -> None:
    """Add absent records without resetting user edits. Caller owns commit/rollback."""
    def add(model, key, **values):
        if db.get(model, key) is None:
            db.add(model(**values))
            db.flush()

    for alias, (name, role) in PEOPLE.items():
        add(User, demo_id(alias), id=demo_id(alias), name=name, role=role, active=True)
        digest = token_hash(tokens[alias])
        add(Credential, digest, token_hash=digest, user_id=demo_id(alias))
    add(Team, demo_id("team"), id=demo_id("team"), name="Fictional Harbor Management",
        coordinator_spend_limit=Decimal("500.00"))
    team = db.get(Team, demo_id("team"))
    if team.coordinator_spend_limit is None:  # Fill the policy added after first seeding only.
        team.coordinator_spend_limit = Decimal("500.00")
    for alias, role in (("coordinator", "coordinator"), ("coordinator_two", "coordinator"), ("member", "member")):
        add(Membership, (demo_id("team"), demo_id(alias)), team_id=demo_id("team"),
            user_id=demo_id(alias), role=role)
    for alias, owner, team in (("cottage", "owner", None), ("apartments", "owner", demo_id("team")),
                               ("other_property", "other_owner", None)):
        add(Property, demo_id(alias), id=demo_id(alias), name=f"Fictional {alias.replace('_', ' ').title()}",
            address=f"{alias.title()} Lane, Demo City (fictional)", owner_id=demo_id(owner), team_id=team)
    for prop, tenant in (("cottage", "tenant"), ("apartments", "tenant"),
                         ("apartments", "tenant_two"), ("other_property", "other_tenant")):
        add(Tenancy, (demo_id(prop), demo_id(tenant)), property_id=demo_id(prop),
            tenant_id=demo_id(tenant), active=True)
    add(Incident, demo_id("incident"), id=demo_id("incident"), property_id=demo_id("apartments"),
        team_id=demo_id("team"), coordinator_id=demo_id("coordinator"),
        title="Fictional shared hot-water interruption", status="open")
    for name, prop, tenant, incident in (
        ("tap_request", "cottage", "tenant", None),
        ("water_request_one", "apartments", "tenant", demo_id("incident")),
        ("water_request_two", "apartments", "tenant_two", demo_id("incident")),
        ("other_request", "other_property", "other_tenant", None),
    ):
        add(MaintenanceRequest, demo_id(name), id=demo_id(name), property_id=demo_id(prop),
            tenant_id=demo_id(tenant), incident_id=incident, title="Fictional water issue",
            description=f"Original fictional tenant complaint: {name}.", category="plumbing",
            status="submitted", idempotency_key=demo_id(name + "/key"),
            created_at=datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
    for prop in ("cottage", "apartments", "other_property"):
        add(Vendor, demo_id(prop + "/vendor"), id=demo_id(prop + "/vendor"), property_id=demo_id(prop),
            name="Fictional Harbor Plumbing", specialty="Plumbing", contact_email="repairs@example.invalid")
        add(MaintenanceHistory, demo_id(prop + "/history"), id=demo_id(prop + "/history"),
            property_id=demo_id(prop), vendor_id=demo_id(prop + "/vendor"),
            performed_on=date(2026, 7, 10), summary="Fictional valve replacement; receipt DEMO-001.",
            cost=Decimal("185.00"))
        add(Warranty, demo_id(prop + "/warranty"), id=demo_id(prop + "/warranty"),
            property_id=demo_id(prop), asset="Demo water heater", provider="Fictional Manufacturer",
            starts_on=date(2026, 1, 1), ends_on=date(2028, 1, 1),
            terms="Fictional parts-only coverage. No real warranty or vendor commitment.")
        add(PlanningEstimate, demo_id(prop + "/estimate"), id=demo_id(prop + "/estimate"),
            property_id=demo_id(prop), vendor_id=demo_id(prop + "/vendor"), category="plumbing",
            low=Decimal("150.00"), high=Decimal("300.00"), currency="USD",
            assumptions="Fictional allowance for a minor valve/tap repair during business hours. "
                        "Excludes major replacement, hidden damage, tax and emergency charges. "
                        "Diagnosis, vendor availability and actual quote are unverified.",
            recorded_on=date(2026, 11, 1), valid_until=date(2026, 12, 1))


def main() -> None:
    path = Path(".local/app/demo-tokens.json")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        with path.open("x") as output:
            path.chmod(0o600)
            json.dump({alias: secrets.token_urlsafe(32) for alias in PEOPLE}, output, indent=2)
    tokens = json.loads(path.read_text())
    if missing := set(PEOPLE) - set(tokens):
        # Demo accounts added in later checkpoints get tokens; existing tokens are kept.
        tokens |= {alias: secrets.token_urlsafe(32) for alias in missing}
        temporary = path.with_suffix(".tmp")
        with temporary.open("x") as output:
            temporary.chmod(0o600)
            json.dump(tokens, output, indent=2)
        temporary.replace(path)
    if set(tokens) != set(PEOPLE) or any(not isinstance(t, str) or len(t) < 32 for t in tokens.values()):
        raise SystemExit("Invalid local demo token file; no data changed")
    engine = build_engine()
    try:
        with Session(engine) as db, db.begin():
            seed(db, tokens)
    finally:
        engine.dispose()
    print("Fictional demo seeded. Tokens are in .local/app/demo-tokens.json; not displayed.")


if __name__ == "__main__":
    main()
