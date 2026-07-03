"""ILLUSTRATIVE X12 5010 835 (remittance advice) serializer + parser.

⚠️  A teaching implementation, NOT a certified EDI translator. It emits and
parses a simplified, self-consistent subset of the 835 (BPR / TRN / CLP / CAS /
SVC) so payment posting exercises a real wire format both ways. A production
adapter would replace this with the vendor's certified translator.

Delimiters: ``*`` element, ``~`` segment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

ELEMENT = "*"
SEGMENT = "~"

# CLP02 — claim status code (subset). 1 = processed as primary (paid), 4 = denied.
CLP_PAID = "1"
CLP_DENIED = "4"


@dataclass
class Adjustment:
    group: str        # CAS01: CO (contractual), PR (patient responsibility), etc.
    reason_code: str  # CAS02: CARC, e.g. 45 (over fee schedule), 97, 16
    amount: Decimal


@dataclass
class RemitResult:
    claim_control_number: str
    charged_amount: Decimal
    paid_amount: Decimal
    patient_responsibility: Decimal
    denied: bool
    adjustments: list[Adjustment] = field(default_factory=list)
    denial_codes: list[str] = field(default_factory=list)


def _seg(*elements: str) -> str:
    parts = [e if e is not None else "" for e in elements]
    while len(parts) > 1 and parts[-1] == "":
        parts.pop()
    return ELEMENT.join(parts) + SEGMENT


def build_835(result: RemitResult, payer_name: str, control: str = "000000001") -> str:
    """Serialize a remittance result to an illustrative X12 835 (inverse of parse)."""
    status = CLP_DENIED if result.denied else CLP_PAID
    segs = [
        _seg("BPR", "I", str(result.paid_amount), "C", "ACH"),
        _seg("TRN", "1", control),
        _seg("N1", "PR", payer_name),
        _seg(
            "CLP", result.claim_control_number, status, str(result.charged_amount),
            str(result.paid_amount), str(result.patient_responsibility),
        ),
    ]
    for adj in result.adjustments:
        segs.append(_seg("CAS", adj.group, adj.reason_code, str(adj.amount)))

    body = "".join(segs)
    st = _seg("ST", "835", control)
    se = _seg("SE", str(body.count(SEGMENT) + 2), control)
    gs = _seg("GS", "HP", "PAYER", "BILLPOP", "20260801", "1200", control, "X",
              "005010X221A1")
    ge = _seg("GE", "1", control)
    isa = _seg("ISA", "00", "          ", "00", "          ", "ZZ",
               "CLEARINGHOUSE  ", "ZZ", "BILLPOP        ", "260801", "1200",
               "^", "00501", control.zfill(9), "0", "P", ":")
    iea = _seg("IEA", "1", control.zfill(9))
    return isa + gs + st + body + se + ge + iea


def parse_835(edi: str) -> RemitResult:
    """Parse an illustrative X12 835 back into a RemitResult."""
    charged = paid = patient = Decimal("0")
    control = ""
    denied = False
    adjustments: list[Adjustment] = []

    for seg in (s for s in edi.split(SEGMENT) if s):
        el = seg.split(ELEMENT)
        tag = el[0]
        if tag == "CLP":
            control = _get(el, 1)
            denied = _get(el, 2) == CLP_DENIED
            charged = _dec(_get(el, 3))
            paid = _dec(_get(el, 4))
            patient = _dec(_get(el, 5))
        elif tag == "CAS":
            adjustments.append(
                Adjustment(group=_get(el, 1), reason_code=_get(el, 2),
                           amount=_dec(_get(el, 3)))
            )

    # Denial reason codes are the contractual/other adjustments on a denied claim.
    denial_codes = (
        [a.reason_code for a in adjustments] if denied else []
    )
    return RemitResult(
        claim_control_number=control,
        charged_amount=charged,
        paid_amount=paid,
        patient_responsibility=patient,
        denied=denied,
        adjustments=adjustments,
        denial_codes=denial_codes,
    )


def _get(el: list[str], idx: int) -> str:
    return el[idx] if idx < len(el) else ""


def _dec(value: str) -> Decimal:
    return Decimal(value) if value else Decimal("0")
