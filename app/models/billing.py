"""Billing entities — charges (this milestone), then claims and remittance.

A ``Charge`` is one priced billable line, derived from a ``READY_TO_CODE``
PhaseRecord by the coding service. It captures which code was chosen, which
payer rule priced it (for audit and rate comparison later), and the amount.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import str_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ChargeStatus


class Charge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "charge"

    phase_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("phase_record.id", ondelete="CASCADE"), nullable=False, index=True
    )
    billing_code_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing_code.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The versioned rule that priced this charge — kept for audit and for later
    # underpayment comparison against the contracted rate.
    payer_code_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer_code_rule.id", ondelete="SET NULL"), nullable=True, index=True
    )
    units: Mapped[int] = mapped_column(nullable=False, default=1)
    modifiers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    diagnosis_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    charge_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[ChargeStatus] = mapped_column(
        str_enum(ChargeStatus), nullable=False, default=ChargeStatus.NEEDS_REVIEW
    )
    # NOTE: ``claim_id`` (link to the assembled claim) is added in Milestone C2,
    # once the ``claim`` table exists.

    phase_record: Mapped["PhaseRecord"] = relationship()  # noqa: F821
    billing_code: Mapped["BillingCode | None"] = relationship()  # noqa: F821
    payer_code_rule: Mapped["PayerCodeRule | None"] = relationship()  # noqa: F821
