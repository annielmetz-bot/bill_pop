"""API schemas for the Eligibility layer."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import EligibilityStatus


class EligibilityCheckCreate(BaseModel):
    client_id: uuid.UUID
    # X12 service type code; 30 = general health benefit plan coverage.
    service_type_code: str = "30"


class EligibilityCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    payer_id: uuid.UUID | None
    service_type_code: str
    subscriber_id: str
    status: EligibilityStatus
    checked_at: datetime
    gateway: str
    coverage: list[dict[str, Any]]
