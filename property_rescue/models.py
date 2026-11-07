"""Maintenance records and relational boundaries. Actions execute only via approved services."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, FetchedValue, ForeignKey,
                        ForeignKeyConstraint, Integer, Numeric, String, Text, UniqueConstraint, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB


class RequestState(StrEnum):
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('tenant', 'owner', 'staff')", name="user_role"),
        UniqueConstraint("id", "role"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Credential(Base):
    __tablename__ = "credentials"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (CheckConstraint("coordinator_spend_limit >= 0", name="team_spend_limit"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    # USD a coordinator may approve per spending action; NULL means owner-only spending.
    coordinator_spend_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "user_role"], ["users.id", "users.role"]),
        CheckConstraint("user_role = 'staff'", name="member_is_staff"),
        CheckConstraint("role IN ('coordinator', 'member')", name="membership_role"),
        UniqueConstraint("team_id", "user_id", "role"),
    )
    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_role: Mapped[str] = mapped_column(String(16), default="staff")
    role: Mapped[str] = mapped_column(String(16))


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "owner_role"], ["users.id", "users.role"]),
        CheckConstraint("owner_role = 'owner'", name="property_owner_role"),
        UniqueConstraint("id", "team_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(250))
    owner_id: Mapped[UUID] = mapped_column(index=True)
    owner_role: Mapped[str] = mapped_column(String(16), default="owner")
    team_id: Mapped[UUID | None] = mapped_column(ForeignKey("teams.id"), index=True)


class Tenancy(Base):
    __tablename__ = "tenancies"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "tenant_role"], ["users.id", "users.role"]),
        CheckConstraint("tenant_role = 'tenant'", name="tenancy_tenant_role"),
    )
    property_id: Mapped[UUID] = mapped_column(ForeignKey("properties.id"), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_role: Mapped[str] = mapped_column(String(16), default="tenant")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Incident(Base):
    """Coordinator-owned group of related team requests; requests keep their original content."""
    __tablename__ = "incidents"
    __table_args__ = (
        ForeignKeyConstraint(["property_id", "team_id"], ["properties.id", "properties.team_id"]),
        ForeignKeyConstraint(["team_id", "coordinator_id", "coordinator_role"],
                             ["memberships.team_id", "memberships.user_id", "memberships.role"]),
        CheckConstraint("coordinator_role = 'coordinator'", name="incident_coordinator_role"),
        CheckConstraint("status = 'open'", name="incident_status"),
        UniqueConstraint("id", "property_id"),
        UniqueConstraint("property_id", "idempotency_key", name="incident_idempotency"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    property_id: Mapped[UUID] = mapped_column()
    team_id: Mapped[UUID] = mapped_column()
    coordinator_id: Mapped[UUID] = mapped_column()
    coordinator_role: Mapped[str] = mapped_column(String(16), default="coordinator")
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="open")
    idempotency_key: Mapped[UUID | None] = mapped_column()


class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"
    __table_args__ = (
        ForeignKeyConstraint(["property_id", "tenant_id"], ["tenancies.property_id", "tenancies.tenant_id"]),
        ForeignKeyConstraint(["incident_id", "property_id"], ["incidents.id", "incidents.property_id"]),
        UniqueConstraint("tenant_id", "idempotency_key", name="request_idempotency"),
        CheckConstraint("status IN ('submitted', 'acknowledged', 'closed')", name="request_status"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="request_title"),
        CheckConstraint("length(trim(description)) BETWEEN 1 AND 5000", name="request_description"),
        CheckConstraint("category IN ('plumbing', 'electrical', 'heating', 'general')", name="request_category"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    property_id: Mapped[UUID] = mapped_column(index=True)
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    incident_id: Mapped[UUID | None] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=RequestState.SUBMITTED)
    idempotency_key: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    specialty: Mapped[str] = mapped_column(String(100))
    contact_email: Mapped[str] = mapped_column(String(200))
    # Each vendor belongs to a property directory; no global contact discovery.
    property_id: Mapped[UUID] = mapped_column(ForeignKey("properties.id"), index=True)
    __table_args__ = (UniqueConstraint("id", "property_id"),)


class MaintenanceHistory(Base):
    __tablename__ = "maintenance_history"
    __table_args__ = (
        ForeignKeyConstraint(["vendor_id", "property_id"], ["vendors.id", "vendors.property_id"]),
        CheckConstraint("cost >= 0", name="history_cost"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    property_id: Mapped[UUID] = mapped_column(ForeignKey("properties.id"), index=True)
    vendor_id: Mapped[UUID | None] = mapped_column()
    performed_on: Mapped[date] = mapped_column()
    summary: Mapped[str] = mapped_column(Text)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Warranty(Base):
    __tablename__ = "warranties"
    __table_args__ = (CheckConstraint("ends_on >= starts_on", name="warranty_dates"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    property_id: Mapped[UUID] = mapped_column(ForeignKey("properties.id"), index=True)
    asset: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100))
    starts_on: Mapped[date] = mapped_column()
    ends_on: Mapped[date] = mapped_column()
    terms: Mapped[str] = mapped_column(Text)


class PlanningEstimate(Base):
    """Fictional indicative allowance, never a vendor quote or spending approval."""
    __tablename__ = "planning_estimates"
    __table_args__ = (
        ForeignKeyConstraint(["vendor_id", "property_id"], ["vendors.id", "vendors.property_id"]),
        CheckConstraint("low >= 0 AND high >= low", name="estimate_range"),
        CheckConstraint("valid_until >= recorded_on", name="estimate_dates"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    property_id: Mapped[UUID] = mapped_column(ForeignKey("properties.id"), index=True)
    vendor_id: Mapped[UUID] = mapped_column()
    category: Mapped[str] = mapped_column(String(16))
    low: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    high: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    assumptions: Mapped[str] = mapped_column(Text)
    recorded_on: Mapped[date] = mapped_column()
    valid_until: Mapped[date] = mapped_column()


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (
        UniqueConstraint("request_id", "idempotency_key", name="investigation_idempotency"),
        UniqueConstraint("id", "request_id", name="investigation_request"),
        CheckConstraint("status IN ('collecting', 'ready_for_review', 'partial')", name="investigation_status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("maintenance_requests.id"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(24), default="collecting")
    as_of: Mapped[date] = mapped_column()
    # All values are validated structured snapshots; JSON assignments replace, not mutate.
    sections: Mapped[dict] = mapped_column(JSONB, default=dict)
    activity: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MaintenanceAction(Base):
    """A proposed consequential action. Database triggers bind status changes to decisions."""
    __tablename__ = "maintenance_actions"
    __table_args__ = (
        ForeignKeyConstraint(["investigation_id", "request_id"], ["investigations.id", "investigations.request_id"]),
        UniqueConstraint("request_id", "idempotency_key", name="action_idempotency"),
        CheckConstraint("kind IN ('contact_vendor', 'schedule_visit', 'authorize_spend', 'close_request')", name="action_kind"),
        CheckConstraint("status IN ('proposed', 'approved', 'rejected', 'executing', 'executed', 'failed')", name="action_status"),
        CheckConstraint("revision >= 1", name="action_revision"),
    )
    __mapper_args__ = {"eager_defaults": True}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("maintenance_requests.id"), index=True)
    investigation_id: Mapped[UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(24))
    details: Mapped[dict] = mapped_column(JSONB)
    rationale: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSONB)
    # Computed by trigger over details, rationale and evidence; approvals bind to it.
    details_hash: Mapped[str] = mapped_column(String(64), server_default=FetchedValue(), server_onupdate=FetchedValue())
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    proposed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[UUID] = mapped_column()
    execution_key: Mapped[UUID | None] = mapped_column()
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ActionDecision(Base):
    """Immutable approval or rejection of one exact action revision."""
    __tablename__ = "action_decisions"
    __table_args__ = (
        UniqueConstraint("action_id", "revision", name="decision_per_revision"),
        CheckConstraint("decision IN ('approved', 'rejected')", name="decision_value"),
        CheckConstraint("authority IN ('owner', 'coordinator')", name="decision_authority"),
        CheckConstraint("expires_at > decided_at", name="decision_expiry"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action_id: Mapped[UUID] = mapped_column(ForeignKey("maintenance_actions.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    details_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(16))
    decided_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    authority: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TimelineEvent(Base):
    """Append-only per-request activity; sequence is gapless and ordered per request."""
    __tablename__ = "timeline_events"
    __table_args__ = (UniqueConstraint("request_id", "sequence", name="timeline_sequence"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("maintenance_requests.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(48))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str | None] = mapped_column(String(16))
    action_id: Mapped[UUID | None] = mapped_column(ForeignKey("maintenance_actions.id"))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollaborationMessage(Base):
    """Switch agent discussion imported read-only from Mattermost; text is untrusted data."""
    __tablename__ = "collaboration_messages"
    __table_args__ = (
        ForeignKeyConstraint(["investigation_id", "request_id"], ["investigations.id", "investigations.request_id"]),
    )
    post_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(index=True)
    request_id: Mapped[UUID] = mapped_column()
    channel_id: Mapped[str] = mapped_column(String(26))
    root_post_id: Mapped[str] = mapped_column(String(26))
    sender: Mapped[str] = mapped_column(String(64))
    sender_is_bot: Mapped[bool] = mapped_column(Boolean)
    tag: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    edited: Mapped[bool] = mapped_column(Boolean)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
