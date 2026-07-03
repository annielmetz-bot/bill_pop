"""Claims layer — assembly, scrubbing, 837 submission, and (C3) remittance.

Like eligibility, the clearinghouse is reached through a swappable gateway; only
a deterministic sandbox exists until a vendor is chosen (spec Q2). The X12 837
serializer here is illustrative, not a certified translator.
"""
