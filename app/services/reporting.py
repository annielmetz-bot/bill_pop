"""Billing reporting — a claims summary for the clinic.

Aggregates claim and remittance state into the numbers a clinic actually asks
for: how much was billed, paid, still outstanding, and short-paid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Claim, Remittance
from app.models.enums import ClaimStatus


@dataclass
class ClaimsReport:
    claims_by_status: dict[str, int] = field(default_factory=dict)
    total_billed: Decimal = Decimal("0")
    total_paid: Decimal = Decimal("0")
    total_underpaid: Decimal = Decimal("0")
    outstanding: Decimal = Decimal("0")  # billed but not yet paid/denied
    underpaid_claims: int = 0


# Claims that have been sent but haven't reached a paid/denied resolution.
_OUTSTANDING = (ClaimStatus.SUBMITTED, ClaimStatus.ACCEPTED)


def claims_report(db: Session) -> ClaimsReport:
    report = ClaimsReport()

    by_status = db.execute(
        select(Claim.status, func.count()).group_by(Claim.status)
    ).all()
    report.claims_by_status = {status.value: count for status, count in by_status}

    report.total_billed = db.scalar(
        select(func.coalesce(func.sum(Claim.total_charge), 0))
    )
    report.outstanding = db.scalar(
        select(func.coalesce(func.sum(Claim.total_charge), 0)).where(
            Claim.status.in_(_OUTSTANDING)
        )
    )
    report.total_paid = db.scalar(
        select(func.coalesce(func.sum(Remittance.paid_amount), 0))
    )
    report.total_underpaid = db.scalar(
        select(func.coalesce(func.sum(Remittance.underpaid_amount), 0))
    )
    report.underpaid_claims = db.scalar(
        select(func.count()).where(Remittance.underpaid_amount > 0)
    )
    return report
