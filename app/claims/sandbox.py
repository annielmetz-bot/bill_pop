"""Deterministic sandbox claims gateway.

Stands in for a real clearinghouse until one is chosen (spec Q2). It accepts a
well-formed 837 and returns a deterministic acknowledgment. A claim can be
forced to reject for testing by including the sentinel member id ``REJECT`` in
the 837 (a stand-in for a clearinghouse front-end edit failure).
"""

from __future__ import annotations

from app.claims.gateway import ClaimAck, ClaimsGateway


class SandboxClaimsGateway(ClaimsGateway):
    name = "sandbox"

    def submit(self, edi_837: str, control_number: str) -> ClaimAck:
        if "REJECT" in edi_837:
            return ClaimAck(
                accepted=False,
                control_number=control_number,
                message="Sandbox rejection (front-end edit): subscriber not found.",
            )
        return ClaimAck(
            accepted=True,
            control_number=control_number,
            message="Accepted by sandbox clearinghouse.",
        )
