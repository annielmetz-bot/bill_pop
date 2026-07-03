"""Claims HTTP endpoints — assemble, scrub, submit, fetch."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Claim
from app.schemas.claims import ClaimCreate, ClaimOut, ScrubResult
from app.services import claims_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=ClaimOut, status_code=201)
def assemble(payload: ClaimCreate, db: Session = Depends(get_db)) -> Claim:
    try:
        return claims_service.assemble_claim(db, payload.episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{claim_id}/scrub", response_model=ScrubResult)
def scrub(claim_id: uuid.UUID, db: Session = Depends(get_db)) -> ScrubResult:
    try:
        errors = claims_service.scrub_claim(db, claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    claim = db.get(Claim, claim_id)
    return ScrubResult(claim_id=claim_id, status=claim.status, errors=errors)


@router.post("/{claim_id}/submit", response_model=ClaimOut)
def submit(claim_id: uuid.UUID, db: Session = Depends(get_db)) -> Claim:
    try:
        return claims_service.submit_claim(db, claim_id)
    except claims_service.ScrubError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "claim failed scrub", "reasons": exc.errors}
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: uuid.UUID, db: Session = Depends(get_db)) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim
