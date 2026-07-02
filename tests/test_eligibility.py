"""Tests for the Eligibility (270/271) layer."""

from __future__ import annotations

from decimal import Decimal

from app.eligibility import x12
from app.eligibility.gateway import get_gateway
from app.eligibility.models import (
    BenefitLine,
    EligibilityRequest,
    EligibilityResponse,
    Subscriber,
)
from app.models.enums import EligibilityStatus
from tests.conftest import requires_db

# --- pure unit tests (no database) -----------------------------------------


def _req(member_id: str) -> EligibilityRequest:
    return EligibilityRequest(
        payer_name="NM Medicaid", subscriber=Subscriber(member_id=member_id)
    )


def test_sandbox_active_returns_benefits():
    resp = get_gateway().check(_req("13579"))  # odd digit sum → active
    assert resp.status is EligibilityStatus.ACTIVE
    assert resp.benefits and resp.plan_name


def test_sandbox_inactive():
    resp = get_gateway().check(_req("1234"))  # even digit sum → inactive
    assert resp.status is EligibilityStatus.INACTIVE
    assert resp.benefits == []


def test_sandbox_not_found():
    resp = get_gateway().check(_req("NF123"))
    assert resp.status is EligibilityStatus.NOT_FOUND


def test_build_270_has_expected_segments():
    edi = x12.build_270(_req("12345"))
    for token in ("ISA*", "ST*270*", "NM1*IL", "EQ*30", "SE*", "IEA*"):
        assert token in edi, token


def test_271_round_trip_preserves_status_and_benefits():
    resp = EligibilityResponse(
        status=EligibilityStatus.ACTIVE,
        plan_name="Test Plan",
        benefits=[
            BenefitLine(
                service_type_code="A6",
                service_type="Psychotherapy",
                coverage="copay",
                in_network=True,
                copay=Decimal("25.00"),
            )
        ],
    )
    parsed = x12.parse_271(x12.build_271(_req("12345"), resp))
    assert parsed.status is EligibilityStatus.ACTIVE
    assert parsed.plan_name == "Test Plan"
    assert len(parsed.benefits) == 1
    assert parsed.benefits[0].copay == Decimal("25.00")
    assert parsed.benefits[0].in_network is True


def test_271_round_trip_not_found():
    resp = EligibilityResponse(status=EligibilityStatus.NOT_FOUND)
    parsed = x12.parse_271(x12.build_271(_req("NF1"), resp))
    assert parsed.status is EligibilityStatus.NOT_FOUND


def test_unknown_gateway_raises():
    import pytest

    with pytest.raises(ValueError, match="Unknown eligibility gateway"):
        get_gateway("waystar")


# --- integration tests (require Postgres) ----------------------------------


@requires_db
def test_run_and_persist_eligibility_check(db_session, seeded_clinic):
    from app.models import Client, EligibilityCheck
    from app.services import eligibility_service

    # A client with a known member id → deterministic active coverage.
    client = Client(
        clinic_id=seeded_clinic["clinic_id"],
        payer_id=seeded_clinic["payer_id"],
        demographics={"member_id": "13579", "first_name": "Ada"},
    )
    db_session.add(client)
    db_session.flush()

    check = eligibility_service.run_eligibility_check(db_session, client.id)
    assert check.status is EligibilityStatus.ACTIVE
    assert check.gateway == "sandbox"
    assert len(check.coverage) == 3
    assert check.raw_request["x12_270"].startswith("ISA*")

    stored = db_session.get(EligibilityCheck, check.id)
    assert stored is not None and stored.subscriber_id == "13579"


@requires_db
def test_eligibility_api_flow(db_session, seeded_clinic):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.models import Client

    client_row = Client(
        clinic_id=seeded_clinic["clinic_id"],
        payer_id=seeded_clinic["payer_id"],
        demographics={"member_id": "13579"},
    )
    db_session.add(client_row)
    db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        api = TestClient(app)
        r = api.post(
            "/eligibility/checks",
            json={"client_id": str(client_row.id), "service_type_code": "30"},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "active"

        latest = api.get(f"/clients/{client_row.id}/eligibility").json()
        assert latest["status"] == "active"
    finally:
        app.dependency_overrides.clear()
