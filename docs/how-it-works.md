# How Bill Pop Works — in Plain English

_A non-technical explanation of what we're building and how the pieces fit
together. For the full technical spec see `BILL_POP_SPEC.md`._

## The one-sentence version

Bill Pop takes the notes a psychedelic-assisted-therapy clinic already writes
about each patient visit, figures out how to bill insurance for that care, and
handles the whole back-and-forth with the insurer — so the clinic gets paid
without a billing department.

## The problem we're solving

Clinics that offer psychedelic-assisted therapy (starting with psilocybin in
New Mexico) run their day-to-day on platforms called **Homecoming** or
**Althea**. Those tools are great at scheduling, intake forms, and taking
cash payments — but neither of them can bill **insurance**. Insurance billing
is its own specialized, paperwork-heavy world, and right now these clinics
either do it by hand or don't do it at all.

Bill Pop is the missing piece: the "insurance engine" that sits behind the
clinic's existing system and does the billing work for them.

## The five stages of care (why "phases" matter)

A course of this therapy isn't one appointment — it's a journey with distinct
stages, and **insurance pays differently for each one**:

1. **Screening** — is this patient a good, safe candidate?
2. **Preparation** — getting the patient ready for the dosing session.
3. **Administration** — the dosing session itself.
4. **Monitoring** — watching over the patient after the dose (checking vital
   signs, keeping them safe as the medicine wears off).
5. **Integration** — follow-up sessions to make sense of the experience.

Each stage has its own billing code and its own paperwork requirements. Stage 4
(**Monitoring**) is the one we watch most carefully — it needs specific proof
(a licensed clinician was present, vital signs were recorded, how long it
lasted), and it's the stage most likely to be missing details in the clinic's
notes. More on why that matters below.

## How a visit becomes a paid claim

Think of Bill Pop as an assembly line. A patient visit goes in one end, and a
paid insurance claim comes out the other. Here are the stations on that line —
the **first two are built today**; the rest are on the roadmap.

### Station 1 — Intake (✅ built)

The clinic gets its records into Bill Pop. Because Homecoming and Althea don't
yet offer a direct connection, this works two ways:

- **Manual entry** — clinic staff type in the visit details (who, which stage,
  when, notes, vitals). This is built first on purpose, because the pilot clinic
  needs it to go live no matter what.
- **File upload** — the clinic exports a spreadsheet (CSV) and uploads it.

Whatever comes in, Bill Pop **keeps the original untouched** and then translates
it into one standard internal format. That translation step is where the
system's smarts live — and it's deliberately built so that when we eventually
learn exactly what a Homecoming or Althea export looks like, we only adjust a
small "translation table," not rebuild anything.

**The most important rule here:** if a record is missing something needed to
bill it properly — say a Monitoring visit with no vital signs recorded — Bill
Pop **flags it for a human to fix** rather than quietly billing it wrong.
Under-billing loses the clinic money; mis-billing can cause compliance trouble.
So Bill Pop's instinct is always "raise your hand," never "guess."

### Station 2 — Eligibility check (✅ built)

Before doing the work of building a claim, Bill Pop asks the patient's insurance
a simple question: **"Is this person covered, and what will you pay for?"**

This is a standardized electronic conversation in the insurance world (the
request is called a "270," the answer a "271"). Bill Pop sends the question,
reads the answer, and records what the plan covers — copays, deductibles,
what's in-network.

Two practical notes:
- Insurers are reached through a middleman service called a **clearinghouse**.
  We haven't picked which one yet, so Bill Pop is built to plug into any of them
  later without changes. For now it runs against a **practice ("sandbox")
  version** that returns realistic answers so we can build and test the whole
  flow safely.
- Every question and answer is **saved for the record**, because healthcare
  rules require us to keep an audit trail of everything.

### Stations 3–7 — coming next (on the roadmap)

- **Coding** — pick the exact billing codes for each stage of care.
- **Prior authorization** — get the insurer's advance approval when required.
- **Claims** — send the actual bill (an "837") and check it for errors first.
- **Remittance & appeals** — read the insurer's payment/denial response (an
  "835"), and when something's denied, auto-draft the appeal.
- **Posting & reporting** — record what was paid, flag underpayments, and give
  the clinic clear revenue reports.

## Why it's built the way it is

A few deliberate choices worth understanding, because they protect the clinic:

- **The rules are data, not code.** New Mexico's Medicaid board is still
  finalizing the exact billing rules for psilocybin therapy, and they'll keep
  changing through 2026–2027. So Bill Pop treats those rules like entries in a
  settings table that can be updated as they change — not something buried in
  software that needs a rebuild each time.
- **Everything's a swappable module.** The clinic's source system, the
  clearinghouse — these aren't decided or are subject to change, so each is a
  plug-in that can be replaced without disturbing the rest.
- **Today's numbers are clearly marked "provisional."** Until the official code
  list and rates are published, Bill Pop ships with clearly-labeled placeholders
  so nothing accidentally gets treated as final.
- **Privacy and audit come first.** Patient data is sensitive health
  information. Everything is logged, nothing sensitive is stored in the open,
  and a clinic isn't switched on until the proper privacy agreement is signed.

## Where we are today

Two of the seven stations are built and tested end-to-end: **getting records in
and normalized (with smart flagging of anything incomplete)**, and **checking
insurance eligibility**. The foundation underneath — the database, the care-stage
model, the provisional New Mexico rules — is in place. The remaining stations
(coding, claims, payments, reporting) come month by month, aiming at a December
2026 go-live alongside New Mexico's soft launch.
