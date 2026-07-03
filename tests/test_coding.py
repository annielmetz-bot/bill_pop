"""Tests for coding & charge capture (Milestone C1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import ChargeStatus, Phase, PhaseStatus
from app.services import coding
from tests.conftest import requires_db


def _episode_with_phase(db, seeded_clinic, phase, status=PhaseStatus.READY_TO_CODE,
                        diagnosis=None):
    """Create an episode with a single phase record + documentation."""
    from app.models import DocumentationRecord, EpisodeOfCare, PhaseRecord

    episode = EpisodeOfCare(client_id=seeded_clinic["client_id"], state="NM")
    db.add(episode)
    db.flush()
    pr = PhaseRecord(
        episode_id=episode.id,
        clinician_id=seeded_clinic["clinician_id"],
        phase=phase,
        service_date=date(2026, 8, 1),
        status=status,
    )
    db.add(pr)
    db.flush()
    db.add(DocumentationRecord(phase_record_id=pr.id, diagnosis_codes=diagnosis or []))
    db.flush()
    return episode, pr


@requires_db
def test_ready_monitoring_phase_is_priced(db_session, seeded_clinic):
    episode, _ = _episode_with_phase(
        db_session, seeded_clinic, Phase.MONITORING, diagnosis=["F33.1"]
    )
    result = coding.code_episode(db_session, episode.id)
    assert result.coded == 1 and result.needs_review == 0

    from app.models import Charge

    charge = db_session.get(Charge, result.charge_ids[0])
    assert charge.status is ChargeStatus.CODED
    assert charge.charge_amount == Decimal("300.00")
    assert charge.diagnosis_codes == ["F33.1"]
    assert charge.payer_code_rule_id is not None


@requires_db
def test_phase_without_a_payer_rule_needs_review(db_session, seeded_clinic):
    # No rule seeded for integration → can't price → flagged, not zero-priced.
    episode, _ = _episode_with_phase(db_session, seeded_clinic, Phase.INTEGRATION)
    result = coding.code_episode(db_session, episode.id)
    assert result.needs_review == 1 and result.coded == 0

    from app.models import Charge

    charge = db_session.get(Charge, result.charge_ids[0])
    assert charge.status is ChargeStatus.NEEDS_REVIEW
    assert charge.charge_amount is None


@requires_db
def test_non_ready_phase_is_skipped(db_session, seeded_clinic):
    episode, _ = _episode_with_phase(
        db_session, seeded_clinic, Phase.MONITORING, status=PhaseStatus.INCOMPLETE
    )
    result = coding.code_episode(db_session, episode.id)
    assert result.coded == 0 and result.needs_review == 0 and result.skipped == 1


@requires_db
def test_coding_is_idempotent(db_session, seeded_clinic):
    episode, _ = _episode_with_phase(db_session, seeded_clinic, Phase.MONITORING)
    first = coding.code_episode(db_session, episode.id)
    second = coding.code_episode(db_session, episode.id)
    assert first.coded == 1
    assert second.coded == 0 and second.needs_review == 0  # nothing new to code


@requires_db
def test_coding_api_flow(db_session, seeded_clinic):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    episode, _ = _episode_with_phase(db_session, seeded_clinic, Phase.MONITORING)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        api = TestClient(app)
        r = api.post(f"/episodes/{episode.id}/code")
        assert r.status_code == 200 and r.json()["coded"] == 1
        charges = api.get(f"/episodes/{episode.id}/charges").json()
        assert len(charges) == 1
        assert charges[0]["status"] == "coded"
        assert charges[0]["charge_amount"] == "300.00"
    finally:
        app.dependency_overrides.clear()
