"""Eligibility gateway interface + selection.

The gateway is the single swap point between Bill Pop and a clearinghouse. Real
adapters (Availity/Waystar/Change) implement the same ``check`` contract and are
selected via ``settings.eligibility_gateway`` — no caller changes required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import settings
from app.eligibility.models import EligibilityRequest, EligibilityResponse


class EligibilityGateway(ABC):
    """Turns a 270 request into a 271 response against some clearinghouse."""

    name: str

    @abstractmethod
    def check(self, request: EligibilityRequest) -> EligibilityResponse:
        ...


def get_gateway(name: str | None = None) -> EligibilityGateway:
    """Return the configured gateway. Defaults to ``settings.eligibility_gateway``."""
    name = (name or settings.eligibility_gateway).lower()
    if name == "sandbox":
        from app.eligibility.sandbox import SandboxGateway

        return SandboxGateway()
    raise ValueError(
        f"Unknown eligibility gateway '{name}'. Only 'sandbox' exists until a "
        "clearinghouse is selected (spec open-question Q2)."
    )
