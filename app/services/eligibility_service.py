"""Eligibility orchestration: build request → call gateway → persist result."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.eligibility.gateway import EligibilityGateway, get_gateway
from app.eligibility.models import EligibilityRequest, Provider, Subscriber
from app.eligibility.x12 import build_270
from app.models import Client, EligibilityCheck


def _build_request(client: Client, service_type_code: str) -> EligibilityRequest:
    """Assemble a 270 request from a client's stored demographics + payer."""
    demo = client.demographics or {}
    payer = client.payer
    return EligibilityRequest(
        payer_name=payer.name if payer else "UNKNOWN",
        subscriber=Subscriber(
            member_id=str(demo.get("member_id") or demo.get("insurance_id") or client.id),
            first_name=demo.get("first_name") or demo.get("first"),
            last_name=demo.get("last_name") or demo.get("last"),
            date_of_birth=demo.get("date_of_birth"),
        ),
        provider=Provider(name=client.clinic.name if client.clinic else None),
        service_type_code=service_type_code,
    )


def run_eligibility_check(
    db: Session,
    client_id: uuid.UUID,
    service_type_code: str = "30",
    gateway: EligibilityGateway | None = None,
) -> EligibilityCheck:
    """Run a 270/271 check for a client and persist the result."""
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError(f"Client {client_id} not found")

    gateway = gateway or get_gateway()
    request = _build_request(client, service_type_code)
    response = gateway.check(request)

    check = EligibilityCheck(
        client_id=client.id,
        payer_id=client.payer_id,
        service_type_code=service_type_code,
        subscriber_id=request.subscriber.member_id,
        status=response.status,
        gateway=gateway.name,
        coverage=[b.model_dump(mode="json") for b in response.benefits],
        raw_request={"x12_270": build_270(request), "request": request.model_dump(mode="json")},
        raw_response={"x12_271": response.raw},
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check
