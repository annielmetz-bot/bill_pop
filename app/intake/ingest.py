"""Ingest adapters: land raw export rows into ``IntakeRawRecord``.

Ingest is intentionally dumb — it stores rows verbatim as JSONB and does not
interpret them. All interpretation happens later in ``normalize`` so the raw
payload is always preserved for audit and re-processing.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.models import IntakeBatch, IntakeRawRecord


def ingest_manual(
    db: Session, batch: IntakeBatch, rows: Iterable[dict[str, Any]]
) -> list[IntakeRawRecord]:
    """Store manually-entered rows (already JSON-shaped) as raw records."""
    records = [IntakeRawRecord(batch_id=batch.id, raw_payload=dict(row)) for row in rows]
    db.add_all(records)
    db.flush()
    return records


def ingest_csv(db: Session, batch: IntakeBatch, content: str) -> list[IntakeRawRecord]:
    """Parse CSV text into one raw record per row, keyed by header.

    Values stay as strings here; type coercion happens in ``mapping.to_canonical``
    during normalization.
    """
    reader = csv.DictReader(io.StringIO(content))
    rows = [dict(row) for row in reader]
    return ingest_manual(db, batch, rows)
