"""Eligibility & Benefits (270/271) HTTP endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EligibilityCheck
from app.schemas.eligibility import EligibilityCheckCreate, EligibilityCheckOut
from app.services import eligibility_service

router = APIRouter(tags=["eligibility"])


@router.post("/eligibility/checks", response_model=EligibilityCheckOut, status_code=201)
def create_check(
    payload: EligibilityCheckCreate, db: Session = Depends(get_db)
) -> EligibilityCheck:
    try:
        return eligibility_service.run_eligibility_check(
            db, payload.client_id, payload.service_type_code
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/eligibility/checks/{check_id}", response_model=EligibilityCheckOut)
def get_check(check_id: uuid.UUID, db: Session = Depends(get_db)) -> EligibilityCheck:
    check = db.get(EligibilityCheck, check_id)
    if check is None:
        raise HTTPException(status_code=404, detail="EligibilityCheck not found")
    return check


@router.get(
    "/clients/{client_id}/eligibility", response_model=EligibilityCheckOut | None
)
def latest_for_client(
    client_id: uuid.UUID, db: Session = Depends(get_db)
) -> EligibilityCheck | None:
    return db.scalars(
        select(EligibilityCheck)
        .where(EligibilityCheck.client_id == client_id)
        .order_by(EligibilityCheck.checked_at.desc())
    ).first()
