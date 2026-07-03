"""API schemas for claims assembly, scrub, and submission."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ClaimStatus


class ClaimCreate(BaseModel):
    episode_id: uuid.UUID


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    payer_id: uuid.UUID | None
    episode_id: uuid.UUID
    status: ClaimStatus
    control_number: str | None
    total_charge: Decimal
    scrub_errors: list[str]
    submitted_at: datetime | None


class ScrubResult(BaseModel):
    claim_id: uuid.UUID
    status: ClaimStatus
    errors: list[str]
