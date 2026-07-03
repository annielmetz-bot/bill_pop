"""FastAPI application entrypoint.

Month 2 adds the Data Intake Layer and Eligibility (270/271). Coding, claims,
remittance, posting, and reporting routers arrive in later months per the
roadmap.
"""

from fastapi import FastAPI

from app.config import settings
from app.routers import billing, eligibility, intake

app = FastAPI(
    title="Bill Pop",
    description="Billing automation agent for psychedelic-assisted therapy clinics",
    version="0.2.0",
)

app.include_router(intake.router)
app.include_router(eligibility.router)
app.include_router(billing.router)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
