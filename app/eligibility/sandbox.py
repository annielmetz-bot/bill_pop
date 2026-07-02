"""Deterministic sandbox eligibility gateway.

Stands in for a real clearinghouse sandbox until one is chosen (spec Q2). It
produces **deterministic** 271 responses keyed off the subscriber member id, so
tests and demos are reproducible:

- member id starting ``NF``           → subscriber not found
- member id whose digits sum is even  → inactive coverage
- otherwise                           → active coverage with provisional
                                        psilocybin-therapy + behavioral-health
                                        benefit lines

To prove the EDI path in both directions, the response is serialized to an
illustrative X12 271 and parsed back before being returned. Benefit amounts are
PROVISIONAL placeholders, not real NM Medicaid figures.
"""

from __future__ import annotations

from decimal import Decimal

from app.eligibility import x12
from app.eligibility.gateway import EligibilityGateway
from app.eligibility.models import (
    BenefitLine,
    EligibilityRequest,
    EligibilityResponse,
)
from app.models.enums import EligibilityStatus

# PROVISIONAL benefit lines for an active PAT / behavioral-health plan.
_ACTIVE_BENEFITS = [
    BenefitLine(
        service_type_code="A6",
        service_type="Psychotherapy",
        coverage="copay",
        in_network=True,
        copay=Decimal("25.00"),
        notes="PROVISIONAL sandbox benefit",
    ),
    BenefitLine(
        service_type_code="MH",
        service_type="Mental Health",
        coverage="coinsurance",
        in_network=True,
        coinsurance_percent=Decimal("20"),
        notes="PROVISIONAL sandbox benefit",
    ),
    BenefitLine(
        service_type_code="30",
        service_type="Health Benefit Plan Coverage",
        coverage="deductible",
        in_network=True,
        deductible_remaining=Decimal("500.00"),
        notes="PROVISIONAL sandbox benefit",
    ),
]


class SandboxGateway(EligibilityGateway):
    name = "sandbox"

    def check(self, request: EligibilityRequest) -> EligibilityResponse:
        member_id = request.subscriber.member_id.strip()

        if member_id.upper().startswith("NF"):
            response = EligibilityResponse(status=EligibilityStatus.NOT_FOUND)
        elif self._digit_sum(member_id) % 2 == 0:
            response = EligibilityResponse(
                status=EligibilityStatus.INACTIVE,
                plan_name="NM Medicaid (PROVISIONAL sandbox)",
            )
        else:
            response = EligibilityResponse(
                status=EligibilityStatus.ACTIVE,
                plan_name="NM Medicaid (PROVISIONAL sandbox)",
                benefits=list(_ACTIVE_BENEFITS),
            )

        # Round-trip through the illustrative X12 271 to exercise the EDI layer.
        edi_271 = x12.build_271(request, response)
        return x12.parse_271(edi_271)

    @staticmethod
    def _digit_sum(value: str) -> int:
        digits = [int(c) for c in value if c.isdigit()]
        return sum(digits) if digits else 1  # no digits → odd → active
