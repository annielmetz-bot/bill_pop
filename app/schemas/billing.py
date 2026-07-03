"""API schemas for coding & charge capture."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ChargeStatus


class ChargeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phase_record_id: uuid.UUID
    billing_code_id: uuid.UUID | None
    payer_code_rule_id: uuid.UUID | None
    units: int
    diagnosis_codes: list[str]
    charge_amount: Decimal | None
    status: ChargeStatus


class CodingResultOut(BaseModel):
    episode_id: uuid.UUID
    coded: int
    needs_review: int
    skipped: int
    charge_ids: list[uuid.UUID]
