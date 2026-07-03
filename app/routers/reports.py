"""Reporting HTTP endpoints."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import reporting

router = APIRouter(prefix="/reports", tags=["reports"])


class ClaimsReportOut(BaseModel):
    claims_by_status: dict[str, int]
    total_billed: Decimal
    total_paid: Decimal
    total_underpaid: Decimal
    outstanding: Decimal
    underpaid_claims: int


@router.get("/claims", response_model=ClaimsReportOut)
def claims_report(db: Session = Depends(get_db)) -> reporting.ClaimsReport:
    return reporting.claims_report(db)
