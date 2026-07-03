"""Claim scrubbing — validate a claim before it goes to the clearinghouse.

Split like ``completeness``: a DB-facing ``build_scrub_input`` gathers the facts,
and a pure ``scrub`` applies the rules so validation is unit-testable without a
database. Catching errors here is far cheaper than a clearinghouse rejection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Charge, Claim, Client, PhaseRecord


@dataclass
class ClaimLineInput:
    code: str | None
    service_date: date | None
    units: int
    amount: Decimal | None


@dataclass
class ClaimScrubInput:
    payer_present: bool
    member_id: str | None
    provider_npis: set[str] = field(default_factory=set)
    diagnosis_codes: list[str] = field(default_factory=list)
    total_charge: Decimal = Decimal("0")
    lines: list[ClaimLineInput] = field(default_factory=list)


def build_scrub_input(db: Session, claim: Claim) -> ClaimScrubInput:
    """Gather the facts a scrub needs from a claim and its charges."""
    client = db.get(Client, claim.client_id)
    demo = (client.demographics if client else None) or {}
    member_id = demo.get("member_id") or demo.get("insurance_id")

    charges = list(
        db.scalars(select(Charge).where(Charge.claim_id == claim.id))
    )
    npis: set[str] = set()
    diagnosis: list[str] = []
    lines: list[ClaimLineInput] = []
    for c in charges:
        pr = db.get(PhaseRecord, c.phase_record_id)
        if pr and pr.clinician and pr.clinician.npi:
            npis.add(pr.clinician.npi)
        for d in c.diagnosis_codes or []:
            if d not in diagnosis:
                diagnosis.append(d)
        code = c.billing_code.code if c.billing_code else None
        lines.append(
            ClaimLineInput(
                code=code,
                service_date=pr.service_date if pr else None,
                units=c.units,
                amount=c.charge_amount,
            )
        )

    return ClaimScrubInput(
        payer_present=claim.payer_id is not None,
        member_id=str(member_id) if member_id else None,
        provider_npis=npis,
        diagnosis_codes=diagnosis,
        total_charge=claim.total_charge,
        lines=lines,
    )


def scrub(data: ClaimScrubInput) -> list[str]:
    """Return a list of validation errors. Empty means the claim is clean.

    Pure and DB-free. Covers required-field presence plus a couple of basic
    NCCI-style sanity checks (duplicate service line, non-positive units).
    """
    errors: list[str] = []
    if not data.payer_present:
        errors.append("missing payer")
    if not data.member_id:
        errors.append("missing subscriber member id")
    if not data.provider_npis:
        errors.append("missing rendering-provider NPI")
    if not data.diagnosis_codes:
        errors.append("missing diagnosis code(s)")
    if not data.lines:
        errors.append("claim has no service lines")
    if data.total_charge is None or data.total_charge <= 0:
        errors.append("claim total charge must be positive")

    seen: set[tuple[str, date]] = set()
    for line in data.lines:
        if line.code is None:
            errors.append("service line missing billing code")
            continue
        if line.units < 1:
            errors.append(f"invalid units on {line.code}")
        if line.service_date is not None:
            key = (line.code, line.service_date)
            if key in seen:
                errors.append(
                    f"duplicate service line: {line.code} on {line.service_date}"
                )
            seen.add(key)
    return errors
