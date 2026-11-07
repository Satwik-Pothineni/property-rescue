"""Authorization, creation and safe acknowledgement in a transaction boundary."""

from hashlib import sha256
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from property_rescue.models import (Credential, Incident, MaintenanceHistory,
    MaintenanceRequest, Membership, Property, RequestState, Tenancy, TimelineEvent, User, Vendor, Warranty)
from property_rescue.schemas import RequestCreate


class DomainError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def authenticate(db: Session, token: str) -> User:
    if not 32 <= len(token) <= 256:
        raise DomainError(401, "Invalid credentials")
    user = db.scalar(select(User).join(Credential).where(
        Credential.token_hash == token_hash(token), User.active.is_(True)))
    if user is None:
        raise DomainError(401, "Invalid credentials")
    return user


def lock_request(db: Session, request_id: UUID) -> None:
    """Writers lock the request row before its actions or investigations, avoiding deadlocks."""
    db.execute(select(MaintenanceRequest.id).where(MaintenanceRequest.id == request_id).with_for_update())


def record_event(db: Session, request_id: UUID, kind: str, actor: User | None,
                 action_id: UUID | None = None, **details) -> TimelineEvent:
    """Append to the request timeline. The request row lock keeps sequences gapless and ordered."""
    lock_request(db, request_id)
    sequence = 1 + db.scalar(select(func.coalesce(func.max(TimelineEvent.sequence), 0))
                             .where(TimelineEvent.request_id == request_id))
    event = TimelineEvent(request_id=request_id, sequence=sequence, kind=kind, action_id=action_id,
                          actor_id=actor.id if actor else None, actor_role=actor.role if actor else None,
                          details=details)
    db.add(event)
    db.flush()
    return event


def visible_property_ids(user: User, *, manage: bool = False) -> Select:
    if user.role == "tenant":
        if manage:
            raise DomainError(403, "Management access required")
        return select(Tenancy.property_id).where(Tenancy.tenant_id == user.id, Tenancy.active.is_(True))
    if user.role == "owner":
        return select(Property.id).where(Property.owner_id == user.id)
    return select(Property.id).where(Property.team_id.in_(
        select(Membership.team_id).where(Membership.user_id == user.id)))


def properties(db: Session, user: User) -> list[Property]:
    return list(db.scalars(select(Property).where(Property.id.in_(visible_property_ids(user))).order_by(Property.id)))


def managed_property(db: Session, user: User, property_id: UUID) -> Property:
    prop = db.scalar(select(Property).where(Property.id == property_id,
                    Property.id.in_(visible_property_ids(user, manage=True))))
    if prop is None:
        raise DomainError(404, "Property not found")
    return prop


def request_query(user: User) -> Select:
    query = select(MaintenanceRequest)
    if user.role == "tenant":
        return query.where(MaintenanceRequest.tenant_id == user.id)
    return query.where(MaintenanceRequest.property_id.in_(visible_property_ids(user, manage=True)))


def requests(db: Session, user: User, limit: int, offset: int) -> list[MaintenanceRequest]:
    return list(db.scalars(request_query(user).order_by(MaintenanceRequest.created_at, MaintenanceRequest.id)
                           .limit(limit).offset(offset)))


def get_request(db: Session, user: User, request_id: UUID, *, lock: bool = False) -> MaintenanceRequest:
    query = request_query(user).where(MaintenanceRequest.id == request_id)
    record = db.scalar(query.with_for_update() if lock else query)
    if record is None:
        raise DomainError(404, "Request not found")
    return record


def create_request(db: Session, user: User, body: RequestCreate, key: UUID) -> tuple[MaintenanceRequest, bool]:
    if user.role != "tenant":
        raise DomainError(403, "Only tenants may submit requests")
    prior_query = select(MaintenanceRequest).where(MaintenanceRequest.tenant_id == user.id,
                                                 MaintenanceRequest.idempotency_key == key)

    def replay(prior: MaintenanceRequest) -> tuple[MaintenanceRequest, bool]:
        if any(getattr(prior, name) != value for name, value in body.model_dump().items()):
            raise DomainError(409, "Idempotency key already used for a different request")
        return prior, False

    prior = db.scalar(prior_query)
    if prior is not None:
        return replay(prior)
    tenancy = db.scalar(select(Tenancy).where(Tenancy.property_id == body.property_id,
                        Tenancy.tenant_id == user.id, Tenancy.active.is_(True)).with_for_update())
    if tenancy is None:
        raise DomainError(404, "Active tenancy not found")
    record = MaintenanceRequest(**body.model_dump(), tenant_id=user.id,
                                idempotency_key=key, status=RequestState.SUBMITTED)
    db.add(record)
    try:
        db.flush()
        record_event(db, record.id, "request.submitted", user, title=record.title, category=record.category)
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.scalar(prior_query)
        if prior is not None:
            return replay(prior)
        raise DomainError(409, "Request conflicts with existing records") from None
    db.refresh(record)
    return record, True


def acknowledge(db: Session, user: User, request_id: UUID) -> MaintenanceRequest:
    if user.role == "tenant":
        raise DomainError(403, "Owner or coordinator required")
    record = get_request(db, user, request_id, lock=True)
    prop = managed_property(db, user, record.property_id)
    if user.role == "staff":
        membership = db.get(Membership, (prop.team_id, user.id))
        if membership is None or membership.role != "coordinator":
            raise DomainError(403, "Owner or coordinator required")
    if record.status == RequestState.ACKNOWLEDGED:
        return record
    if record.status != RequestState.SUBMITTED:
        raise DomainError(409, "Invalid request state transition")
    record.status = RequestState.ACKNOWLEDGED
    record_event(db, record.id, "request.acknowledged", user)
    db.commit()
    db.refresh(record)
    return record


def property_records(db: Session, user: User, property_id: UUID,
                     model: type[MaintenanceHistory] | type[Warranty] | type[Vendor] | type[Incident]) -> list:
    managed_property(db, user, property_id)
    return list(db.scalars(select(model).where(model.property_id == property_id).order_by(model.id)))
