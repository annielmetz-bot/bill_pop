"""Shared test fixtures.

Unit tests run everywhere with no database. Integration tests depend on the
``db_session`` fixture, which **skips** the test when Postgres isn't reachable —
so the committed suite stays green in a bare CI while still exercising the full
DB/API flow wherever a database is present (e.g. the dev container).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings

_engine = create_engine(settings.database_url, future=True)


def _postgres_available() -> bool:
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


POSTGRES = _postgres_available()
requires_db = pytest.mark.skipif(not POSTGRES, reason="Postgres not available")


@pytest.fixture
def db_session():
    """A session whose writes (even committed ones) roll back after the test.

    Uses SQLAlchemy 2.0 ``join_transaction_mode="create_savepoint"`` so the
    service layer's ``db.commit()`` calls land on a savepoint inside an outer
    transaction we roll back at teardown.
    """
    if not POSTGRES:
        pytest.skip("Postgres not available")
    connection = _engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def seeded_clinic(db_session: Session):
    """A clinic + client + Phase-3B payer config, for intake integration tests.

    Returns a small namespace of ids the tests can reference. The payer config
    mirrors the Month 1 seed: monitoring (Phase 3B) requires vitals + time.
    """
    from app.models import (
        BillingCode,
        Client,
        Clinic,
        Clinician,
        DocumentationRequirement,
        Payer,
        PayerCodeRule,
    )
    from app.models.enums import BaaStatus, PayerType, Phase, SourceSystem

    clinic = Clinic(
        name="Test PAT Clinic",
        source_system=SourceSystem.MANUAL,
        baa_status=BaaStatus.SIGNED,
        state="NM",
    )
    payer = Payer(name="Test NM Medicaid", type=PayerType.MEDICAID, state="NM")
    db_session.add_all([clinic, payer])
    db_session.flush()

    client = Client(clinic_id=clinic.id, demographics={"first": "Test"}, payer_id=payer.id)
    clinician = Clinician(
        clinic_id=clinic.id, name="Dr. Test", credential_type="MD", npi="1234567890"
    )
    # Unique code so the fixture never collides with seeded/other-test data.
    monitor_code = BillingCode(
        code=f"TM-{uuid.uuid4().hex[:8]}",
        phase=Phase.MONITORING,
        description="test monitor",
    )
    db_session.add_all([client, clinician, monitor_code])
    db_session.flush()

    rule = PayerCodeRule(
        payer_id=payer.id,
        billing_code_id=monitor_code.id,
        effective_date=date(2026, 1, 1),
    )
    db_session.add(rule)
    db_session.flush()
    db_session.add_all(
        [
            DocumentationRequirement(
                payer_code_rule_id=rule.id, required_field="vitals", required=True
            ),
            DocumentationRequirement(
                payer_code_rule_id=rule.id, required_field="time_in_session", required=True
            ),
            DocumentationRequirement(
                payer_code_rule_id=rule.id,
                required_field="licensed_clinician_signature",
                required=True,
            ),
        ]
    )
    db_session.flush()

    return {
        "clinic_id": clinic.id,
        "client_id": client.id,
        "clinician_id": clinician.id,
        "payer_id": payer.id,
    }
