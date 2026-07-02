# Intake & Export Gaps — Open Questions (Month 1)

_Status: open. Owner: pilot-clinic / vendor track. Last updated: July 2026._

Month 1 (data model & schema) deliberately treats two things as
**configuration / staging data** rather than baking assumptions into the
schema, because neither is known yet. This file tracks those gaps so they stay
visible instead of becoming silent assumptions.

## Q1 — What do Homecoming / Althea exports actually contain?

We need **sample exports (real or redacted)** from Homecoming and/or Althea to
scope:

- Field names and coverage — especially whether **Phase 3B monitoring** data
  (licensed-clinician documentation, vitals, time-in-session) is present at all.
- Format: CSV columns? PDF layout? Manual-entry portal form?
- Which of the entities in the data model each export can actually populate.

**Why the schema doesn't assume an answer:** `IntakeRawRecord.raw_payload` is
loosely-typed JSONB. Raw export rows land there untouched; the normalization
step (`pending → normalized | flagged_incomplete`) maps them onto
`PhaseRecord` / `DocumentationRecord` once the real shapes are known — no
migration required per new field. Incomplete records are **flagged, not
silently under-coded**.

## Q2 — Which clearinghouse is the pilot targeting?

Availity / Waystar / Change Healthcare. Affects 270/271/837/835 format
assumptions **later** (Aug–Oct), not the Month 1 schema directly. Recorded here
so the eligibility/claims work in following months has a decision to point at.

## Q3 — Confirmed NM Medicaid CPT/HCPCS codes per phase?

The NM Medicaid Advisory Board has **not** finalized the PAT code list as of
July 2026. Until it does:

- `BillingCode`, `PayerCodeRule`, and `DocumentationRequirement` are seeded with
  **provisional placeholder codes** (`app/seed/seed_data.py`), clearly marked
  `PROVISIONAL` in every description and note.
- `NM-PSIL-*` codes are Bill Pop-internal placeholders for services with no
  established CPT/HCPCS analog (preparation, administration, monitoring). The
  standard CPT codes used (`90791`, `90834`) are plausible analogs only —
  **not confirmed NM Medicaid-covered for PAT**.
- `PayerCodeRule` is **versioned by `effective_date`** so when the Advisory
  Board's real codes land, they are added as new rows; historical claims keep
  referencing the rule that was live when the service happened. No rewrite of
  the coding engine — it's data, not logic.

## Compliance note (not a code question, but a blocker)

Any PHI moved through manual exports needs a **signed BAA** and a secure
transfer process with each clinic — treated the same as a live API integration.
The `Clinic` model tracks this (`baa_status`, `baa_signed_at`); a clinic should
not go live until `baa_status = signed`.
