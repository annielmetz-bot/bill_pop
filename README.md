# Bill Pop

Billing automation agent for **psychedelic-assisted therapy (PAT) clinics**.
It's the insurance coding/claims engine downstream of the clinic's system of
record (Homecoming or Althea) — not a clinical or scheduling app.

> **Status: July 2026 — Month 1 of 6 (data model & schema).**
> This repo currently contains the database schema, SQLAlchemy models, the
> initial Alembic migration, and provisional seed data. Intake, eligibility,
> coding, claims, remittance, posting, and reporting layers arrive in later
> months per the roadmap in `BILL_POP_SPEC.md`.

## Architecture (target)

1. Data Intake Layer — Homecoming/Althea export parsing or manual entry
2. Coding Rules Engine — config-driven payer/code/documentation tables
3. Eligibility & Prior Auth — 270/271, PA packets
4. Claims — NCCI/modifier validation, 837 submission
5. Remittance & Denial — 835 parsing, denial classification, appeals
6. Payment Posting & Reconciliation
7. Reporting & Compliance — audit logging, revenue reports

### The four-phase model

`screening` (1) · `preparation` (2) · `administration` (3A) ·
`monitoring` (3B) · `integration` (4). Each phase maps to its own billing codes
and documentation requirements. **Phase 3B monitoring** is the one most likely
to be under-documented in exports, so its records are flagged rather than
silently under-coded.

## Data model (this month)

- **Clinical:** `Clinic → Client / Clinician → EpisodeOfCare → PhaseRecord →
  DocumentationRecord`. `PhaseRecord` is the core billable unit.
- **Coding config (data, not logic):** `Payer`, `BillingCode`, `PayerCodeRule`
  (versioned by `effective_date`), `DocumentationRequirement`.
- **Intake staging:** `IntakeBatch`, `IntakeRawRecord` (raw export held as
  loosely-typed JSONB until real export shapes are scoped).

See `docs/intake-export-gaps.md` for the open questions this schema
deliberately leaves as config/staging data.

## Tech

Python 3.11 · FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL (psycopg3).

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # set DATABASE_URL

alembic upgrade head          # create the schema
python -m app.seed.seed_data  # load PROVISIONAL NM Medicaid config

uvicorn app.main:app --reload # GET /health
```

> ⚠️ The seeded billing codes and rates are **provisional placeholders**
> pending the NM Medicaid Advisory Board's final list. Do not bill against them
> as-is. See `app/seed/seed_data.py` and `docs/intake-export-gaps.md` (Q3).

## HIPAA

Encryption at rest and in transit, audit logging on every claim touch, and a
signed BAA with each clinic and infrastructure provider are requirements, not
options. `.env` and any PHI are git-ignored; a clinic should not go live until
its `Clinic.baa_status = signed`.
