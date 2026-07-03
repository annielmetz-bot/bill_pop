"""SQLAlchemy models for Bill Pop.

Importing this package registers every table on ``Base.metadata`` so Alembic
autogenerate and ``create_all`` see the full schema.
"""

from app.models.base import Base
from app.models.billing import Charge, Claim
from app.models.clinical import (
    Client,
    Clinic,
    Clinician,
    DocumentationRecord,
    EpisodeOfCare,
    PhaseRecord,
)
from app.models.coding import (
    BillingCode,
    DocumentationRequirement,
    Payer,
    PayerCodeRule,
)
from app.models.eligibility import EligibilityCheck
from app.models.intake import IntakeBatch, IntakeRawRecord

__all__ = [
    "Base",
    # clinical
    "Clinic",
    "Client",
    "Clinician",
    "EpisodeOfCare",
    "PhaseRecord",
    "DocumentationRecord",
    # coding config
    "Payer",
    "BillingCode",
    "PayerCodeRule",
    "DocumentationRequirement",
    # intake
    "IntakeBatch",
    "IntakeRawRecord",
    # eligibility
    "EligibilityCheck",
    # billing
    "Charge",
    "Claim",
]
