"""Vendor-agnostic domain objects for a 270 request / 271 response.

These are the internal representation the whole app speaks. A gateway adapter is
responsible for translating between these objects and its clearinghouse's wire
format (X12 5010 270/271, or a vendor JSON-over-X12 API).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import EligibilityStatus


class Subscriber(BaseModel):
    """The insured party we're checking coverage for."""

    member_id: str
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None  # ISO date; kept as string at the EDI edge


class Provider(BaseModel):
    """The requesting provider (clinic / facilitator)."""

    npi: str | None = None
    name: str | None = None


class EligibilityRequest(BaseModel):
    """Inputs to a 270 inquiry."""

    payer_name: str
    payer_id: str | None = None  # clearinghouse payer id, when known
    subscriber: Subscriber
    provider: Provider = Field(default_factory=Provider)
    # X12 service type code (270 EQ01). 30 = "Health Benefit Plan Coverage";
    # behavioral-health/PAT-specific codes are provisional pending NM guidance.
    service_type_code: str = "30"


class BenefitLine(BaseModel):
    """One coverage/benefit detail (a 271 2110 EB loop, simplified)."""

    service_type_code: str
    service_type: str
    coverage: str  # e.g. "active", "copay", "deductible"
    in_network: bool | None = None
    copay: Decimal | None = None
    coinsurance_percent: Decimal | None = None
    deductible_remaining: Decimal | None = None
    notes: str | None = None


class EligibilityResponse(BaseModel):
    """Parsed result of a 271 response."""

    status: EligibilityStatus
    plan_name: str | None = None
    benefits: list[BenefitLine] = Field(default_factory=list)
    # The raw wire payload (X12 string or vendor JSON) for audit / debugging.
    raw: str | None = None
