"""Eligibility check results.

One row per 270/271 inquiry, retaining the raw request/response for audit (every
claim touch is logged per HIPAA) and the parsed benefits for downstream use.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import str_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EligibilityStatus


class EligibilityCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eligibility_check"

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    service_type_code: Mapped[str] = mapped_column(String(16), nullable=False)
    subscriber_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[EligibilityStatus] = mapped_column(
        str_enum(EligibilityStatus), nullable=False, index=True
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    gateway: Mapped[str] = mapped_column(String(32), nullable=False)
    # Parsed benefit lines (list) + raw wire payloads, for audit / debugging.
    coverage: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_request: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    client: Mapped["Client"] = relationship()  # noqa: F821
    payer: Mapped["Payer | None"] = relationship()  # noqa: F821
