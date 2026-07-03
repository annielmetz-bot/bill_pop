# Bill Pop

Billing automation agent for **psychedelic-assisted therapy (PAT) clinics**.
It's the insurance coding/claims engine downstream of the clinic's system of
record (Homecoming or Althea) — not a clinical or scheduling app.

> **Status: claims-first build.**
> Built so far: the schema + migrations + provisional seed data; the **Data
> Intake Layer v1** (manual entry + CSV, normalization into billable records
> with incomplete-record flagging); and the full **billing spine** — coding &
> charge capture → claim assembly, scrub & **837** submission → **835**
> remittance & payment posting (with underpayment flagging), all against a
> vendor-agnostic clearinghouse **sandbox**. **Eligibility & Benefits (270/271)**
> is also built but **deferred as a feature** — its gateway/EDI scaffolding is
> reused by the claims layer. Reporting arrives next per `BILL_POP_SPEC.md`.

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

## Data model

- **Clinical:** `Clinic → Client / Clinician → EpisodeOfCare → PhaseRecord →
  DocumentationRecord`. `PhaseRecord` is the core billable unit.
- **Coding config (data, not logic):** `Payer`, `BillingCode`, `PayerCodeRule`
  (versioned by `effective_date`), `DocumentationRequirement`.
- **Intake staging:** `IntakeBatch`, `IntakeRawRecord` (raw export held as
  loosely-typed JSONB until real export shapes are scoped).
- **Eligibility:** `EligibilityCheck` (270/271 result + parsed benefits + raw
  wire payloads for audit).

See `docs/intake-export-gaps.md` for the open questions the schema
deliberately leaves as config/staging data.

## Intake layer (Month 2)

Modular and swappable: **ingest** adapters (`app/intake/ingest.py`) land raw
export rows verbatim in `IntakeRawRecord`; **normalization**
(`app/intake/normalize.py`) maps them onto `PhaseRecord`/`DocumentationRecord`
via per-source field maps (`app/intake/mapping.py`) and runs a config-driven
completeness check (`app/services/completeness.py`). Incomplete records — Phase
3B monitoring missing vitals/time above all — are **flagged, not silently
under-coded**. Adding a Homecoming/Althea connector is a mapping-config change.

Endpoints: `POST /intake/batches`, `.../records` (manual), `.../import-csv`,
`.../normalize`, `GET /intake/batches/{id}` (summary + flagged records).

## Eligibility layer (Month 2)

Vendor-agnostic 270/271. The app builds an `EligibilityRequest`, hands it to an
`EligibilityGateway`, and stores an `EligibilityCheck`. The clearinghouse is
undecided (spec Q2), so only a deterministic **`SandboxGateway`** exists today;
a real Availity/Waystar/Change adapter drops in behind the same interface
(`ELIGIBILITY_GATEWAY` setting). `app/eligibility/x12.py` is an **illustrative**
(not certified) X12 270/271 serializer the sandbox round-trips through.

Endpoints: `POST /eligibility/checks`, `GET /eligibility/checks/{id}`,
`GET /clients/{id}/eligibility`.

## Billing spine (claims-first)

The end-to-end billing pipeline: **code → assemble → scrub → submit → post**.

- **Coding & charge capture** (`app/services/coding.py`) — turns each
  `READY_TO_CODE` PhaseRecord into a priced `Charge`, resolving the billing code
  and the effective-dated `PayerCodeRule` for the client's payer. No active rule
  → `needs_review`, never silently zero-priced.
- **Claim assembly, scrub & 837** (`app/services/claims_service.py`,
  `claim_scrub.py`) — groups coded charges into a `Claim`, validates it
  (required fields, duplicate lines), builds an **illustrative** X12 837P
  (`app/claims/x12_837.py`), and submits it through a swappable
  `ClaimsGateway` (sandbox today).
- **Remittance & posting** (`app/services/posting.py`, `app/claims/x12_835.py`)
  — reads the payer's **835**, records what was paid, classifies denials, and
  **flags underpayments vs. the contracted rate**.

Endpoints: `POST /episodes/{id}/code`, `GET /episodes/{id}/charges`,
`POST /claims`, `POST /claims/{id}/scrub`, `POST /claims/{id}/submit`,
`POST /claims/{id}/remittance`, `GET /claims/{id}`.

## Tech

Python 3.11 · FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL (psycopg3).

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # runtime + test deps (or requirements.txt for runtime only)

cp .env.example .env          # set DATABASE_URL

alembic upgrade head          # create the schema
python -m app.seed.seed_data  # load PROVISIONAL NM Medicaid config

uvicorn app.main:app --reload # GET /health, /docs

pytest                        # unit tests always run; DB-backed tests skip without Postgres
```

> ⚠️ The seeded billing codes and rates are **provisional placeholders**
> pending the NM Medicaid Advisory Board's final list. Do not bill against them
> as-is. See `app/seed/seed_data.py` and `docs/intake-export-gaps.md` (Q3).

## HIPAA

Encryption at rest and in transit, audit logging on every claim touch, and a
signed BAA with each clinic and infrastructure provider are requirements, not
options. `.env` and any PHI are git-ignored; a clinic should not go live until
its `Clinic.baa_status = signed`.
