"""Coding & charge capture HTTP endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Charge, EpisodeOfCare, PhaseRecord
from app.schemas.billing import ChargeOut, CodingResultOut
from app.services import coding

router = APIRouter(tags=["billing"])


@router.post("/episodes/{episode_id}/code", response_model=CodingResultOut)
def code_episode(episode_id: uuid.UUID, db: Session = Depends(get_db)) -> coding.CodingResult:
    try:
        return coding.code_episode(db, episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/episodes/{episode_id}/charges", response_model=list[ChargeOut])
def list_charges(episode_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Charge]:
    if db.get(EpisodeOfCare, episode_id) is None:
        raise HTTPException(status_code=404, detail="EpisodeOfCare not found")
    return list(
        db.scalars(
            select(Charge)
            .join(PhaseRecord, Charge.phase_record_id == PhaseRecord.id)
            .where(PhaseRecord.episode_id == episode_id)
        )
    )
