"""End-to-end API smoke tests via TestClient (require Postgres)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from tests.conftest import requires_db


@pytest.fixture
def client(db_session):
    """TestClient wired to the rolled-back test session."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_health():
    assert TestClient(app).get("/health").json()["status"] == "ok"


@requires_db
def test_intake_flow_surfaces_flagged_records(client, seeded_clinic):
    cid = str(seeded_clinic["client_id"])
    clinician = str(seeded_clinic["clinician_id"])

    r = client.post(
        "/intake/batches",
        json={
            "clinic_id": str(seeded_clinic["clinic_id"]),
            "source_system": "manual",
            "import_type": "manual",
        },
    )
    assert r.status_code == 201
    batch_id = r.json()["id"]

    r = client.post(
        f"/intake/batches/{batch_id}/records",
        json={
            "rows": [
                {  # complete Phase 3B monitoring
                    "client_id": cid,
                    "clinician_id": clinician,
                    "phase": "monitoring",
                    "service_date": "2026-08-01",
                    "vitals": {"bp": "118/76"},
                    "time_in_session_minutes": 120,
                },
                {  # incomplete — missing vitals + time
                    "client_id": cid,
                    "clinician_id": clinician,
                    "phase": "monitoring",
                    "service_date": "2026-08-01",
                },
            ]
        },
    )
    assert r.status_code == 201 and r.json()["ingested"] == 2

    r = client.post(f"/intake/batches/{batch_id}/normalize")
    body = r.json()
    assert body["normalized"] == 1 and body["flagged"] == 1

    summary = client.get(f"/intake/batches/{batch_id}").json()
    assert summary["counts"]["normalized"] == 1
    assert summary["counts"]["flagged_incomplete"] == 1
    assert len(summary["flagged_records"]) == 1
    missing = {f["field"] for f in summary["flagged_records"][0]["flags"]}
    assert {"vitals", "time_in_session"} <= missing
