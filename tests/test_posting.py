"""Tests for remittance (835) & payment posting (Milestone C3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.claims.remittance_gateway import get_remittance_gateway
from app.claims.x12_835 import Adjustment, RemitResult, build_835, parse_835
from app.models.enums import ClaimStatus, Phase, PhaseStatus, RemittanceStatus
from app.services import claims_service, coding, posting
from tests.conftest import requires_db

# --- pure unit tests (no database) -----------------------------------------


def test_835_round_trip_paid():
    r = RemitResult(
        claim_control_number="BP1", charged_amount=Decimal("300.00"),
        paid_amount=Decimal("300.00"), patient_responsibility=Decimal("0"), denied=False,
    )
    p = parse_835(build_835(r, "NM Medicaid"))
    assert p.paid_amount == Decimal("300.00") and not p.denied


def test_835_round_trip_denied_carries_codes():
    r = RemitResult(
        claim_control_number="BP1", charged_amount=Decimal("300.00"),
        paid_amount=Decimal("0"), patient_responsibility=Decimal("0"), denied=True,
        adjustments=[Adjustment("CO", "16", Decimal("300.00"))],
    )
    p = parse_835(build_835(r, "NM Medicaid"))
    assert p.denied and p.denial_codes == ["16"]


def test_sandbox_scenarios_by_member_id():
    gw = get_remittance_gateway()
    full = parse_835(gw.remit("BP1", Decimal("300.00"), "NM", "13579"))
    under = parse_835(gw.remit("BP2", Decimal("300.00"), "NM", "UNDER1"))
    deny = parse_835(gw.remit("BP3", Decimal("300.00"), "NM", "DENY1"))
    assert full.paid_amount == Decimal("300.00") and not full.denied
    assert under.paid_amount == Decimal("240.00") and not under.denied
    assert deny.denied and deny.paid_amount == Decimal("0")


def test_unknown_remittance_gateway_raises():
    import pytest

    with pytest.raises(ValueError, match="Unknown remittance gateway"):
        get_remittance_gateway("waystar")


# --- integration tests (require Postgres) ----------------------------------


def _submitted_claim(db, seeded, member_id="13579"):
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
    return claims_service.submit_claim(db, claim.id)


@requires_db
def test_full_payment_posts_and_marks_claim_paid(db_session, seeded_clinic):
    claim = _submitted_claim(db_session, seeded_clinic, member_id="13579")
    rem = posting.post_remittance(db_session, claim.id)
    assert rem.status is RemittanceStatus.PAID
    assert rem.paid_amount == Decimal("300.00")
    assert rem.underpaid_amount == Decimal("0")
    assert db_session.get(type(claim), claim.id).status is ClaimStatus.PAID


@requires_db
def test_underpayment_is_flagged(db_session, seeded_clinic):
    claim = _submitted_claim(db_session, seeded_clinic, member_id="UNDER9")
    rem = posting.post_remittance(db_session, claim.id)
    assert rem.status is RemittanceStatus.PAID
    assert rem.paid_amount == Decimal("240.00")
    assert rem.underpaid_amount == Decimal("60.00")  # 300 contracted - 240 allowed


@requires_db
def test_denial_marks_claim_denied(db_session, seeded_clinic):
    claim = _submitted_claim(db_session, seeded_clinic, member_id="DENY7")
    rem = posting.post_remittance(db_session, claim.id)
    assert rem.status is RemittanceStatus.DENIED
    assert rem.paid_amount == Decimal("0")
    assert rem.denial_codes  # carries CARC code(s)
    assert db_session.get(type(claim), claim.id).status is ClaimStatus.DENIED


@requires_db
def test_double_posting_is_rejected(db_session, seeded_clinic):
    import pytest

    claim = _submitted_claim(db_session, seeded_clinic)
    posting.post_remittance(db_session, claim.id)
    with pytest.raises(ValueError, match="already has a posted remittance"):
        posting.post_remittance(db_session, claim.id)


@requires_db
def test_remittance_api_flow(db_session, seeded_clinic):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    claim = _submitted_claim(db_session, seeded_clinic, member_id="UNDER1")
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        api = TestClient(app)
        r = api.post(f"/claims/{claim.id}/remittance")
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "paid"
        assert body["underpaid_amount"] == "60.00"
        assert api.get(f"/claims/{claim.id}").json()["status"] == "paid"
    finally:
        app.dependency_overrides.clear()
