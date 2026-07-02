"""Data Intake Layer.

Modular, swappable intake: ingest adapters land raw rows in
``IntakeRawRecord.raw_payload``; the normalizer maps them onto
``PhaseRecord``/``DocumentationRecord`` and flags incomplete records. Adding a
new source system (Homecoming, Althea) is a mapping-config change, not new code.
"""
