"""Intake / export staging.

Month 1 *scopes* intake but does not build the parsers. Raw export data is kept
as loosely-typed JSONB in IntakeRawRecord because the actual Homecoming/Althea
export shapes are not known yet — normalization from raw → PhaseRecord is where
that mapping will live once discovered, without forcing a migration per new field.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import str_enum
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ImportType, NormalizationStatus, SourceSystem


class IntakeBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intake_batch"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinic.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_system: Mapped[SourceSystem] = mapped_column(
        str_enum(SourceSystem), nullable=False
    )
    import_type: Mapped[ImportType] = mapped_column(str_enum(ImportType), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Reference to the stored file (object-store key / path), not the file itself.
    raw_file_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    raw_records: Mapped[list["IntakeRawRecord"]] = relationship(
        back_populates="batch"
    )


class IntakeRawRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intake_raw_record"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intake_batch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Deliberately unstructured until real export shapes are known.
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    normalization_status: Mapped[NormalizationStatus] = mapped_column(
        str_enum(NormalizationStatus),
        nullable=False,
        default=NormalizationStatus.PENDING,
    )
    # Why a record was flagged: list of missing-field descriptors from the
    # completeness check. Empty when normalized cleanly. This is what keeps
    # Phase 3B gaps visible instead of silently under-coded.
    flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Set once normalized into a PhaseRecord.
    phase_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("phase_record.id", ondelete="SET NULL"), nullable=True, index=True
    )

    batch: Mapped["IntakeBatch"] = relationship(back_populates="raw_records")
