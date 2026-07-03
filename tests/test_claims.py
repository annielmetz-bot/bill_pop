"""Tests for claim assembly, scrub, and 837 submission (Milestone C2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.claims.gateway import get_claims_gateway
from app.claims.x12_837 import Encounter, ServiceLine, build_837
from app.models.enums import ClaimStatus, Phase, PhaseStatus
from app.services import claim_scrub, claims_service, coding
from app.services.claim_scrub import ClaimLineInput, ClaimScrubInput
from tests.conftest import requires_db

# --- pure unit tests (no database) -----------------------------------------


def _valid_input() -> ClaimScrubInput:
    return ClaimScrubInput(
        payer_present=True,
        member_id="13579",
        provider_npis={"1234567890"},
        diagnosis_codes=["F33.1"],
        total_charge=Decimal("300.00"),
        lines=[ClaimLineInput(code="X", service_date=date(2026, 8, 1), units=1,
                              amount=Decimal("300.00"))],
    )


def test_scrub_passes_a_complete_claim():
    assert claim_scrub.scrub(_valid_input()) == []


def test_scrub_flags_missing_fields():
    data = ClaimScrubInput(payer_present=False, member_id=None)
    errors = claim_scrub.scrub(data)
    assert any("payer" in e for e in errors)
    assert any("member id" in e for e in errors)
    assert any("NPI" in e for e in errors)
    assert any("diagnosis" in e for e in errors)


def test_scrub_flags_duplicate_service_line():
    data = _valid_input()
    data.lines.append(
        ClaimLineInput(code="X", service_date=date(2026, 8, 1), units=1,
                       amount=Decimal("300.00"))
    )
    data.total_charge = Decimal("600.00")
    assert any("duplicate service line" in e for e in claim_scrub.scrub(data))


def test_build_837_contains_expected_segments():
    edi = build_837(
        Encounter(
            claim_control_number="BP1",
            total_charge=Decimal("300.00"),
            payer_name="NM Medicaid",
            member_id="13579",
            provider_npi="1234567890",
            diagnosis_codes=["F33.1"],
            lines=[ServiceLine(code="NM-PSIL-MONITOR", charge=Decimal("300.00"),
                              units=1, service_date="20260801")],
        )
    )
    for tok in ("ISA*", "ST*837", "CLM*BP1", "HI*ABK:F33.1", "SV1*HC:NM-PSIL-MONITOR",
                "SE*", "IEA*"):
        assert tok in edi, tok


def test_sandbox_gateway_accepts_and_rejects():
    gw = get_claims_gateway()
    assert gw.submit("ISA*...clean 837...~", "BP1").accepted is True
    assert gw.submit("ISA*...NM1*IL*...REJECT...~", "BP2").accepted is False


def test_unknown_claims_gateway_raises():
    import pytest

    with pytest.raises(ValueError, match="Unknown claims gateway"):
        get_claims_gateway("waystar")


# --- integration tests (require Postgres) ----------------------------------


def _coded_episode(db, seeded, member_id="13579"):
    from app.models import Client, DocumentationRecord, EpisodeOfCare, PhaseRecord

    demo = {"member_id": member_id} if member_id else {"first": "Test"}
    client = Client(
        clinic_id=seeded["clinic_id"], payer_id=seeded["payer_id"], demographics=demo
    )
    db.add(client)
    db.flush()
    episode = EpisodeOfCare(client_id=client.id, state="NM")
    db.add(episode)
    db.flush()
    pr = PhaseRecord(
        episode_id=episode.id,
        clinician_id=seeded["clinician_id"],  # has NPI 1234567890
        phase=Phase.MONITORING,
        service_date=date(2026, 8, 1),
        status=PhaseStatus.READY_TO_CODE,
    )
    db.add(pr)
    db.flush()
    db.add(DocumentationRecord(phase_record_id=pr.id, diagnosis_codes=["F33.1"]))
    db.flush()
    coding.code_episode(db, episode.id)
    return episode


@requires_db
def test_assemble_scrub_submit_happy_path(db_session, seeded_clinic):
    episode = _coded_episode(db_session, seeded_clinic)

    claim = claims_service.assemble_claim(db_session, episode.id)
    assert claim.status is ClaimStatus.DRAFT
    assert claim.total_charge == Decimal("300.00")
    assert len(claim.charges) == 1

    assert claims_service.scrub_claim(db_session, claim.id) == []
    assert db_session.get(type(claim), claim.id).status is ClaimStatus.SCRUBBED

    submitted = claims_service.submit_claim(db_session, claim.id)
    assert submitted.status is ClaimStatus.ACCEPTED
    assert submitted.control_number and submitted.submitted_at
    assert submitted.raw_837["x12"].startswith("ISA*")
    assert submitted.raw_837["ack"]["accepted"] is True


@requires_db
def test_submit_blocked_when_scrub_fails(db_session, seeded_clinic):
    # Client without a member id → claim can't pass scrub.
    episode = _coded_episode(db_session, seeded_clinic, member_id=None)
    claim = claims_service.assemble_claim(db_session, episode.id)

    import pytest

    with pytest.raises(claims_service.ScrubError):
        claims_service.submit_claim(db_session, claim.id)
    assert db_session.get(type(claim), claim.id).status is ClaimStatus.DRAFT


@requires_db
def test_claims_api_flow(db_session, seeded_clinic):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    episode = _coded_episode(db_session, seeded_clinic)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        api = TestClient(app)
        claim_id = api.post("/claims", json={"episode_id": str(episode.id)}).json()["id"]
        scrub = api.post(f"/claims/{claim_id}/scrub").json()
        assert scrub["status"] == "scrubbed" and scrub["errors"] == []
        submitted = api.post(f"/claims/{claim_id}/submit").json()
        assert submitted["status"] == "accepted"
        assert api.get(f"/claims/{claim_id}").json()["control_number"]
    finally:
        app.dependency_overrides.clear()
