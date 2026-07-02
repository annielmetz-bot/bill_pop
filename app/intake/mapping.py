"""Source-system field mappings: raw export shape → canonical intake shape.

The normalizer works only against the **canonical** field names below. Each
source system supplies a mapping from its own field names to canonical ones, so
supporting a new export format is a config change here — the coding, claims, and
reporting layers never see the raw shapes.

⚠️  The HOMECOMING and ALTHEA mappings are PROVISIONAL placeholders. The real
export column names are not known yet (spec open-question Q1); they are guesses
kept here purely to show the extension point. Replace them once real (or
redacted) sample exports arrive.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from app.models.enums import Phase, SourceSystem

# Canonical fields the normalizer understands. ``client_id`` is required; the
# rest are optional and drive the phase / documentation records.
CANONICAL_FIELDS = frozenset(
    {
        "client_id",
        "episode_id",
        "phase",
        "service_date",
        "start_time",
        "end_time",
        "clinician_id",
        "diagnosis_codes",
        "session_notes",
        "vitals",
        "time_in_session_minutes",
    }
)

# raw_field_name -> canonical_field_name, per source system.
# MANUAL is the identity mapping: the manual-entry portal already speaks canonical.
FIELD_MAPS: dict[SourceSystem, dict[str, str]] = {
    SourceSystem.MANUAL: {f: f for f in CANONICAL_FIELDS},
    # PROVISIONAL — placeholder guesses, pending real export samples (Q1).
    SourceSystem.HOMECOMING: {
        "patient_id": "client_id",
        "course_id": "episode_id",
        "session_stage": "phase",
        "session_date": "service_date",
        "session_start": "start_time",
        "session_end": "end_time",
        "provider_id": "clinician_id",
        "dx_codes": "diagnosis_codes",
        "notes": "session_notes",
        "vitals": "vitals",
        "duration_minutes": "time_in_session_minutes",
    },
    # PROVISIONAL — placeholder guesses, pending real export samples (Q1).
    SourceSystem.ALTHEA: {
        "client_ref": "client_id",
        "treatment_id": "episode_id",
        "phase_name": "phase",
        "date_of_service": "service_date",
        "start": "start_time",
        "end": "end_time",
        "facilitator_id": "clinician_id",
        "diagnoses": "diagnosis_codes",
        "clinical_notes": "session_notes",
        "vital_signs": "vitals",
        "minutes": "time_in_session_minutes",
    },
}

# Homecoming/Althea may label phases differently; normalize common synonyms.
_PHASE_SYNONYMS: dict[str, Phase] = {
    "screening": Phase.SCREENING,
    "screen": Phase.SCREENING,
    "preparation": Phase.PREPARATION,
    "prep": Phase.PREPARATION,
    "administration": Phase.ADMINISTRATION,
    "dosing": Phase.ADMINISTRATION,
    "session": Phase.ADMINISTRATION,
    "monitoring": Phase.MONITORING,
    "monitor": Phase.MONITORING,
    "integration": Phase.INTEGRATION,
    "integrate": Phase.INTEGRATION,
}


def parse_phase(value: Any) -> Phase | None:
    """Best-effort map of a raw phase label onto the canonical Phase enum."""
    if value is None:
        return None
    if isinstance(value, Phase):
        return value
    return _PHASE_SYNONYMS.get(str(value).strip().lower())


def _coerce(field: str, value: Any) -> Any:
    """Light coercion of stringy CSV values into typed canonical values."""
    if value is None or value == "":
        return None
    if field == "phase":
        return parse_phase(value)
    if field == "service_date":
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    if field in ("start_time", "end_time"):
        return value if isinstance(value, time) else time.fromisoformat(str(value))
    if field == "time_in_session_minutes":
        return int(value)
    if field == "diagnosis_codes":
        if isinstance(value, list):
            return value
        # CSV supplies a delimited string, e.g. "F33.1;F41.1".
        return [c.strip() for c in str(value).replace(",", ";").split(";") if c.strip()]
    if field == "vitals":
        return value if isinstance(value, dict) else {"raw": value}
    return value


def to_canonical(source: SourceSystem, raw: dict[str, Any]) -> dict[str, Any]:
    """Translate one raw export row into a typed canonical dict.

    Unknown raw fields are ignored; unmapped canonical fields are simply absent.
    """
    field_map = FIELD_MAPS[source]
    canonical: dict[str, Any] = {}
    for raw_key, raw_val in raw.items():
        canonical_key = field_map.get(raw_key)
        if canonical_key is None:
            continue
        coerced = _coerce(canonical_key, raw_val)
        if coerced is not None:
            canonical[canonical_key] = coerced
    return canonical
