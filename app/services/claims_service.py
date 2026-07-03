"""Claims orchestration — assemble → scrub → submit.

Assembly groups an episode's coded charges for the client's payer into a claim;
scrub validates it; submit builds the 837 and hands it to the clearinghouse
gateway. The scrub input doubles as the source for 837 assembly, so validation
and submission read the exact same facts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.claims.gateway import ClaimsGateway, get_claims_gateway
from app.claims.x12_837 import Encounter, ServiceLine, build_837
from app.models import Charge, Claim, EpisodeOfCare, Payer
from app.models.enums import ChargeStatus, ClaimStatus
from app.services import claim_scrub


class ScrubError(ValueError):
    """Raised when a claim can't be submitted because it fails validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def assemble_claim(db: Session, episode_id: uuid.UUID) -> Claim:
    """Group an episode's unclaimed coded charges into a draft claim."""
    episode = db.get(EpisodeOfCare, episode_id)
    if episode is None:
        raise ValueError(f"EpisodeOfCare {episode_id} not found")

    charges = _unclaimed_coded_charges(db, episode_id)
    if not charges:
        raise ValueError("no coded, unclaimed charges to assemble for this episode")

    total = sum((c.charge_amount or Decimal("0") for c in charges), Decimal("0"))
    claim = Claim(
        client_id=episode.client_id,
        payer_id=episode.client.payer_id,
        episode_id=episode_id,
        status=ClaimStatus.DRAFT,
        total_charge=total,
    )
    db.add(claim)
    db.flush()
    for c in charges:
        c.claim_id = claim.id
    db.commit()
    db.refresh(claim)
    return claim


def _unclaimed_coded_charges(db: Session, episode_id: uuid.UUID) -> list[Charge]:
    from app.models import PhaseRecord

    return list(
        db.scalars(
            select(Charge)
            .join(PhaseRecord, Charge.phase_record_id == PhaseRecord.id)
            .where(
                PhaseRecord.episode_id == episode_id,
                Charge.claim_id.is_(None),
                Charge.status == ChargeStatus.CODED,
            )
        )
    )


def scrub_claim(db: Session, claim_id: uuid.UUID) -> list[str]:
    """Validate a claim; SCRUBBED when clean, else DRAFT with recorded reasons."""
    claim = _get_claim(db, claim_id)
    errors = claim_scrub.scrub(claim_scrub.build_scrub_input(db, claim))
    claim.scrub_errors = errors
    claim.status = ClaimStatus.SCRUBBED if not errors else ClaimStatus.DRAFT
    db.commit()
    return errors


def submit_claim(
    db: Session, claim_id: uuid.UUID, gateway: ClaimsGateway | None = None
) -> Claim:
    """Scrub (if needed), build the 837, and submit to the clearinghouse."""
    claim = _get_claim(db, claim_id)
    data = claim_scrub.build_scrub_input(db, claim)
    errors = claim_scrub.scrub(data)
    if errors:
        claim.scrub_errors = errors
        claim.status = ClaimStatus.DRAFT
        db.commit()
        raise ScrubError(errors)

    control = f"BP{claim.id.hex[:10].upper()}"
    encounter = Encounter(
        claim_control_number=control,
        total_charge=claim.total_charge,
        payer_name=_payer_name(db, claim.payer_id),
        member_id=data.member_id or "",
        provider_npi=next(iter(data.provider_npis), ""),
        diagnosis_codes=data.diagnosis_codes,
        lines=[
            ServiceLine(
                code=line.code or "",
                charge=line.amount or Decimal("0"),
                units=line.units,
                service_date=line.service_date.strftime("%Y%m%d")
                if line.service_date
                else None,
            )
            for line in data.lines
        ],
    )
    edi = build_837(encounter)

    gateway = gateway or get_claims_gateway()
    ack = gateway.submit(edi, control)

    claim.control_number = control
    claim.gateway = gateway.name
    claim.scrub_errors = []
    claim.status = ClaimStatus.ACCEPTED if ack.accepted else ClaimStatus.REJECTED
    claim.submitted_at = datetime.now(UTC)
    claim.raw_837 = {"x12": edi, "ack": ack.model_dump()}
    db.commit()
    db.refresh(claim)
    return claim


def _get_claim(db: Session, claim_id: uuid.UUID) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise ValueError(f"Claim {claim_id} not found")
    return claim


def _payer_name(db: Session, payer_id: uuid.UUID | None) -> str:
    if payer_id is None:
        return "UNKNOWN"
    payer = db.get(Payer, payer_id)
    return payer.name if payer else "UNKNOWN"
