"""Coding & charge capture — turn documented visits into priced charges.

For each ``READY_TO_CODE`` PhaseRecord in an episode, pick the billing code for
its phase/modality, find the payer rule in effect on the service date, and
create a priced ``Charge``. When no active rule exists we can't price the visit,
so the charge is marked ``needs_review`` — never silently priced at zero.

The effective-dated rule lookup mirrors
``app/services/completeness.py:required_fields_for`` so pricing and completeness
read the same config the same way.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BillingCode,
    Charge,
    DocumentationRecord,
    EpisodeOfCare,
    PayerCodeRule,
    PhaseRecord,
)
from app.models.enums import ChargeStatus, Phase, PhaseStatus


@dataclass
class CodingResult:
    episode_id: uuid.UUID
    coded: int = 0
    needs_review: int = 0
    skipped: int = 0  # phases not ready to code
    charge_ids: list[uuid.UUID] = field(default_factory=list)


def _active_rule(
    db: Session, payer_id: uuid.UUID | None, phase: Phase, on: date
) -> tuple[BillingCode, PayerCodeRule] | None:
    """The billing code + payer rule in effect for a phase on a date, if any."""
    if payer_id is None:
        return None
    row = db.execute(
        select(BillingCode, PayerCodeRule)
        .join(PayerCodeRule, PayerCodeRule.billing_code_id == BillingCode.id)
        .where(
            PayerCodeRule.payer_id == payer_id,
            BillingCode.phase == phase,
            PayerCodeRule.effective_date <= on,
            (PayerCodeRule.end_date.is_(None)) | (PayerCodeRule.end_date >= on),
        )
        .order_by(PayerCodeRule.effective_date.desc())
    ).first()
    return (row[0], row[1]) if row else None


def _diagnosis_for(db: Session, phase_record_id: uuid.UUID) -> list:
    doc = db.scalar(
        select(DocumentationRecord).where(
            DocumentationRecord.phase_record_id == phase_record_id
        )
    )
    return list(doc.diagnosis_codes) if doc and doc.diagnosis_codes else []


def code_phase_record(db: Session, phase_record: PhaseRecord, payer_id: uuid.UUID | None) -> Charge:
    """Create (and add) a Charge for one ready-to-code phase record."""
    on = phase_record.service_date or date.today()
    match = _active_rule(db, payer_id, phase_record.phase, on)
    diagnosis = _diagnosis_for(db, phase_record.id)

    if match is None:
        charge = Charge(
            phase_record_id=phase_record.id,
            diagnosis_codes=diagnosis,
            status=ChargeStatus.NEEDS_REVIEW,
        )
    else:
        code, rule = match
        charge = Charge(
            phase_record_id=phase_record.id,
            billing_code_id=code.id,
            payer_code_rule_id=rule.id,
            diagnosis_codes=diagnosis,
            charge_amount=rule.rate,
            status=ChargeStatus.CODED if rule.rate is not None else ChargeStatus.NEEDS_REVIEW,
        )
    db.add(charge)
    db.flush()
    return charge


def code_episode(db: Session, episode_id: uuid.UUID) -> CodingResult:
    """Code every ready-to-code phase in an episode. Commits on success.

    Idempotency: a phase that already has a charge is skipped, so re-running is
    safe and won't double-bill.
    """
    episode = db.get(EpisodeOfCare, episode_id)
    if episode is None:
        raise ValueError(f"EpisodeOfCare {episode_id} not found")
    payer_id = episode.client.payer_id

    already = {
        c.phase_record_id
        for c in db.scalars(
            select(Charge).join(
                PhaseRecord, Charge.phase_record_id == PhaseRecord.id
            ).where(PhaseRecord.episode_id == episode_id)
        )
    }

    result = CodingResult(episode_id=episode_id)
    for pr in episode.phase_records:
        if pr.status != PhaseStatus.READY_TO_CODE:
            result.skipped += 1
            continue
        if pr.id in already:
            continue
        charge = code_phase_record(db, pr, payer_id)
        result.charge_ids.append(charge.id)
        if charge.status == ChargeStatus.CODED:
            result.coded += 1
        else:
            result.needs_review += 1

    db.commit()
    return result
