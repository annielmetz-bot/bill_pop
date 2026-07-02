"""Configuration tables — the coding rules engine as *data, not logic*.

Payer + BillingCode + PayerCodeRule + DocumentationRequirement. PayerCodeRule
is versioned by effective_date so an old claim still references the rule that
was live when the service happened — this is the table NM Medicaid Advisory
Board changes land in through 2026–2027.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import str_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Modality, PayerType, Phase


class Payer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payer"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[PayerType] = mapped_column(str_enum(PayerType), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)

    code_rules: Mapped[list["PayerCodeRule"]] = relationship(back_populates="payer")


class BillingCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A CPT/HCPCS code, tied to the phase it bills for."""

    __tablename__ = "billing_code"
    __table_args__ = (UniqueConstraint("code", name="uq_billing_code_code"),)

    code: Mapped[str] = mapped_column(String(16), nullable=False)  # CPT / HCPCS
    phase: Mapped[Phase] = mapped_column(str_enum(Phase), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Which modalities this code may apply to (e.g. ["psilocybin"]).
    modality: Mapped[Modality] = mapped_column(
        str_enum(Modality), nullable=False, default=Modality.PSILOCYBIN
    )

    code_rules: Mapped[list["PayerCodeRule"]] = relationship(
        back_populates="billing_code"
    )


class PayerCodeRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A payer's coverage of a code for a date range. Versioned by effective_date.

    ``end_date`` NULL means currently in effect. Supersede a rule by setting its
    end_date and inserting a new row — never mutate a rule an old claim relied on.
    """

    __tablename__ = "payer_code_rule"

    payer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    billing_code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_code.id", ondelete="CASCADE"), nullable=False, index=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    payer: Mapped["Payer"] = relationship(back_populates="code_rules")
    billing_code: Mapped["BillingCode"] = relationship(back_populates="code_rules")
    documentation_requirements: Mapped[list["DocumentationRequirement"]] = relationship(
        back_populates="payer_code_rule"
    )


class DocumentationRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What documentation a PhaseRecord needs before a code is billable.

    Used to validate a PhaseRecord is ready to code, and to flag Phase 3B gaps
    (vitals, licensed-clinician signature, time-in-session) rather than silently
    under-coding them.
    """

    __tablename__ = "documentation_requirement"

    payer_code_rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payer_code_rule.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    required_field: Mapped[str] = mapped_column(String(128), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    payer_code_rule: Mapped["PayerCodeRule"] = relationship(
        back_populates="documentation_requirements"
    )
