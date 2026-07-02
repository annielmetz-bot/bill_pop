"""FastAPI application entrypoint.

Month 1 is data model & schema. The app exposes only a health check for now;
intake, eligibility, coding, claims, remittance, posting, and reporting
routers arrive in later months per the roadmap.
"""

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="Bill Pop",
    description="Billing automation agent for psychedelic-assisted therapy clinics",
    version="0.1.0",
)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
