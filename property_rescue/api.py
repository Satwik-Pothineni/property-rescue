"""Thin FastAPI routes. Use --factory property_rescue.api:create_app."""

from contextlib import asynccontextmanager
import asyncio
import os
from collections.abc import AsyncIterable
import time
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from property_rescue import actions, collaboration, incidents, service, investigation
from property_rescue.database import build_engine
from property_rescue.models import Incident, MaintenanceHistory, Membership, User, Vendor, Warranty
from property_rescue.schemas import (HistoryView, IncidentView, PropertyView, RequestCreate,
                                     RequestView, UserView, VendorView, WarrantyView)


def create_app(engine: Engine | None = None,
               investigation_tools: dict[str, investigation.EvidenceTool] | None = None,
               executor: actions.ActionExecutor | None = None,
               mattermost: collaboration.Collaboration | None = None) -> FastAPI:
    own_engine = engine is None
    database = engine or build_engine()
    tools = investigation.default_tools() if investigation_tools is None else investigation_tools
    executor = executor or actions.FictionalDemoExecutor()
    mattermost = mattermost or collaboration.Collaboration.from_env(os.environ)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if own_engine:
            database.dispose()

    app = FastAPI(title="Property Rescue", version="0.2.0", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    def session():
        with Session(database, expire_on_commit=False) as db:
            yield db

    def current_user(db: Annotated[Session, Depends(session)],
                     credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
        if credentials is None:
            raise service.DomainError(401, "Bearer authentication required")
        return service.authenticate(db, credentials.credentials)

    # Dependencies are local to this app, so tests can inject an isolated database.
    Db = Annotated[Session, Depends(session)]
    Actor = Annotated[User, Depends(current_user)]

    @app.exception_handler(service.DomainError)
    async def domain_error(request: Request, error: service.DomainError):
        headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else None
        return JSONResponse({"detail": error.detail}, status_code=error.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Default validation responses echo submitted fields, possibly credentials.
        return JSONResponse({"detail": [{"loc": e["loc"], "type": e["type"], "msg": e["msg"]}
                                        for e in error.errors()]}, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        return JSONResponse({"detail": "Database operation unavailable"}, status_code=503)

    @app.get("/me", response_model=UserView)
    def me(user: Actor):
        return user

    @app.get("/properties", response_model=list[PropertyView])
    def list_properties(db: Db, user: Actor):
        return service.properties(db, user)

    @app.post("/requests", response_model=RequestView, status_code=201)
    def submit(body: RequestCreate, db: Db, user: Actor, response: Response,
               idempotency_key: Annotated[UUID, Header()]):
        result, created = service.create_request(db, user, body, idempotency_key)
        response.status_code = 201 if created else 200
        return result

    @app.get("/requests", response_model=list[RequestView])
    def list_requests(db: Db, user: Actor, limit: Annotated[int, Query(ge=1, le=100)] = 50,
                      offset: Annotated[int, Query(ge=0)] = 0):
        return service.requests(db, user, limit, offset)

    @app.get("/requests/{request_id}", response_model=RequestView)
    def read_request(request_id: UUID, db: Db, user: Actor):
        return service.get_request(db, user, request_id)

    @app.put("/requests/{request_id}/acknowledgement", response_model=RequestView)
    def acknowledge(request_id: UUID, db: Db, user: Actor):
        return service.acknowledge(db, user, request_id)

    @app.get("/properties/{property_id}/history", response_model=list[HistoryView])
    def history(property_id: UUID, db: Db, user: Actor):
        return service.property_records(db, user, property_id, MaintenanceHistory)

    @app.get("/properties/{property_id}/warranties", response_model=list[WarrantyView])
    def warranties(property_id: UUID, db: Db, user: Actor):
        return service.property_records(db, user, property_id, Warranty)

    @app.get("/properties/{property_id}/vendors", response_model=list[VendorView])
    def vendors(property_id: UUID, db: Db, user: Actor):
        return service.property_records(db, user, property_id, Vendor)

    @app.get("/properties/{property_id}/incidents", response_model=list[IncidentView])
    def property_incidents(property_id: UUID, db: Db, user: Actor):
        return service.property_records(db, user, property_id, Incident)

    @app.post("/requests/{request_id}/investigations")
    def investigate(request_id: UUID, db: Db, user: Actor,
                    idempotency_key: Annotated[UUID, Header()]) -> dict:
        return investigation.view(investigation.start(db, user, request_id, idempotency_key, tools))

    @app.get("/investigations/{run_id}")
    def read_investigation(run_id: UUID, db: Db, user: Actor) -> dict:
        run = investigation.get_investigation(db, user, run_id)
        return investigation.view(run, collaboration.agent_review(db, run.id))

    @app.get("/requests/{request_id}/investigations")
    def list_investigations(request_id: UUID, db: Db, user: Actor) -> list[dict]:
        return [investigation.view(run, collaboration.agent_review(db, run.id))
                for run in investigation.request_investigations(db, user, request_id)]

    @app.get("/investigations/{run_id}/collaboration")
    def read_collaboration(run_id: UUID, db: Db, user: Actor) -> list[dict]:
        investigation.get_investigation(db, user, run_id)
        return [collaboration.message_view(m) for m in collaboration.messages(db, run_id)]

    @app.post("/investigations/{run_id}/collaboration/sync")
    def sync_collaboration(run_id: UUID, body: collaboration.SyncRequest, db: Db, user: Actor) -> list[dict]:
        return [collaboration.message_view(m) for m in collaboration.sync(db, user, run_id, body, mattermost)]

    @app.post("/investigations/{run_id}/retry")
    def retry_investigation(run_id: UUID, db: Db, user: Actor,
                           idempotency_key: Annotated[UUID, Header()]) -> dict:
        return investigation.view(investigation.retry(db, user, run_id, idempotency_key, tools))

    @app.get("/investigations/{run_id}/brief", response_class=Response)
    def investigation_brief(run_id: UUID, db: Db, user: Actor) -> Response:
        return Response(investigation.brief(investigation.get_investigation(db, user, run_id)), media_type="text/plain")

    @app.get("/queue")
    def read_queue(db: Db, user: Actor, status: Annotated[str | None, Query(pattern="^(submitted|acknowledged|closed)$")] = None,
                   limit: Annotated[int, Query(ge=1, le=200)] = 100, offset: Annotated[int, Query(ge=0)] = 0) -> list[dict]:
        return incidents.queue(db, user, status, limit, offset)

    @app.get("/properties/{property_id}/staff")
    def property_staff(property_id: UUID, db: Db, user: Actor) -> list[dict]:
        prop = service.managed_property(db, user, property_id)
        rows = db.execute(select(User, Membership.role).join(Membership, Membership.user_id == User.id)
                          .where(Membership.team_id == prop.team_id).order_by(User.name)) if prop.team_id else []
        return [{"id": str(u.id), "name": u.name, "role": role, "active": u.active} for u, role in rows]

    @app.get("/incidents")
    def list_incidents(db: Db, user: Actor) -> list[dict]:
        return [incidents.view(db, i) for i in incidents.incidents(db, user)]

    @app.post("/incidents", status_code=201)
    def create_incident(body: incidents.IncidentCreate, db: Db, user: Actor, response: Response,
                        idempotency_key: Annotated[UUID, Header()]) -> dict:
        incident, created = incidents.create(db, user, body, idempotency_key)
        response.status_code = 201 if created else 200
        return incidents.view(db, incident)

    @app.get("/incidents/{incident_id}")
    def read_incident(incident_id: UUID, db: Db, user: Actor) -> dict:
        return incidents.view(db, incidents.get_incident(db, user, incident_id)[0])

    @app.put("/incidents/{incident_id}/requests/{request_id}")
    def link_request(incident_id: UUID, request_id: UUID, db: Db, user: Actor) -> dict:
        return incidents.view(db, incidents.link(db, user, incident_id, request_id))

    @app.delete("/incidents/{incident_id}/requests/{request_id}")
    def unlink_request(incident_id: UUID, request_id: UUID, db: Db, user: Actor) -> dict:
        return incidents.view(db, incidents.unlink(db, user, incident_id, request_id))

    @app.put("/incidents/{incident_id}/coordinator")
    def assign_coordinator(incident_id: UUID, body: incidents.CoordinatorAssignment, db: Db, user: Actor) -> dict:
        return incidents.view(db, incidents.assign(db, user, incident_id, body))

    @app.post("/requests/{request_id}/actions", status_code=201)
    def propose_action(request_id: UUID, body: actions.ActionCreate, db: Db, user: Actor, response: Response,
                       idempotency_key: Annotated[UUID, Header()]) -> dict:
        action, created = actions.propose(db, user, request_id, body, idempotency_key)
        response.status_code = 201 if created else 200
        return actions.view(db, action)

    @app.get("/requests/{request_id}/actions")
    def list_actions(request_id: UUID, db: Db, user: Actor) -> list[dict]:
        return [actions.view(db, a) for a in actions.request_actions(db, user, request_id)]

    @app.get("/actions/{action_id}")
    def read_action(action_id: UUID, db: Db, user: Actor) -> dict:
        return actions.view(db, actions.get_action(db, user, action_id)[0])

    @app.put("/actions/{action_id}")
    def revise_action(action_id: UUID, body: actions.ActionRevision, db: Db, user: Actor) -> dict:
        return actions.view(db, actions.revise(db, user, action_id, body))

    @app.post("/actions/{action_id}/decision")
    def decide_action(action_id: UUID, body: actions.DecisionCreate, db: Db, user: Actor) -> dict:
        return actions.view(db, actions.decide(db, user, action_id, body))

    @app.post("/actions/{action_id}/execution")
    def execute_action(action_id: UUID, db: Db, user: Actor,
                       idempotency_key: Annotated[UUID, Header()]) -> dict:
        return actions.view(db, actions.execute(db, user, action_id, idempotency_key, executor))

    @app.get("/requests/{request_id}/timeline")
    def read_timeline(request_id: UUID, db: Db, user: Actor, after: Annotated[int, Query(ge=0)] = 0,
                      limit: Annotated[int, Query(ge=1, le=500)] = 200) -> list[dict]:
        return actions.timeline(db, user, request_id, after, limit)

    def timeline_access(request_id: UUID, db: Db, user: Actor) -> None:
        investigation.authorize(db, user, request_id)

    @app.get("/requests/{request_id}/timeline/stream", response_class=EventSourceResponse,
             dependencies=[Depends(timeline_access)])
    async def stream_timeline(request_id: UUID, request: Request,
                              credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
                              after: Annotated[int, Query(ge=0)] = 0,
                              timeout: Annotated[int, Query(ge=1, le=300)] = 300,
                              last_event_id: Annotated[int | None, Header()] = None) -> AsyncIterable[ServerSentEvent]:
        """Live owner timeline. Ends after `timeout`; EventSource reconnects with Last-Event-ID."""
        cursor = last_event_id if last_event_id is not None else after

        def poll(position: int) -> list[dict]:
            # Re-authenticate every poll so revoked tokens and lost access stop the stream.
            with Session(database) as db:
                return actions.timeline(db, service.authenticate(db, credentials.credentials), request_id, position)

        deadline = time.monotonic() + timeout
        while True:
            try:
                events = await run_in_threadpool(poll, cursor)
            except service.DomainError:
                return  # Access revoked mid-stream: stop without revealing further events.
            for event in events:
                cursor = event["sequence"]
                yield ServerSentEvent(data=event, id=str(cursor), event=event["kind"])
            if time.monotonic() >= deadline or await request.is_disconnected():
                return
            await asyncio.sleep(1)

    return app
