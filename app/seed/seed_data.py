"""Seed data for the coding-rules configuration tables.

⚠️  PROVISIONAL DATA — DO NOT BILL AGAINST THIS AS-IS.

Every billing code and rate below is a *placeholder* standing in for the NM
Medicaid Advisory Board's final psilocybin-assisted-therapy code list, which
is not published as of July 2026 (see docs/intake-export-gaps.md, Q3). Codes
marked ``NM-PSIL-*`` are Bill Pop-internal placeholders for services that have
no established CPT/HCPCS analog yet; the standard CPT codes (90791, 90834) are
plausible analogs but are NOT confirmed as NM Medicaid-covered for PAT.

Rates are illustrative round numbers, not contracted amounts.

Run with:  python -m app.seed.seed_data
The script is idempotent — it upserts by natural key and can be re-run safely.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    BillingCode,
    DocumentationRequirement,
    Payer,
    PayerCodeRule,
)
from app.models.enums import Modality, PayerType, Phase

# Rules effective from NM's soft-launch window; all provisional.
EFFECTIVE_DATE = date(2026, 7, 1)

# --- Payer -----------------------------------------------------------------
PAYER = {"name": "NM Medicaid (PROVISIONAL)", "type": PayerType.MEDICAID, "state": "NM"}

# --- Billing codes, one representative per phase ----------------------------
# (code, phase, description, provisional_rate)
BILLING_CODES: list[tuple[str, Phase, str, Decimal]] = [
    (
        "90791",
        Phase.SCREENING,
        "PROVISIONAL — Psychiatric diagnostic evaluation (screening analog)",
        Decimal("180.00"),
    ),
    (
        "NM-PSIL-PREP",
        Phase.PREPARATION,
        "PROVISIONAL — Preparation session (no confirmed CPT analog)",
        Decimal("150.00"),
    ),
    (
        "NM-PSIL-ADMIN",
        Phase.ADMINISTRATION,
        "PROVISIONAL — Psilocybin administration / dosing session (Phase 3A)",
        Decimal("600.00"),
    ),
    (
        "NM-PSIL-MONITOR",
        Phase.MONITORING,
        "PROVISIONAL — Post-dose clinical monitoring (Phase 3B)",
        Decimal("300.00"),
    ),
    (
        "90834",
        Phase.INTEGRATION,
        "PROVISIONAL — Psychotherapy 45 min (integration analog)",
        Decimal("140.00"),
    ),
]

# --- Documentation requirements per phase -----------------------------------
# Phase 3B monitoring is intentionally the strictest — the roadmap flags it as
# the phase most likely to be under-documented in exports.
DOC_REQUIREMENTS: dict[Phase, list[tuple[str, bool]]] = {
    Phase.SCREENING: [
        ("licensed_clinician_signature", True),
        ("diagnosis_code", True),
    ],
    Phase.PREPARATION: [
        ("licensed_clinician_signature", True),
        ("session_notes", True),
    ],
    Phase.ADMINISTRATION: [
        ("licensed_clinician_signature", True),
        ("time_in_session", True),
    ],
    Phase.MONITORING: [
        ("licensed_clinician_signature", True),
        ("vitals", True),
        ("time_in_session", True),
    ],
    Phase.INTEGRATION: [
        ("licensed_clinician_signature", True),
        ("session_notes", True),
    ],
}


def _get_or_create_payer(db: Session) -> Payer:
    payer = db.scalar(select(Payer).where(Payer.name == PAYER["name"]))
    if payer is None:
        payer = Payer(**PAYER)
        db.add(payer)
        db.flush()
    return payer


def _get_or_create_code(db: Session, code: str, phase: Phase, desc: str) -> BillingCode:
    bc = db.scalar(select(BillingCode).where(BillingCode.code == code))
    if bc is None:
        bc = BillingCode(
            code=code, phase=phase, description=desc, modality=Modality.PSILOCYBIN
        )
        db.add(bc)
        db.flush()
    return bc


def _get_or_create_rule(
    db: Session, payer: Payer, code: BillingCode, rate: Decimal
) -> PayerCodeRule:
    rule = db.scalar(
        select(PayerCodeRule).where(
            PayerCodeRule.payer_id == payer.id,
            PayerCodeRule.billing_code_id == code.id,
            PayerCodeRule.effective_date == EFFECTIVE_DATE,
        )
    )
    if rule is None:
        rule = PayerCodeRule(
            payer_id=payer.id,
            billing_code_id=code.id,
            effective_date=EFFECTIVE_DATE,
            end_date=None,
            rate=rate,
            notes="PROVISIONAL placeholder pending NM Medicaid Advisory Board list.",
        )
        db.add(rule)
        db.flush()
    return rule


def _ensure_requirements(db: Session, rule: PayerCodeRule, phase: Phase) -> None:
    existing = {
        r.required_field
        for r in db.scalars(
            select(DocumentationRequirement).where(
                DocumentationRequirement.payer_code_rule_id == rule.id
            )
        )
    }
    for field, required in DOC_REQUIREMENTS[phase]:
        if field not in existing:
            db.add(
                DocumentationRequirement(
                    payer_code_rule_id=rule.id,
                    required_field=field,
                    required=required,
                )
            )


def seed(db: Session) -> None:
    payer = _get_or_create_payer(db)
    for code, phase, desc, rate in BILLING_CODES:
        bc = _get_or_create_code(db, code, phase, desc)
        rule = _get_or_create_rule(db, payer, bc, rate)
        _ensure_requirements(db, rule, phase)
    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed(db)
    print("Seed complete — PROVISIONAL NM Medicaid config loaded.")


if __name__ == "__main__":
    main()
