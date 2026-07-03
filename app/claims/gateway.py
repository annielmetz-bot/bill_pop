"""Claims submission gateway interface + selection.

Mirrors the eligibility gateway: the single swap point between Bill Pop and a
clearinghouse for 837 submission. Only a sandbox exists until a vendor is chosen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.config import settings


class ClaimAck(BaseModel):
    """Clearinghouse acknowledgment of a submitted 837 (a simplified 999/277CA)."""

    accepted: bool
    control_number: str
    message: str = ""


class ClaimsGateway(ABC):
    name: str

    @abstractmethod
    def submit(self, edi_837: str, control_number: str) -> ClaimAck:
        ...


def get_claims_gateway(name: str | None = None) -> ClaimsGateway:
    name = (name or settings.claims_gateway).lower()
    if name == "sandbox":
        from app.claims.sandbox import SandboxClaimsGateway

        return SandboxClaimsGateway()
    raise ValueError(
        f"Unknown claims gateway '{name}'. Only 'sandbox' exists until a "
        "clearinghouse is selected (spec open-question Q2)."
    )
