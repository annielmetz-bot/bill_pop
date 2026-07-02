"""Core clinical entities.

Clinic → Client / Clinician → EpisodeOfCare → PhaseRecord → DocumentationRecord.

PhaseRecord is the core billable unit; DocumentationRecord is what gets checked
against DocumentationRequirement before a phase is codeable.
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import str_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    BaaStatus,
    Modality,
    Phase,
    PhaseStatus,
    SourceSystem,
)


class Clinic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clinic"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_system: Mapped[SourceSystem] = mapped_column(
        str_enum(SourceSystem), nullable=False
    )
    # Every clinic moving PHI needs a signed BAA before go-live (HIPAA).
    baa_status: Mapped[BaaStatus] = mapped_column(
        str_enum(BaaStatus), nullable=False, default=BaaStatus.PENDING
    )
    baa_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[str] = mapped_column(String(2), nullable=False)  # "NM" first

    clients: Mapped[list["Client"]] = relationship(back_populates="clinic")
    clinicians: Mapped[list["Clinician"]] = relationship(back_populates="clinic")


class Client(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The patient. Contains PHI — encrypt at rest at the storage layer.

    Demographics are held in a JSONB blob rather than fanned out into columns:
    Month 1 does not yet know the exact fields Homecoming/Althea exports carry,
    and this keeps ``demographics`` as staging-shaped data until intake scoping
    lands.
    """

    __tablename__ = "client"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinic.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    demographics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    payer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer.id", ondelete="SET NULL"), nullable=True, index=True
    )

    clinic: Mapped["Clinic"] = relationship(back_populates="clients")
    payer: Mapped["Payer | None"] = relationship()  # noqa: F821
    episodes: Mapped[list["EpisodeOfCare"]] = relationship(back_populates="client")


class Clinician(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clinician"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinic.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    npi: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)

    clinic: Mapped["Clinic"] = relationship(back_populates="clinicians")


class EpisodeOfCare(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Groups the phases for one course of treatment."""

    __tablename__ = "episode_of_care"

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modality: Mapped[Modality] = mapped_column(
        str_enum(Modality), nullable=False, default=Modality.PSILOCYBIN
    )
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    client: Mapped["Client"] = relationship(back_populates="episodes")
    phase_records: Mapped[list["PhaseRecord"]] = relationship(
        back_populates="episode"
    )


class PhaseRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The core billable unit — one phase of care within an episode."""

    __tablename__ = "phase_record"

    episode_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("episode_of_care.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinician_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clinician.id", ondelete="SET NULL"), nullable=True, index=True
    )
    phase: Mapped[Phase] = mapped_column(str_enum(Phase), nullable=False, index=True)
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    status: Mapped[PhaseStatus] = mapped_column(
        str_enum(PhaseStatus), nullable=False, default=PhaseStatus.INCOMPLETE
    )

    episode: Mapped["EpisodeOfCare"] = relationship(back_populates="phase_records")
    clinician: Mapped["Clinician | None"] = relationship()
    documentation: Mapped["DocumentationRecord | None"] = relationship(
        back_populates="phase_record", uselist=False
    )


class DocumentationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Clinical documentation attached to a phase.

    Checked against DocumentationRequirement before a phase is codeable. Vitals
    and time-in-session matter most for Phase 3B monitoring, the phase the
    roadmap flags as most likely to be under-documented in exports.
    """

    __tablename__ = "documentation_record"

    phase_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("phase_record.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    diagnosis_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    session_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    vitals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    time_in_session_minutes: Mapped[int | None] = mapped_column(nullable=True)

    phase_record: Mapped["PhaseRecord"] = relationship(back_populates="documentation")
