"""Tests for the billing report (Milestone C4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import Phase, PhaseStatus
from app.services import claims_service, coding, posting, reporting
from tests.conftest import requires_db


def _post_claim(db, seeded, member_id):
    """Full spine for one client → posted remittance."""
    from app.models import Client, DocumentationRecord, EpisodeOfCare, PhaseRecord

    client = Client(
        clinic_id=seeded["clinic_id"], payer_id=seeded["payer_id"],
        demographics={"member_id": member_id},
    )
    db.add(client)
    db.flush()
    episode = EpisodeOfCare(client_id=client.id, state="NM")
    db.add(episode)
    db.flush()
    pr = PhaseRecord(
        episode_id=episode.id, clinician_id=seeded["clinician_id"],
        phase=Phase.MONITORING, service_date=date(2026, 8, 1),
        status=PhaseStatus.READY_TO_CODE,
    )
    db.add(pr)
    db.flush()
    db.add(DocumentationRecord(phase_record_id=pr.id, diagnosis_codes=["F33.1"]))
    db.flush()
    coding.code_episode(db, episode.id)
    claim = claims_service.assemble_claim(db, episode.id)
    claims_service.submit_claim(db, claim.id)
    posting.post_remittance(db, claim.id)


@requires_db
def test_claims_report_rolls_up_billed_paid_and_underpaid(db_session, seeded_clinic):
    _post_claim(db_session, seeded_clinic, "13579")   # paid in full: 300
    _post_claim(db_session, seeded_clinic, "UNDER1")  # underpaid: paid 240
    _post_claim(db_session, seeded_clinic, "DENY1")   # denied: paid 0

    report = reporting.claims_report(db_session)
    assert report.total_billed == Decimal("900.00")           # 3 x 300
    assert report.total_paid == Decimal("540.00")             # 300 + 240 + 0
    assert report.total_underpaid == Decimal("60.00")         # UNDER: 300-240
    assert report.underpaid_claims == 1
    assert report.claims_by_status.get("paid") == 2
    assert report.claims_by_status.get("denied") == 1


@requires_db
def test_report_api(db_session, seeded_clinic):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    _post_claim(db_session, seeded_clinic, "13579")
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        body = TestClient(app).get("/reports/claims").json()
        assert body["total_billed"] == "300.00"
        assert body["total_paid"] == "300.00"
    finally:
        app.dependency_overrides.clear()
