"""Domain enumerations.

These mirror the roadmap's controlled vocabularies. They are intentionally
extensible (e.g. ``Modality`` ships with psilocybin only but is designed to
grow to other PAT modalities without a schema rebuild).
"""

import enum


class SourceSystem(enum.StrEnum):
    """Clinic system of record a record originated from."""

    HOMECOMING = "homecoming"
    ALTHEA = "althea"
    MANUAL = "manual"


class BaaStatus(enum.StrEnum):
    """Business Associate Agreement status for a clinic."""

    PENDING = "pending"
    SIGNED = "signed"
    EXPIRED = "expired"


class Modality(enum.StrEnum):
    """PAT modality. Psilocybin (NM) is the first; built to extend."""

    PSILOCYBIN = "psilocybin"


class Phase(enum.StrEnum):
    """The four-phase model, with Phase 3 split into 3A/3B."""

    SCREENING = "screening"          # Phase 1
    PREPARATION = "preparation"      # Phase 2
    ADMINISTRATION = "administration"  # Phase 3A — dosing session
    MONITORING = "monitoring"        # Phase 3B — post-dose monitoring
    INTEGRATION = "integration"      # Phase 4


class PhaseStatus(enum.StrEnum):
    """Coding-readiness of a phase record."""

    DOCUMENTED = "documented"
    INCOMPLETE = "incomplete"
    READY_TO_CODE = "ready_to_code"


class PayerType(enum.StrEnum):
    MEDICAID = "medicaid"
    COMMERCIAL = "commercial"


class ImportType(enum.StrEnum):
    CSV = "csv"
    PDF = "pdf"
    MANUAL = "manual"


class NormalizationStatus(enum.StrEnum):
    """Lifecycle of a raw intake record on its way to a PhaseRecord."""

    PENDING = "pending"
    NORMALIZED = "normalized"
    FLAGGED_INCOMPLETE = "flagged_incomplete"


class EligibilityStatus(enum.StrEnum):
    """Outcome of a 270/271 eligibility check (271 EB01-derived)."""

    ACTIVE = "active"          # coverage active
    INACTIVE = "inactive"      # coverage inactive/terminated
    NEEDS_INFO = "needs_info"  # payer needs more info to respond
    NOT_FOUND = "not_found"    # subscriber/patient not found (271 AAA)
    ERROR = "error"            # transport / gateway error


class ChargeStatus(enum.StrEnum):
    """Coding-readiness of a billable charge line."""

    CODED = "coded"                  # priced against an active payer rule
    NEEDS_REVIEW = "needs_review"    # no active rule / can't price — flag, don't guess


class ClaimStatus(enum.StrEnum):
    """Lifecycle of a claim from assembly through payment."""

    DRAFT = "draft"          # assembled, not yet passing scrub
    SCRUBBED = "scrubbed"    # passed validation, ready to submit
    SUBMITTED = "submitted"  # sent to the clearinghouse
    ACCEPTED = "accepted"    # clearinghouse accepted the 837
    REJECTED = "rejected"    # clearinghouse rejected the 837
    PAID = "paid"            # remittance posted (Milestone C3)
    DENIED = "denied"        # remittance denied (Milestone C3)
