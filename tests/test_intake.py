"""Tests for the Data Intake Layer."""

from __future__ import annotations

import uuid
from datetime import date, time

from app.intake import ingest, normalize
from app.intake.mapping import parse_phase, to_canonical
from app.models.enums import NormalizationStatus, Phase, PhaseStatus, SourceSystem
from app.services import completeness
from tests.conftest import requires_db

# --- pure unit tests (no database) -----------------------------------------


def test_manual_mapping_is_identity_and_coerces_types():
    raw = {
        "client_id": "abc",
        "phase": "monitoring",
        "service_date": "2026-08-01",
        "start_time": "09:30",
        "time_in_session_minutes": "90",
        "diagnosis_codes": "F33.1;F41.1",
        "unknown_field": "ignored",
    }
    canonical = to_canonical(SourceSystem.MANUAL, raw)
    assert canonical["phase"] is Phase.MONITORING
    assert canonical["service_date"] == date(2026, 8, 1)
    assert canonical["start_time"] == time(9, 30)
    assert canonical["time_in_session_minutes"] == 90
    assert canonical["diagnosis_codes"] == ["F33.1", "F41.1"]
    assert "unknown_field" not in canonical


def test_homecoming_mapping_translates_vendor_fields():
    raw = {"patient_id": "p1", "session_stage": "dosing", "duration_minutes": "120"}
    canonical = to_canonical(SourceSystem.HOMECOMING, raw)
    assert canonical["client_id"] == "p1"
    assert canonical["phase"] is Phase.ADMINISTRATION
    assert canonical["time_in_session_minutes"] == 120


def test_parse_phase_synonyms():
    assert parse_phase("Prep") is Phase.PREPARATION
    assert parse_phase("MONITOR") is Phase.MONITORING
    assert parse_phase("nonsense") is None


def test_completeness_evaluate_flags_missing_phase3b_fields():
    required = {"vitals", "time_in_session", "licensed_clinician_signature"}

    class FakePR:
        clinician_id = None

    class FakeDoc:
        vitals = {}
        time_in_session_minutes = None
        diagnosis_codes = []
        session_notes = None

    missing = completeness.evaluate(required, FakePR(), FakeDoc())
    assert set(missing) == required


def test_completeness_evaluate_passes_when_documented():
    required = {"vitals", "time_in_session", "licensed_clinician_signature"}

    class FakePR:
        clinician_id = uuid.uuid4()

    class FakeDoc:
        vitals = {"bp": "120/80"}
        time_in_session_minutes = 90

    assert completeness.evaluate(required, FakePR(), FakeDoc()) == []


# --- integration tests (require Postgres) ----------------------------------


@requires_db
def test_normalize_complete_monitoring_record_is_ready_to_code(db_session, seeded_clinic):
    from app.models import IntakeBatch

    batch = IntakeBatch(clinic_id=seeded_clinic["clinic_id"], source_system=SourceSystem.MANUAL,
                        import_type="manual")
    db_session.add(batch)
    db_session.flush()

    ingest.ingest_manual(db_session, batch, [{
        "client_id": str(seeded_clinic["client_id"]),
        "clinician_id": str(seeded_clinic["clinician_id"]),
        "phase": "monitoring",
        "service_date": "2026-08-01",
        "vitals": {"bp": "118/76", "hr": 68},
        "time_in_session_minutes": 120,
    }])

    result = normalize.normalize_batch(db_session, batch.id)
    assert result.normalized == 1 and result.flagged == 0
    outcome = result.outcomes[0]
    assert outcome.status is NormalizationStatus.NORMALIZED

    from app.models import PhaseRecord

    pr = db_session.get(PhaseRecord, outcome.phase_record_id)
    assert pr.status is PhaseStatus.READY_TO_CODE


@requires_db
def test_normalize_monitoring_missing_vitals_is_flagged(db_session, seeded_clinic):
    from app.models import IntakeBatch

    batch = IntakeBatch(clinic_id=seeded_clinic["clinic_id"], source_system=SourceSystem.MANUAL,
                        import_type="manual")
    db_session.add(batch)
    db_session.flush()

    # Phase 3B monitoring with no vitals and no time — the roadmap's canonical gap.
    ingest.ingest_manual(db_session, batch, [{
        "client_id": str(seeded_clinic["client_id"]),
        "clinician_id": str(seeded_clinic["clinician_id"]),
        "phase": "monitoring",
        "service_date": "2026-08-01",
    }])

    result = normalize.normalize_batch(db_session, batch.id)
    assert result.flagged == 1 and result.normalized == 0
    flags = {f["field"] for f in result.outcomes[0].flags}
    assert {"vitals", "time_in_session"} <= flags


@requires_db
def test_normalize_missing_client_reference_fails_structurally(db_session, seeded_clinic):
    from app.models import IntakeBatch

    batch = IntakeBatch(clinic_id=seeded_clinic["clinic_id"], source_system=SourceSystem.MANUAL,
                        import_type="manual")
    db_session.add(batch)
    db_session.flush()
    ingest.ingest_manual(db_session, batch, [{"phase": "monitoring"}])

    result = normalize.normalize_batch(db_session, batch.id)
    assert result.flagged == 1
    assert result.outcomes[0].flags[0]["field"] == "client_id"
    assert result.outcomes[0].phase_record_id is None


@requires_db
def test_ingest_csv_creates_one_record_per_row(db_session, seeded_clinic):
    from app.models import IntakeBatch

    batch = IntakeBatch(clinic_id=seeded_clinic["clinic_id"], source_system=SourceSystem.MANUAL,
                        import_type="csv")
    db_session.add(batch)
    db_session.flush()
    csv_text = "client_id,phase\n{cid},monitoring\n{cid},integration\n".format(
        cid=seeded_clinic["client_id"]
    )
    records = ingest.ingest_csv(db_session, batch, csv_text)
    assert len(records) == 2
