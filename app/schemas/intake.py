"""API schemas for the Data Intake Layer."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ImportType, NormalizationStatus, SourceSystem


class BatchCreate(BaseModel):
    clinic_id: uuid.UUID
    source_system: SourceSystem
    import_type: ImportType
    raw_file_ref: str | None = None


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    source_system: SourceSystem
    import_type: ImportType
    imported_at: datetime


class ManualRecordsIn(BaseModel):
    """Manual-entry rows, already in canonical shape (client_id + phase, etc.)."""

    rows: list[dict[str, Any]] = Field(min_length=1)


class RawRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    normalization_status: NormalizationStatus
    phase_record_id: uuid.UUID | None
    flags: list[dict[str, str]]


class IngestResult(BaseModel):
    batch_id: uuid.UUID
    ingested: int


class RecordOutcomeOut(BaseModel):
    raw_record_id: uuid.UUID
    status: NormalizationStatus
    phase_record_id: uuid.UUID | None = None
    flags: list[dict[str, str]] = []


class NormalizeResultOut(BaseModel):
    batch_id: uuid.UUID
    processed: int
    normalized: int
    flagged: int
    outcomes: list[RecordOutcomeOut]


class BatchSummaryOut(BaseModel):
    batch: BatchOut
    counts: dict[str, int]
    flagged_records: list[RawRecordOut]
