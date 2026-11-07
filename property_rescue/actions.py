"""Proposals, role-bound decisions and approval-enforced execution of maintenance actions.

Execution re-verifies authority and the exact approved revision here, and database
triggers independently refuse execution without a matching unexpired approval.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from property_rescue.models import (ActionDecision, Incident, Investigation, MaintenanceAction, MaintenanceRequest,
                                   Membership, Property, RequestState, Team, TimelineEvent, User, Vendor)
from property_rescue.service import DomainError, get_request, lock_request, managed_property, record_event

APPROVAL_LIFETIME = timedelta(hours=24)
REVISABLE = {"proposed", "approved", "rejected", "failed"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ContactVendor(Strict):
    kind: Literal["contact_vendor"]
    vendor_id: UUID
    message: str = Field(min_length=1, max_length=2000)


class ScheduleVisit(Strict):
    kind: Literal["schedule_visit"]
    vendor_id: UUID
    window_start: datetime
    window_end: datetime

    @field_validator("window_start", "window_end")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Include a timezone offset")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def window(self):
        if not timedelta(0) < self.window_end - self.window_start <= timedelta(hours=12):
            raise ValueError("Window must end after it starts and last at most 12 hours")
        return self


class AuthorizeSpend(Strict):
    kind: Literal["authorize_spend"]
    vendor_id: UUID
    amount: Decimal = Field(gt=0, le=100000, max_digits=8, decimal_places=2)
    currency: Literal["USD"]


class CloseRequest(Strict):
    kind: Literal["close_request"]
    resolution: str = Field(min_length=1, max_length=2000)


Details = Annotated[ContactVendor | ScheduleVisit | AuthorizeSpend | CloseRequest, Field(discriminator="kind")]


class ActionCreate(Strict):
    investigation_id: UUID
    details: Details
    rationale: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)


class ActionRevision(Strict):
    expected_revision: int = Field(ge=1)
    details: Details
    rationale: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)


class DecisionCreate(Strict):
    decision: Literal["approved", "rejected"]
    revision: int = Field(ge=1)
    details_hash: str = Field(min_length=64, max_length=64)
    reason: str | None = Field(default=None, max_length=2000)


class ActionExecutor(Protocol):
    """External side effects. Receives the idempotency key so real providers can deduplicate."""
    def execute(self, action: MaintenanceAction, vendor: Vendor | None, key: UUID) -> dict: ...


class FictionalDemoExecutor:
    """Demo adapter: records what would be sent. Contacts nobody and moves no money."""
    def execute(self, action: MaintenanceAction, vendor: Vendor | None, key: UUID) -> dict:
        return {"mode": "fictional_demo", "delivery": "not_sent", "vendor": vendor.name if vendor else None,
                "summary": f"Approved {action.kind} recorded; no real vendor, calendar or payment system contacted."}


def now() -> datetime:
    return datetime.now(timezone.utc)


def authority(db: Session, user: User, prop: Property, request: MaintenanceRequest | None = None) -> str | None:
    """Owner, coordinator or member. Requests in an incident answer only to its coordinator."""
    if user.role == "owner" and prop.owner_id == user.id:
        return "owner"
    if user.role != "staff" or prop.team_id is None:
        return None
    membership = db.get(Membership, (prop.team_id, user.id))
    if membership is None:
        return None
    if membership.role == "coordinator" and request is not None and request.incident_id is not None:
        incident = db.get(Incident, request.incident_id)
        return "coordinator" if incident.coordinator_id == user.id else "member"
    return membership.role


def permitted(db: Session, user: User, prop: Property, action: MaintenanceAction) -> str | None:
    """Authority under which `user` may decide and execute `action`, or None.

    Owners: everything. Coordinators: vendor contact, scheduling and closure, and
    spending up to their team's limit. Members: propose only.
    """
    role = authority(db, user, prop, db.get(MaintenanceRequest, action.request_id))
    if role == "owner":
        return role
    if role != "coordinator":
        return None
    if action.kind != "authorize_spend":
        return role
    limit = db.scalar(select(Team.coordinator_spend_limit).where(Team.id == prop.team_id))
    return role if limit is not None and Decimal(action.details["amount"]) <= limit else None


def get_action(db: Session, user: User, action_id: UUID, *, lock: bool = False) -> tuple[MaintenanceAction, Property]:
    query = select(MaintenanceAction).where(MaintenanceAction.id == action_id)
    action = db.scalar(query)
    if action is None:
        raise DomainError(404, "Action not found")
    if lock:
        lock_request(db, action.request_id)
        action = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    request = get_request(db, user, action.request_id)
    return action, managed_property(db, user, request.property_id)


def deny(db: Session, user: User, action: MaintenanceAction, status: int, code: str, detail: str):
    """Discard pending changes, keep an audit entry of the refusal, then refuse."""
    action_id, request_id, revision = action.id, action.request_id, action.revision
    db.rollback()
    record_event(db, request_id, "action.denied", user, action_id, reason=code, revision=revision)
    db.commit()
    raise DomainError(status, detail)


def validate(db: Session, request: MaintenanceRequest, investigation_id: UUID,
             details: ContactVendor | ScheduleVisit | AuthorizeSpend | CloseRequest, evidence_ids: list[str]) -> None:
    run = db.get(Investigation, investigation_id)
    if run is None or run.request_id != request.id:
        raise DomainError(422, "Investigation does not belong to this request")
    if run.status != "ready_for_review":
        raise DomainError(409, "Investigation evidence is incomplete")
    known = {e["id"] for section in run.sections.values() for e in section.get("evidence", [])}
    if not set(evidence_ids) <= known:
        raise DomainError(422, "Evidence IDs must come from the investigation")
    vendor_id = getattr(details, "vendor_id", None)
    if vendor_id is not None and db.scalar(select(Vendor.id).where(
            Vendor.id == vendor_id, Vendor.property_id == request.property_id)) is None:
        raise DomainError(422, "Vendor is not in this property's directory")


def view(db: Session, action: MaintenanceAction) -> dict:
    decision = db.scalar(select(ActionDecision).where(ActionDecision.action_id == action.id,
                                                     ActionDecision.revision == action.revision))
    return {
        "id": str(action.id), "request_id": str(action.request_id), "investigation_id": str(action.investigation_id),
        "kind": action.kind, "details": action.details, "rationale": action.rationale,
        "evidence_ids": action.evidence_ids, "revision": action.revision, "details_hash": action.details_hash,
        "status": action.status, "proposed_by": str(action.proposed_by), "result": action.result,
        "current_decision": None if decision is None else {
            "decision": decision.decision, "decided_by": str(decision.decided_by), "authority": decision.authority,
            "reason": decision.reason, "decided_at": decision.decided_at.isoformat(),
            "expires_at": decision.expires_at.isoformat()},
    }


def propose(db: Session, user: User, request_id: UUID, body: ActionCreate, key: UUID) -> tuple[MaintenanceAction, bool]:
    request = get_request(db, user, request_id)
    prop = managed_property(db, user, request.property_id)
    if authority(db, user, prop, request) is None:
        raise DomainError(403, "Owner or assigned team staff required")
    content = {"investigation_id": body.investigation_id, "kind": body.details.kind,
               "details": body.details.model_dump(mode="json"), "rationale": body.rationale,
               "evidence_ids": body.evidence_ids}
    prior_query = select(MaintenanceAction).where(MaintenanceAction.request_id == request_id,
                                                MaintenanceAction.idempotency_key == key)

    def replay(prior: MaintenanceAction) -> tuple[MaintenanceAction, bool]:
        if any(getattr(prior, name) != value for name, value in content.items()):
            raise DomainError(409, "Idempotency key already used for a different proposal")
        return prior, False

    if (prior := db.scalar(prior_query)) is not None:
        return replay(prior)
    lock_request(db, request_id)
    if request.status == RequestState.CLOSED:
        raise DomainError(409, "Request is closed")
    validate(db, request, body.investigation_id, body.details, body.evidence_ids)
    action = MaintenanceAction(**content, request_id=request_id, proposed_by=user.id,
                               idempotency_key=key, status="proposed", revision=1)
    db.add(action)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if (prior := db.scalar(prior_query)) is not None:
            return replay(prior)
        raise DomainError(409, "Proposal conflicts with existing records") from None
    record_event(db, request_id, "action.proposed", user, action.id, action_kind=action.kind, revision=1,
                 details=action.details, evidence_ids=action.evidence_ids)
    db.commit()
    return action, True


def revise(db: Session, user: User, action_id: UUID, body: ActionRevision) -> MaintenanceAction:
    action, prop = get_action(db, user, action_id, lock=True)
    if authority(db, user, prop) is None:
        deny(db, user, action, 403, "unauthorized_revision", "Owner or assigned team staff required")
    if body.details.kind != action.kind:
        raise DomainError(422, "Action kind cannot change; propose a new action")
    details = body.details.model_dump(mode="json")
    if body.expected_revision == action.revision - 1 and (details, body.rationale, body.evidence_ids) == (
            action.details, action.rationale, action.evidence_ids):
        return action  # Retried revision already applied.
    if body.expected_revision != action.revision:
        deny(db, user, action, 409, "stale_revision", "Action changed; reload the current revision")
    if action.status not in REVISABLE:
        deny(db, user, action, 409, "not_revisable", "Action can no longer be changed")
    request = db.get(MaintenanceRequest, action.request_id)
    validate(db, request, action.investigation_id, body.details, body.evidence_ids)
    previous = action.status
    action.details, action.rationale, action.evidence_ids = details, body.rationale, body.evidence_ids
    action.revision += 1
    action.status = "proposed"
    db.flush()
    record_event(db, action.request_id, "action.revised", user, action.id, revision=action.revision, details=details)
    if previous == "approved":
        record_event(db, action.request_id, "action.approval_invalidated", user, action.id,
                     revision=action.revision - 1, reason="details_changed")
    db.commit()
    return action


def decide(db: Session, user: User, action_id: UUID, body: DecisionCreate) -> MaintenanceAction:
    action, prop = get_action(db, user, action_id, lock=True)
    role = permitted(db, user, prop, action)
    if role is None:
        deny(db, user, action, 403, "unauthorized_decision", f"Not permitted to decide {action.kind}")
    if (body.revision, body.details_hash) != (action.revision, action.details_hash):
        deny(db, user, action, 409, "stale_decision", "Action changed; review the current revision")
    existing = db.scalar(select(ActionDecision).where(ActionDecision.action_id == action.id,
                                                     ActionDecision.revision == action.revision))
    if existing is not None:
        if existing.decision == body.decision:
            return action
        deny(db, user, action, 409, "already_decided", "This revision already has a decision")
    if action.status != "proposed":
        deny(db, user, action, 409, "not_pending", "Action is not awaiting a decision")
    decided_at = now()
    db.add(ActionDecision(action_id=action.id, revision=action.revision, details_hash=action.details_hash,
                          decision=body.decision, decided_by=user.id, authority=role, reason=body.reason,
                          decided_at=decided_at, expires_at=decided_at + APPROVAL_LIFETIME))
    db.flush()
    action.status = body.decision
    record_event(db, action.request_id, "action." + body.decision, user, action.id,
                 revision=action.revision, authority=role, reason=body.reason)
    db.commit()
    return action


def execute(db: Session, user: User, action_id: UUID, key: UUID, executor: ActionExecutor) -> MaintenanceAction:
    action, prop = get_action(db, user, action_id, lock=True)
    if action.execution_key == key or db.scalar(select(TimelineEvent.id).where(
            TimelineEvent.action_id == action.id, TimelineEvent.kind == "action.execution_started",
            TimelineEvent.details["key"].astext == str(key))) is not None:
        return action  # Replayed request: report the outcome, never execute again.
    if permitted(db, user, prop, action) is None:
        deny(db, user, action, 403, "unauthorized_execution", f"Not permitted to execute {action.kind}")
    if action.status == "executed":
        deny(db, user, action, 409, "already_executed", "Action already executed")
    if action.status == "executing":
        deny(db, user, action, 409, "execution_in_progress", "Execution in progress or outcome unknown")
    if action.status not in ("approved", "failed"):
        deny(db, user, action, 409, "not_approved", "Action has no current approval")
    request = db.get(MaintenanceRequest, action.request_id)
    if request.status == RequestState.CLOSED:
        deny(db, user, action, 409, "request_closed", "Request is closed")
    approval = db.scalar(select(ActionDecision).where(
        ActionDecision.action_id == action.id, ActionDecision.revision == action.revision,
        ActionDecision.details_hash == action.details_hash, ActionDecision.decision == "approved"))
    if approval is None:
        deny(db, user, action, 409, "not_approved", "Action has no current approval")
    if approval.expires_at <= now():
        deny(db, user, action, 409, "approval_expired", "Approval expired; request a new decision")
    approver = db.get(User, approval.decided_by)
    if not approver.active or permitted(db, approver, prop, action) is None:
        deny(db, user, action, 409, "approver_lost_authority", "Approver no longer holds authority")

    action.status, action.execution_key = "executing", key
    record_event(db, action.request_id, "action.execution_started", user, action.id,
                 revision=action.revision, key=str(key), approval_id=str(approval.id))
    db.commit()
    vendor_id = action.details.get("vendor_id")
    vendor = db.get(Vendor, UUID(vendor_id)) if vendor_id else None
    lock_request(db, action.request_id)
    try:
        if action.kind == "close_request":
            request.status = RequestState.CLOSED
            db.flush()  # The request trigger requires this action to still be executing.
            result = {"mode": "internal", "request_status": "closed"}
            record_event(db, request.id, "request.closed", user, action.id, resolution=action.details["resolution"])
        else:
            result = dict(executor.execute(action, vendor, key))
    except Exception:
        # Never persist provider messages; they may contain credentials or personal data.
        db.rollback()
        lock_request(db, action.request_id)
        action = db.get(MaintenanceAction, action_id, with_for_update=True, populate_existing=True)
        action.status, action.result = "failed", {"error_code": "execution_failed", "retryable": True}
        record_event(db, action.request_id, "action.execution_failed", user, action.id, key=str(key))
        db.commit()
        return action
    action.status, action.result = "executed", result
    record_event(db, action.request_id, "action.executed", user, action.id, key=str(key), result=result)
    db.commit()
    return action


def request_actions(db: Session, user: User, request_id: UUID) -> list[MaintenanceAction]:
    request = get_request(db, user, request_id)
    managed_property(db, user, request.property_id)
    return list(db.scalars(select(MaintenanceAction).where(MaintenanceAction.request_id == request_id)
                           .order_by(MaintenanceAction.created_at, MaintenanceAction.id)))


def timeline(db: Session, user: User, request_id: UUID, after: int = 0, limit: int = 200) -> list[dict]:
    request = get_request(db, user, request_id)
    managed_property(db, user, request.property_id)
    events = db.scalars(select(TimelineEvent).where(TimelineEvent.request_id == request_id,
                        TimelineEvent.sequence > after).order_by(TimelineEvent.sequence).limit(limit))
    return [{"sequence": e.sequence, "kind": e.kind, "at": e.at.isoformat(),
             "actor_id": str(e.actor_id) if e.actor_id else None, "actor_role": e.actor_role,
             "action_id": str(e.action_id) if e.action_id else None, "details": e.details} for e in events]
