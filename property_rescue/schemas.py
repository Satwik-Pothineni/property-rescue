"""Explicit API contracts, independent of database credentials and internal fields."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    property_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: Literal["plumbing", "electrical", "heating", "general"]


class UserView(Output):
    id: UUID
    name: str
    role: str


class PropertyView(Output):
    id: UUID
    name: str
    address: str
    owner_id: UUID
    team_id: UUID | None


class RequestView(Output):
    id: UUID
    property_id: UUID
    tenant_id: UUID
    incident_id: UUID | None
    title: str
    description: str
    category: str
    status: str
    created_at: datetime


class HistoryView(Output):
    id: UUID
    property_id: UUID
    vendor_id: UUID | None
    performed_on: date
    summary: str
    cost: Decimal


class WarrantyView(Output):
    id: UUID
    asset: str
    provider: str
    starts_on: date
    ends_on: date
    terms: str


class VendorView(Output):
    id: UUID
    name: str
    specialty: str
    contact_email: str


class IncidentView(Output):
    id: UUID
    property_id: UUID
    team_id: UUID
    coordinator_id: UUID
    title: str
    status: str
