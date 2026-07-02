"""Normalization: raw intake rows → PhaseRecord / DocumentationRecord.

This is where the roadmap's central intake rule lives: incomplete records are
**flagged, not silently under-coded** (Phase 3B monitoring most of all). Each
pending raw record in a batch is mapped to canonical fields, turned into a
PhaseRecord + DocumentationRecord, and checked for documentation completeness.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intake.mapping import to_canonical
from app.models import (
    Client,
    DocumentationRecord,
    EpisodeOfCare,
    IntakeBatch,
    IntakeRawRecord,
    PhaseRecord,
)
from app.models.enums import (
    Modality,
    NormalizationStatus,
    Phase,
    PhaseStatus,
    SourceSystem,
)
from app.services import completeness


@dataclass
class RecordOutcome:
    raw_record_id: uuid.UUID
    status: NormalizationStatus
    phase_record_id: uuid.UUID | None = None
    flags: list[dict[str, str]] = field(default_factory=list)


@dataclass
class NormalizeResult:
    batch_id: uuid.UUID
    processed: int = 0
    normalized: int = 0
    flagged: int = 0
    outcomes: list[RecordOutcome] = field(default_factory=list)


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _flag(field_name: str, reason: str) -> dict[str, str]:
    return {"field": field_name, "reason": reason}


def _resolve_episode(
    db: Session, client: Client, episode_id: uuid.UUID | None
) -> EpisodeOfCare:
    """Use the referenced episode, else the client's latest, else create one."""
    if episode_id is not None:
        episode = db.get(EpisodeOfCare, episode_id)
        if episode is not None and episode.client_id == client.id:
            return episode

    existing = db.scalars(
        select(EpisodeOfCare)
        .where(EpisodeOfCare.client_id == client.id)
        .order_by(EpisodeOfCare.created_at.desc())
    ).first()
    if existing is not None:
        return existing

    episode = EpisodeOfCare(
        client_id=client.id,
        modality=Modality.PSILOCYBIN,
        state=client.clinic.state,
    )
    db.add(episode)
    db.flush()
    return episode


def _normalize_one(
    db: Session, source: SourceSystem, raw: IntakeRawRecord
) -> RecordOutcome:
    canonical = to_canonical(source, raw.raw_payload)

    # Structural prerequisites — without these we can't build a billable record.
    client_id = _as_uuid(canonical.get("client_id"))
    client = db.get(Client, client_id) if client_id else None
    if client is None:
        return _fail(raw, [_flag("client_id", "missing or unresolved client reference")])

    phase: Phase | None = canonical.get("phase")
    if phase is None:
        return _fail(raw, [_flag("phase", "missing or unrecognized phase label")])

    episode = _resolve_episode(db, client, _as_uuid(canonical.get("episode_id")))

    phase_record = PhaseRecord(
        episode_id=episode.id,
        clinician_id=_as_uuid(canonical.get("clinician_id")),
        phase=phase,
        service_date=canonical.get("service_date"),
        start_time=canonical.get("start_time"),
        end_time=canonical.get("end_time"),
        status=PhaseStatus.INCOMPLETE,
    )
    db.add(phase_record)
    db.flush()

    doc = DocumentationRecord(
        phase_record_id=phase_record.id,
        diagnosis_codes=canonical.get("diagnosis_codes") or [],
        session_notes=canonical.get("session_notes"),
        vitals=canonical.get("vitals") or {},
        time_in_session_minutes=canonical.get("time_in_session_minutes"),
    )
    db.add(doc)

    # Completeness against the client's payer config (Phase 3B strictness = data).
    required = completeness.required_fields_for(
        db, client.payer_id, phase, phase_record.service_date
    )
    missing = completeness.evaluate(required, phase_record, doc)

    raw.phase_record_id = phase_record.id
    if missing:
        phase_record.status = PhaseStatus.INCOMPLETE
        raw.normalization_status = NormalizationStatus.FLAGGED_INCOMPLETE
        raw.flags = [_flag(f, "required documentation missing") for f in missing]
    else:
        phase_record.status = PhaseStatus.READY_TO_CODE
        raw.normalization_status = NormalizationStatus.NORMALIZED
        raw.flags = []

    return RecordOutcome(
        raw_record_id=raw.id,
        status=raw.normalization_status,
        phase_record_id=phase_record.id,
        flags=list(raw.flags),
    )


def _fail(raw: IntakeRawRecord, flags: list[dict[str, str]]) -> RecordOutcome:
    """Flag a record that couldn't be structurally normalized. No PhaseRecord."""
    raw.normalization_status = NormalizationStatus.FLAGGED_INCOMPLETE
    raw.flags = flags
    return RecordOutcome(raw_record_id=raw.id, status=raw.normalization_status, flags=flags)


def normalize_batch(
    db: Session, batch_id: uuid.UUID, only_pending: bool = True
) -> NormalizeResult:
    """Normalize the (pending) raw records in a batch. Commits on success."""
    batch = db.get(IntakeBatch, batch_id)
    if batch is None:
        raise ValueError(f"IntakeBatch {batch_id} not found")

    records: Iterable[IntakeRawRecord] = batch.raw_records
    if only_pending:
        records = [
            r for r in records
            if r.normalization_status == NormalizationStatus.PENDING
        ]

    result = NormalizeResult(batch_id=batch.id)
    for raw in records:
        outcome = _normalize_one(db, batch.source_system, raw)
        result.processed += 1
        if outcome.status == NormalizationStatus.NORMALIZED:
            result.normalized += 1
        else:
            result.flagged += 1
        result.outcomes.append(outcome)

    db.commit()
    return result
