"""Payment posting — read an 835 and settle the claim.

Requests a remittance for a submitted claim, parses the 835, records what the
payer paid, classifies denials, and **flags underpayments vs. the contracted
rate** (the claim total, which was priced from ``PayerCodeRule.rate``).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.claims.remittance_gateway import RemittanceGateway, get_remittance_gateway
from app.claims.x12_835 import parse_835
from app.models import Claim, Client, Payer, Remittance
from app.models.enums import ClaimStatus, RemittanceStatus


def _underpaid(charged: Decimal, paid: Decimal, patient_resp: Decimal) -> Decimal:
    """Contracted rate minus what the payer allowed (paid + patient share)."""
    gap = charged - paid - patient_resp
    return gap if gap > 0 else Decimal("0")


def post_remittance(
    db: Session, claim_id: uuid.UUID, gateway: RemittanceGateway | None = None
) -> Remittance:
    """Fetch + post the 835 for a submitted claim. Commits."""
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise ValueError(f"Claim {claim_id} not found")
    if claim.remittance is not None:
        raise ValueError("claim already has a posted remittance")
    if claim.control_number is None or claim.status not in (
        ClaimStatus.SUBMITTED,
        ClaimStatus.ACCEPTED,
    ):
        raise ValueError("claim must be submitted/accepted before posting a remittance")

    client = db.get(Client, claim.client_id)
    member_id = str((client.demographics or {}).get("member_id", "")) if client else ""
    payer = db.get(Payer, claim.payer_id) if claim.payer_id else None

    gateway = gateway or get_remittance_gateway()
    edi = gateway.remit(
        claim.control_number, claim.total_charge, payer.name if payer else "UNKNOWN",
        member_id,
    )
    result = parse_835(edi)

    underpaid = (
        Decimal("0")
        if result.denied
        else _underpaid(claim.total_charge, result.paid_amount, result.patient_responsibility)
    )
    remittance = Remittance(
        claim_id=claim.id,
        payer_id=claim.payer_id,
        status=RemittanceStatus.DENIED if result.denied else RemittanceStatus.PAID,
        charged_amount=claim.total_charge,
        paid_amount=result.paid_amount,
        underpaid_amount=underpaid,
        adjustments=[
            {"group": a.group, "reason_code": a.reason_code, "amount": str(a.amount)}
            for a in result.adjustments
        ],
        denial_codes=list(result.denial_codes),
        raw_835={"x12": edi, "gateway": gateway.name},
    )
    db.add(remittance)
    claim.status = ClaimStatus.DENIED if result.denied else ClaimStatus.PAID
    db.commit()
    db.refresh(remittance)
    return remittance
