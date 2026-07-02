"""Eligibility & Benefits layer (EDI 270/271).

Vendor-agnostic by design: the app builds an ``EligibilityRequest``, hands it to
an ``EligibilityGateway``, and stores the ``EligibilityResponse``. The clearing-
house is still undecided (spec open-question Q2), so today only a deterministic
``SandboxGateway`` exists; a real Availity/Waystar/Change adapter drops in later
behind the same interface without touching callers.
"""
