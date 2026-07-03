"""Remittance gateway — where an 835 comes back from the clearinghouse.

Only a deterministic sandbox exists until a vendor is chosen (spec Q2). The
sandbox picks a payment scenario from the subscriber member id so tests and
demos are reproducible:

- member id starts ``DENY``   → claim denied (zero paid)
- member id starts ``UNDER``  → underpaid (payer allows 80% of the contracted rate)
- otherwise                   → paid in full at the contracted rate
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.claims.x12_835 import Adjustment, RemitResult, build_835
from app.config import settings


class RemittanceGateway(ABC):
    name: str

    @abstractmethod
    def remit(
        self, control_number: str, charged_amount: Decimal, payer_name: str, member_id: str
    ) -> str:
        """Return an 835 (EDI string) for the given claim."""


class SandboxRemittanceGateway(RemittanceGateway):
    name = "sandbox"

    def remit(
        self, control_number: str, charged_amount: Decimal, payer_name: str, member_id: str
    ) -> str:
        mid = (member_id or "").upper()
        if mid.startswith("DENY"):
            result = RemitResult(
                claim_control_number=control_number,
                charged_amount=charged_amount,
                paid_amount=Decimal("0"),
                patient_responsibility=Decimal("0"),
                denied=True,
                adjustments=[Adjustment(group="CO", reason_code="16", amount=charged_amount)],
            )
        elif mid.startswith("UNDER"):
            allowed = (charged_amount * Decimal("0.80")).quantize(Decimal("0.01"))
            result = RemitResult(
                claim_control_number=control_number,
                charged_amount=charged_amount,
                paid_amount=allowed,
                patient_responsibility=Decimal("0"),
                denied=False,
                # CO-45: charge exceeds the payer's fee schedule (an underpayment).
                adjustments=[
                    Adjustment(group="CO", reason_code="45", amount=charged_amount - allowed)
                ],
            )
        else:
            result = RemitResult(
                claim_control_number=control_number,
                charged_amount=charged_amount,
                paid_amount=charged_amount,
                patient_responsibility=Decimal("0"),
                denied=False,
            )
        return build_835(result, payer_name)


def get_remittance_gateway(name: str | None = None) -> RemittanceGateway:
    name = (name or settings.remittance_gateway).lower()
    if name == "sandbox":
        return SandboxRemittanceGateway()
    raise ValueError(
        f"Unknown remittance gateway '{name}'. Only 'sandbox' exists until a "
        "clearinghouse is selected (spec open-question Q2)."
    )
