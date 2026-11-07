"""Shared team queue, incident grouping and coordinator assignment.

Linking only sets a request's incident reference; the database keeps the original
complaint immutable. Owners and team coordinators manage incidents; members cannot.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from property_rescue.actions import authority
from property_rescue.models import (Incident, Investigation, MaintenanceAction, MaintenanceRequest,
                                   Membership, Property, RequestState, User)
from property_rescue.service import (DomainError, lock_request, managed_property, record_event,
                                     request_query, visible_property_ids)


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    property_id: UUID
    title: str = Field(min_length=1, max_length=200)
    coordinator_id: UUID
    request_ids: list[UUID] = Field(min_length=1, max_length=50)


class CoordinatorAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coordinator_id: UUID


def request_row(r: MaintenanceRequest) -> dict:
    return {"id": str(r.id), "property_id": str(r.property_id), "tenant_id": str(r.tenant_id),
            "incident_id": str(r.incident_id) if r.incident_id else None, "title": r.title,
            "description": r.description, "category": r.category, "status": r.status,
            "created_at": r.created_at.isoformat()}


def view(db: Session, incident: Incident) -> dict:
    coordinator = db.get(User, incident.coordinator_id)
    requests = db.scalars(select(MaintenanceRequest).where(MaintenanceRequest.incident_id == incident.id)
                          .order_by(MaintenanceRequest.created_at, MaintenanceRequest.id))
    return {"id": str(incident.id), "property_id": str(incident.property_id), "team_id": str(incident.team_id),
            "property_name": db.get(Property, incident.property_id).name, "title": incident.title,
            "status": incident.status, "coordinator": {"id": str(coordinator.id), "name": coordinator.name},
            "requests": [request_row(r) for r in requests]}


def require_manager(db: Session, user: User, prop: Property) -> None:
    if prop.team_id is None:
        raise DomainError(422, "Incidents group requests on team-managed properties")
    if authority(db, user, prop) not in ("owner", "coordinator"):
        raise DomainError(403, "Owner or team coordinator required")


def require_coordinator(db: Session, prop: Property, coordinator_id: UUID) -> None:
    membership = db.get(Membership, (prop.team_id, coordinator_id))
    if membership is None or membership.role != "coordinator":
        raise DomainError(422, "Coordinator must be a coordinator on this property's team")


def get_incident(db: Session, user: User, incident_id: UUID) -> tuple[Incident, Property]:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise DomainError(404, "Incident not found")
    return incident, managed_property(db, user, incident.property_id)


def incidents(db: Session, user: User) -> list[Incident]:
    return list(db.scalars(select(Incident).where(Incident.property_id.in_(visible_property_ids(user, manage=True)))
                           .order_by(Incident.title, Incident.id)))


def locked_requests(db: Session, request_ids) -> list[MaintenanceRequest]:
    # Sorted request locks first, matching every other writer's lock order.
    for request_id in sorted(set(request_ids)):
        lock_request(db, request_id)
    return list(db.scalars(select(MaintenanceRequest).where(MaintenanceRequest.id.in_(request_ids))
                           .execution_options(populate_existing=True)))


def attach(db: Session, user: User, incident: Incident, request: MaintenanceRequest) -> None:
    if request.property_id != incident.property_id:
        raise DomainError(422, "Request belongs to a different property")
    if request.incident_id not in (None, incident.id):
        raise DomainError(409, "Request is linked to another incident; unlink it first")
    if request.status == RequestState.CLOSED:
        raise DomainError(409, "Closed requests cannot be linked")
    if request.incident_id is None:
        request.incident_id = incident.id
        db.flush()
        record_event(db, request.id, "incident.linked", user, incident_id=str(incident.id), title=incident.title)


def create(db: Session, user: User, body: IncidentCreate, key: UUID) -> tuple[Incident, bool]:
    prop = managed_property(db, user, body.property_id)
    require_manager(db, user, prop)
    prior = db.scalar(select(Incident).where(Incident.property_id == prop.id, Incident.idempotency_key == key))
    if prior is not None:
        if (prior.title, prior.coordinator_id) != (body.title, body.coordinator_id):
            raise DomainError(409, "Idempotency key already used for a different incident")
        return prior, False
    require_coordinator(db, prop, body.coordinator_id)
    requests = locked_requests(db, body.request_ids)
    visible = set(db.scalars(request_query(user).where(MaintenanceRequest.id.in_(body.request_ids))
                             .with_only_columns(MaintenanceRequest.id)))
    if len(requests) != len(set(body.request_ids)) or visible != {r.id for r in requests}:
        raise DomainError(404, "Request not found")
    incident = Incident(property_id=prop.id, team_id=prop.team_id, coordinator_id=body.coordinator_id,
                        title=body.title, status="open", idempotency_key=key)
    db.add(incident)
    db.flush()
    for request in sorted(requests, key=lambda r: r.id):
        attach(db, user, incident, request)
    db.commit()
    return incident, True


def link(db: Session, user: User, incident_id: UUID, request_id: UUID) -> Incident:
    incident, prop = get_incident(db, user, incident_id)
    require_manager(db, user, prop)
    requests = locked_requests(db, [request_id])
    if not requests or db.scalar(request_query(user).where(MaintenanceRequest.id == request_id)) is None:
        raise DomainError(404, "Request not found")
    attach(db, user, incident, requests[0])
    db.commit()
    return incident


def unlink(db: Session, user: User, incident_id: UUID, request_id: UUID) -> Incident:
    incident, prop = get_incident(db, user, incident_id)
    require_manager(db, user, prop)
    requests = locked_requests(db, [request_id])
    if not requests or requests[0].incident_id != incident.id:
        raise DomainError(404, "Request is not linked to this incident")
    requests[0].incident_id = None
    db.flush()
    record_event(db, request_id, "incident.unlinked", user, incident_id=str(incident.id))
    db.commit()
    return incident


def assign(db: Session, user: User, incident_id: UUID, body: CoordinatorAssignment) -> Incident:
    incident, prop = get_incident(db, user, incident_id)
    require_manager(db, user, prop)
    require_coordinator(db, prop, body.coordinator_id)
    linked = db.scalars(select(MaintenanceRequest.id).where(MaintenanceRequest.incident_id == incident.id)).all()
    locked_requests(db, linked)
    incident = db.get(Incident, incident_id, with_for_update=True, populate_existing=True)
    if incident.coordinator_id == body.coordinator_id:
        return incident
    previous, incident.coordinator_id = incident.coordinator_id, body.coordinator_id
    db.flush()
    for request_id in sorted(linked):
        # Approvals by the previous coordinator stop being executable (approver_lost_authority).
        record_event(db, request_id, "incident.coordinator_assigned", user, incident_id=str(incident.id),
                     previous=str(previous), coordinator=str(body.coordinator_id))
    db.commit()
    return incident


def queue(db: Session, user: User, status: str | None, limit: int, offset: int) -> list[dict]:
    """Shared operations queue: each original request with incident, investigation and action status."""
    query = request_query(user)
    if user.role == "tenant":
        raise DomainError(403, "Management access required")
    if status:
        query = query.where(MaintenanceRequest.status == status)
    requests = db.scalars(query.order_by(MaintenanceRequest.created_at.desc(), MaintenanceRequest.id)
                          .limit(limit).offset(offset)).all()
    ids = [r.id for r in requests]
    props = {p.id: p for p in db.scalars(select(Property).where(Property.id.in_({r.property_id for r in requests})))}
    tenants = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.tenant_id for r in requests})))}
    linked = {i.id: i for i in db.scalars(select(Incident).where(Incident.id.in_({r.incident_id for r in requests if r.incident_id})))}
    coordinators = {u.id: u for u in db.scalars(select(User).where(User.id.in_({i.coordinator_id for i in linked.values()})))}
    latest = {}
    for run in db.scalars(select(Investigation).where(Investigation.request_id.in_(ids)).order_by(Investigation.created_at)):
        latest[run.request_id] = run
    counts: dict = {}
    for request_id, state, count in db.execute(select(MaintenanceAction.request_id, MaintenanceAction.status, func.count())
                                               .where(MaintenanceAction.request_id.in_(ids))
                                               .group_by(MaintenanceAction.request_id, MaintenanceAction.status)):
        counts.setdefault(request_id, {})[state] = count
    rows = []
    for r in requests:
        prop, incident, run = props[r.property_id], linked.get(r.incident_id), latest.get(r.id)
        rows.append({
            "request": request_row(r), "tenant_name": tenants[r.tenant_id].name,
            "property": {"id": str(prop.id), "name": prop.name, "team_id": str(prop.team_id) if prop.team_id else None},
            "incident": None if incident is None else {
                "id": str(incident.id), "title": incident.title,
                "coordinator": {"id": str(incident.coordinator_id), "name": coordinators[incident.coordinator_id].name}},
            "investigation": None if run is None else {"id": str(run.id), "status": run.status},
            "actions": counts.get(r.id, {}),
        })
    return rows
