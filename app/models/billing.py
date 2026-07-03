"""Billing entities.

A ``Charge`` is one priced billable line, derived from a ``READY_TO_CODE``
PhaseRecord by the coding service. A ``Claim`` groups an episode's coded charges
for one payer and carries the submission lifecycle (assemble → scrub → submit).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import str_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ChargeStatus, ClaimStatus, RemittanceStatus


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
    # Set when the charge is assembled onto a claim.
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("claim.id", ondelete="SET NULL"), nullable=True, index=True
    )

    phase_record: Mapped["PhaseRecord"] = relationship()  # noqa: F821
    billing_code: Mapped["BillingCode | None"] = relationship()  # noqa: F821
    payer_code_rule: Mapped["PayerCodeRule | None"] = relationship()  # noqa: F821
    claim: Mapped["Claim | None"] = relationship(back_populates="charges")


class Claim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "claim"

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    episode_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("episode_of_care.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ClaimStatus] = mapped_column(
        str_enum(ClaimStatus), nullable=False, default=ClaimStatus.DRAFT, index=True
    )
    control_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_charge: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    # Reasons the last scrub failed; empty once the claim is clean.
    scrub_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gateway: Mapped[str | None] = mapped_column(String(32), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The generated 837 and the clearinghouse acknowledgment, for audit.
    raw_837: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    charges: Mapped[list["Charge"]] = relationship(back_populates="claim")
    remittance: Mapped["Remittance | None"] = relationship(
        back_populates="claim", uselist=False
    )


class Remittance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Posted 835 remittance for a claim: what the payer actually paid."""

    __tablename__ = "remittance"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    payer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RemittanceStatus] = mapped_column(
        str_enum(RemittanceStatus), nullable=False, index=True
    )
    charged_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Paid short of the contracted rate (0 when paid in full). Flagged for follow-up.
    underpaid_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    adjustments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    denial_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_835: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    claim: Mapped["Claim"] = relationship(back_populates="remittance")
