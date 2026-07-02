# Bill Pop — Billing Automation Agent

Built around clinics running Homecoming or Althea · July 2026 → December 2026

## What Bill Pop Is

Bill Pop is a **billing automation agent for psychedelic-assisted therapy (PAT)
clinics**. It is *not* a clinical or scheduling app — it's the insurance
coding/claims engine that sits downstream of the clinic's system of record.

The architecture is built for PAT broadly (psilocybin in New Mexico is just the
first modality/state it goes live with). The coding rules engine, layer
structure, and intake design are all meant to extend to additional PAT
modalities and states without a rebuild.

### Why it exists

Neither **Homecoming** nor **Althea** (the two clinic platforms Bill Pop
integrates with) is an insurance-claims engine, and neither publishes an open
developer API:

- **Homecoming** — intake, prep, integration, outcomes tracking; cash-pay
  billing via Stripe; scheduling via Calendly.
- **Althea** — client screening, state-specific compliance workflows, payment
  processing for licensed facilitators in OR/CO (free to facilitators).

Both are the clinical/financial system of record on the clinic's side, but
neither codes, submits, or manages insurance claims. Bill Pop has to pull
clinical documentation (diagnosis, session type, time, clinician credentials)
out of whichever platform a clinic uses and run its own coding + claims
pipeline independently.

Because there's no public API for either platform today, the near-term
integration path is a **data export/import layer** — CSV, PDF, or a
manual-entry portal for clinic staff — while a parallel vendor conversation
explores enterprise-tier API/webhook access. The intake layer is built as a
**swappable module** specifically so that if a vendor opens up direct access
later, only that one layer changes — not the coding, claims, or reporting
logic behind it.

## Architecture, Layer by Layer

1. **Data Intake Layer** — Homecoming/Althea export parsing (or manual entry)
   that normalizes clinical documentation into a common internal format,
   regardless of source system.
2. **Coding Rules Engine** — configuration-driven payer + code +
   documentation-requirement tables, built around the **four-phase model**
   (screening, preparation, administration/monitoring, integration) shared
   across PAT modalities rather than hard-coded, psilocybin-only logic.
3. **Eligibility & Prior Auth Layer** — 270/271 eligibility checks and PA
   packet assembly/tracking, run against a clearinghouse.
4. **Claims Layer** — NCCI/modifier validation and 837 claim submission via
   clearinghouse.
5. **Remittance & Denial Layer** — 835 parsing, denial classification, and
   auto-drafted appeals.
6. **Payment Posting & Reconciliation Layer** — posts payments/adjustments
   against the ledger and flags underpayments vs. contracted rates.
7. **Reporting & Compliance Layer** — audit logging of every claim touch,
   documentation-completeness checks, and client-facing revenue reports.

### The four-phase model

Referenced throughout as "Phase 1/2/4" plus a split Phase 3:

- **Phase 1 — Screening**
- **Phase 2 — Preparation**
- **Phase 3A — Administration** (the dosing session itself)
- **Phase 3B — Monitoring** (post-dose clinical monitoring — needs
  licensed-clinician documentation, vitals, and time; this is called out as
  the phase most likely to be under-documented in exports)
- **Phase 4 — Integration**

Each phase maps to its own billing codes and documentation requirements —
this mapping is exactly what the Month 1 config tables need to represent.

## Build Sequence

| Month | Focus | What Gets Built |
|---|---|---|
| **July 2026** | Data model & schema | Design the phase-based documentation schema and payer/code/documentation config tables; scope exactly what Homecoming and Althea exports contain (fields, formats, gaps). |
| August 2026 | Intake layer + eligibility | Data Intake Layer v1 (structured import from exports, or manual-entry fallback); Eligibility & Benefits module (270/271) against a clearinghouse sandbox. |
| September 2026 | Coding engine + prior auth | Configuration-driven Coding & Charge Capture rules engine (Phase 1/2/4 codes, Phase 3B monitoring logic); Prior Authorization packet assembly and tracking. |
| October 2026 | Claims + denials | Claim scrubbing/validation and 837 submission via clearinghouse; 835 remittance parsing and denial classification with auto-drafted appeals. |
| November 2026 | Posting, reporting, dry run | Payment posting/reconciliation and compliance/reporting dashboards; audit logging and encryption; full end-to-end dry run on the pilot clinic's real export data. |
| December 2026 | Go-live & iterate | Go live alongside NM's soft launch; monitor first real claims/remittances closely; tighten coding rules and intake parsing based on real payer responses. |

**We are here: July 2026 — Month 1, data model & schema.**

## Homecoming & Althea Integration Track (parallel, non-blocking)

- Reach out to both vendors in July/August about enterprise export or webhook
  access — doesn't block the build, but could simplify the intake layer if
  either says yes.
- Data Intake Layer is a modular connector from day one, so a Homecoming
  connector and an Althea connector can sit side by side without touching
  coding/claims/reporting.
- Build the **manual-entry fallback first regardless** — needed for the pilot
  clinic's December go-live either way, and de-risks the roadmap if vendor
  access doesn't come through in time.
- Any PHI moved through manual exports still needs a **signed BAA** and secure
  transfer process with each clinic — treated the same as a live API
  integration from a compliance standpoint.

## Technical Standards to Build On

- **EDI transactions** — 270/271 (eligibility), 837 (claims), 835
  (remittance) — via a clearinghouse (Availity, Waystar, or Change
  Healthcare) rather than connecting to payers directly.
- **HL7/FHIR** — worth scoping if a true EHR-style integration becomes
  available later; not needed for the manual/export-based intake layer built
  now.
- **Configuration over hard-coding** — payer, code, and
  documentation-requirement tables should be *data*, not logic, so new NM
  codes and Medicaid rules can be added through 2026–2027 without a rebuild.
- **HIPAA by default** — encryption at rest and in transit, audit logging on
  every claim touch, and a signed BAA with whatever model/infrastructure
  provider powers the agent.

## Technical Risks to Watch

- No public API for Homecoming or Althea → intake layer starts
  manual/export-based; real capacity constraint on how many clinics can be
  onboarded at once until that changes.
- Vendor cooperation is not guaranteed — plan for the manual path to persist
  past December.
- Coding rules will keep changing as the **NM Medicaid Advisory Board**
  finalizes them through 2026–2027 — the rules engine needs to be *genuinely*
  swappable, not just theoretically configurable.
- Exported clinical documentation from Homecoming/Althea may not always
  contain everything needed to bill **Phase 3B monitoring** (licensed-clinician
  documentation, vitals, time) — the intake layer should **flag incomplete
  records rather than silently under-coding them**.

---

## Month 1 Data Model — Proposed Entities & Relationships

This is a starting proposal derived from the roadmap above, to unblock schema
work now. Two things called out in the roadmap are genuinely open —
**exactly what fields Homecoming/Althea exports contain**, and the **final NM
Medicaid code list** — neither is known yet, so the schema below treats both
as configuration/staging data rather than baking in assumptions.

### Core clinical entities

- **Clinic** — id, name, source_system (`homecoming` | `althea` | `manual`),
  baa_status, baa_signed_at, state (NM first).
- **Client** (the patient) — id, clinic_id, demographics, insurance/payer
  reference. PHI — encrypt at rest.
- **Clinician** — id, clinic_id, name, credentials/license type, NPI number.
- **EpisodeOfCare** — id, client_id, modality (`psilocybin`, future
  modalities), state, started_at. Groups the phases for one course of
  treatment.
- **PhaseRecord** (the core billable unit) — id, episode_id, phase
  (`screening`|`preparation`|`administration`|`monitoring`|`integration`),
  clinician_id, date, start_time, end_time, status
  (`documented`|`incomplete`|`ready_to_code`).
- **DocumentationRecord** — id, phase_record_id, diagnosis codes, session
  notes, vitals (for Phase 3B monitoring), time-in-session. This is what gets
  checked against `DocumentationRequirement` before a phase is codeable.

### Configuration tables (the "coding rules engine," data not logic)

- **Payer** — id, name, type (`medicaid`|`commercial`), state.
- **BillingCode** — id, code (CPT/HCPCS), phase, description,
  modality-applicable flags.
- **PayerCodeRule** — payer_id, billing_code_id, effective_date,
  end_date, rate/notes. This is the table the NM Medicaid Advisory Board
  changes will land in — versioned by effective date so old claims still
  reference the rule that was live when the service happened.
- **DocumentationRequirement** — payer_code_rule_id, required_field
  (e.g. "licensed-clinician signature," "vitals," "time-in-session"),
  required (bool). Used to validate a `PhaseRecord` is ready to code, and to
  flag Phase 3B gaps rather than silently under-coding.

### Intake / export staging (Month 1 also scopes this, doesn't build it yet)

- **IntakeBatch** — id, clinic_id, source_system, import_type
  (`csv`|`pdf`|`manual`), imported_at, raw_file_ref.
- **IntakeRawRecord** — id, batch_id, raw_payload (JSON — deliberately
  unstructured until we know actual Homecoming/Althea export shapes),
  normalization_status (`pending`|`normalized`|`flagged_incomplete`),
  linked `phase_record_id` once normalized.

Keeping raw export data as loosely-typed JSON in `IntakeRawRecord` (rather
than a rigid schema) is intentional — the Month 1 task explicitly includes
*scoping what the exports actually contain*, which isn't known yet. The
normalization step from raw → `PhaseRecord`/`DocumentationRecord` is where
that mapping logic will live once it's discovered, without forcing a schema
migration every time a new export field shows up.

### Open questions for the pilot clinic / vendors (not answerable from the doc alone)

1. Sample Homecoming and/or Althea exports (real or redacted) — field names,
   formats (CSV columns? PDF layout? manual portal form?).
2. Which clearinghouse (Availity / Waystar / Change Healthcare) is the
   pilot targeting, if decided yet — affects 270/271/837/835 format
   assumptions later, not Month 1 schema directly.
3. Confirmed NM Medicaid CPT/HCPCS codes per phase, if available yet, or
   whether Month 1 should ship with placeholder/example codes pending the
   Advisory Board's final list.

## Suggested Month 1 Deliverables

1. Python/FastAPI/PostgreSQL project scaffold (already in progress per your
   note).
2. SQLAlchemy models + Alembic migration for the entities above.
3. Seed/fixture data for `Payer`, `BillingCode`, `PayerCodeRule`,
   `DocumentationRequirement` using placeholder NM Medicaid codes, clearly
   marked as provisional pending the Advisory Board's list.
4. A short `docs/intake-export-gaps.md` capturing the three open questions
   above, so it's visible as a tracked gap rather than a silent assumption.
