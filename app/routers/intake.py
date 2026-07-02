"""Data Intake Layer HTTP endpoints."""

from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.intake import ingest, normalize
from app.models import IntakeBatch
from app.models.enums import NormalizationStatus
from app.schemas.intake import (
    BatchCreate,
    BatchOut,
    BatchSummaryOut,
    IngestResult,
    ManualRecordsIn,
    NormalizeResultOut,
    RawRecordOut,
)

router = APIRouter(prefix="/intake", tags=["intake"])


def _get_batch(db: Session, batch_id: uuid.UUID) -> IntakeBatch:
    batch = db.get(IntakeBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="IntakeBatch not found")
    return batch


@router.post("/batches", response_model=BatchOut, status_code=201)
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)) -> IntakeBatch:
    batch = IntakeBatch(**payload.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/batches/{batch_id}/records", response_model=IngestResult, status_code=201)
def add_manual_records(
    batch_id: uuid.UUID, payload: ManualRecordsIn, db: Session = Depends(get_db)
) -> IngestResult:
    batch = _get_batch(db, batch_id)
    records = ingest.ingest_manual(db, batch, payload.rows)
    db.commit()
    return IngestResult(batch_id=batch.id, ingested=len(records))


@router.post("/batches/{batch_id}/import-csv", response_model=IngestResult, status_code=201)
async def import_csv(
    batch_id: uuid.UUID, file: UploadFile, db: Session = Depends(get_db)
) -> IngestResult:
    batch = _get_batch(db, batch_id)
    content = (await file.read()).decode("utf-8-sig")
    records = ingest.ingest_csv(db, batch, content)
    db.commit()
    return IngestResult(batch_id=batch.id, ingested=len(records))


@router.post("/batches/{batch_id}/normalize", response_model=NormalizeResultOut)
def normalize_batch(
    batch_id: uuid.UUID, db: Session = Depends(get_db)
) -> normalize.NormalizeResult:
    _get_batch(db, batch_id)
    return normalize.normalize_batch(db, batch_id)


@router.get("/batches/{batch_id}", response_model=BatchSummaryOut)
def get_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)) -> BatchSummaryOut:
    batch = _get_batch(db, batch_id)
    counts = Counter(r.normalization_status.value for r in batch.raw_records)
    flagged = [
        r
        for r in batch.raw_records
        if r.normalization_status == NormalizationStatus.FLAGGED_INCOMPLETE
    ]
    return BatchSummaryOut(
        batch=BatchOut.model_validate(batch),
        counts=dict(counts),
        flagged_records=[RawRecordOut.model_validate(r) for r in flagged],
    )
