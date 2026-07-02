"""Documentation-completeness check — is a PhaseRecord ready to code?

Requirements are read from the same ``DocumentationRequirement`` config the
Month 1 seed populates, so Phase 3B monitoring's strictness (vitals + time) is
*data, not special-cased logic*. The evaluator is a pure function so it can be
unit-tested without a database.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BillingCode,
    DocumentationRecord,
    DocumentationRequirement,
    PayerCodeRule,
    PhaseRecord,
)
from app.models.enums import Phase

# Maps a required_field name to a predicate: does the documentation satisfy it?
# Kept here (not in config) because these are *how we read our own models*, not
# payer policy. Unknown requirement names are treated as satisfied-if-present-
# elsewhere — see ``evaluate`` — so a new payer field never hard-crashes intake.
_SATISFIED: dict[str, Callable[[PhaseRecord, DocumentationRecord | None], bool]] = {
    "licensed_clinician_signature": lambda pr, doc: pr.clinician_id is not None,
    "vitals": lambda pr, doc: bool(doc and doc.vitals),
    "time_in_session": lambda pr, doc: bool(doc and doc.time_in_session_minutes),
    "diagnosis_code": lambda pr, doc: bool(doc and doc.diagnosis_codes),
    "session_notes": lambda pr, doc: bool(doc and doc.session_notes),
}


def required_fields_for(
    db: Session,
    payer_id: uuid.UUID | None,
    phase: Phase,
    service_date: date | None,
) -> set[str]:
    """Required documentation fields for a phase, per the client's payer config.

    Unions the ``required`` DocumentationRequirements across every billing code
    for the phase whose PayerCodeRule is in effect on ``service_date``. Returns
    an empty set when no payer / no matching rules — nothing to enforce yet.
    """
    if payer_id is None:
        return set()

    on_date = service_date or date.today()
    stmt = (
        select(DocumentationRequirement.required_field)
        .join(
            PayerCodeRule,
            DocumentationRequirement.payer_code_rule_id == PayerCodeRule.id,
        )
        .join(BillingCode, PayerCodeRule.billing_code_id == BillingCode.id)
        .where(
            PayerCodeRule.payer_id == payer_id,
            BillingCode.phase == phase,
            DocumentationRequirement.required.is_(True),
            PayerCodeRule.effective_date <= on_date,
            (PayerCodeRule.end_date.is_(None)) | (PayerCodeRule.end_date >= on_date),
        )
    )
    return set(db.scalars(stmt).all())


def evaluate(
    required: set[str],
    phase_record: PhaseRecord,
    doc: DocumentationRecord | None,
) -> list[str]:
    """Pure check: which required fields are missing? DB-free by design.

    A requirement with no known predicate is conservatively treated as *missing*
    unless it maps to a truthy attribute on the documentation record — this fails
    safe (flag for review) rather than silently passing an unrecognized rule.
    """
    missing: list[str] = []
    for field in sorted(required):
        predicate = _SATISFIED.get(field)
        if predicate is not None:
            satisfied = predicate(phase_record, doc)
        else:
            satisfied = bool(doc and getattr(doc, field, None))
        if not satisfied:
            missing.append(field)
    return missing
