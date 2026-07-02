"""Schema smoke tests — no database required.

These validate the model layer assembles as expected, so a broken import or a
dropped table is caught in CI without needing Postgres.
"""

from app.models import Base
from app.models.enums import Phase
from app.seed.seed_data import BILLING_CODES, DOC_REQUIREMENTS

EXPECTED_TABLES = {
    "clinic",
    "client",
    "clinician",
    "episode_of_care",
    "phase_record",
    "documentation_record",
    "payer",
    "billing_code",
    "payer_code_rule",
    "documentation_requirement",
    "intake_batch",
    "intake_raw_record",
}


def test_all_tables_registered():
    assert EXPECTED_TABLES <= set(Base.metadata.tables.keys())


def test_every_phase_has_a_seed_code_and_requirements():
    seeded_phases = {phase for _, phase, _, _ in BILLING_CODES}
    assert seeded_phases == set(Phase)
    assert set(DOC_REQUIREMENTS.keys()) == set(Phase)


def test_phase_3b_monitoring_requires_vitals_and_time():
    fields = {field for field, _ in DOC_REQUIREMENTS[Phase.MONITORING]}
    assert {"vitals", "time_in_session"} <= fields
