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
