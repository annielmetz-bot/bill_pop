"""ILLUSTRATIVE X12 5010 270/271 serialization.

⚠️  This is a teaching/demonstration implementation, NOT a certified EDI
translator. It emits and parses a simplified, self-consistent subset of the
270/271 transaction sets so the eligibility pipeline exercises a real wire
format end to end. A production clearinghouse adapter (Availity/Waystar/Change)
would replace this with the vendor's certified translator or JSON API — the
domain objects in ``models.py`` stay the same.

Delimiters follow X12 convention: ``*`` element, ``~`` segment.
"""

from __future__ import annotations

from decimal import Decimal

from app.eligibility.models import (
    BenefitLine,
    EligibilityRequest,
    EligibilityResponse,
)
from app.models.enums import EligibilityStatus

ELEMENT = "*"
SEGMENT = "~"

# 271 EB01 — Eligibility or Benefit Information code (subset).
EB_ACTIVE = "1"
EB_INACTIVE = "6"
EB_COPAY = "B"
EB_COINSURANCE = "A"
EB_DEDUCTIBLE = "C"

# X12 service-type-code → human label (subset; PAT codes provisional).
SERVICE_TYPE_NAMES = {
    "30": "Health Benefit Plan Coverage",
    "MH": "Mental Health",
    "A6": "Psychotherapy",
    "A4": "Psychiatric",
}


def _seg(*elements: str) -> str:
    """Join elements into a segment, trimming trailing empties."""
    parts = [e if e is not None else "" for e in elements]
    while len(parts) > 1 and parts[-1] == "":
        parts.pop()
    return ELEMENT.join(parts) + SEGMENT


def _control_envelope(body: str, txn_set: str, control: str = "000000001") -> str:
    """Wrap transaction-set body in ISA/GS/ST … SE/GE/IEA. Illustrative header."""
    st = _seg("ST", txn_set, control)
    se = _seg("SE", str(body.count(SEGMENT) + 2), control)
    gs = _seg("GS", "HS" if txn_set == "270" else "HB", "BILLPOP", "RECEIVER",
              "20260801", "1200", control, "X", "005010X279A1")
    ge = _seg("GE", "1", control)
    isa = _seg("ISA", "00", "          ", "00", "          ", "ZZ",
               "BILLPOP        ", "ZZ", "CLEARINGHOUSE  ", "260801", "1200",
               "^", "00501", control.zfill(9), "0", "P", ":")
    iea = _seg("IEA", "1", control.zfill(9))
    return isa + gs + st + body + se + ge + iea


def build_270(req: EligibilityRequest) -> str:
    """Serialize an eligibility inquiry to an illustrative X12 270."""
    sub = req.subscriber
    body = "".join(
        [
            _seg("BHT", "0022", "13", "BILLPOP270", "20260801", "1200"),
            _seg("HL", "1", "", "20", "1"),  # information source (payer)
            _seg("NM1", "PR", "2", req.payer_name, "", "", "", "", "PI",
                 req.payer_id or ""),
            _seg("HL", "2", "1", "21", "1"),  # information receiver (provider)
            _seg("NM1", "1P", "2", req.provider.name or "", "", "", "", "",
                 "XX", req.provider.npi or ""),
            _seg("HL", "3", "2", "22", "0"),  # subscriber
            _seg("NM1", "IL", "1", sub.last_name or "", sub.first_name or "",
                 "", "", "", "MI", sub.member_id),
            _seg("DMG", "D8", (sub.date_of_birth or "").replace("-", "")),
            _seg("EQ", req.service_type_code),
        ]
    )
    return _control_envelope(body, "270")


def build_271(req: EligibilityRequest, resp: EligibilityResponse) -> str:
    """Serialize a response to an illustrative X12 271 (inverse of parse_271)."""
    sub = req.subscriber
    segs = [
        _seg("BHT", "0022", "11", "BILLPOP271", "20260801", "1200"),
        _seg("HL", "1", "", "20", "1"),
        _seg("NM1", "PR", "2", req.payer_name, "", "", "", "", "PI",
             req.payer_id or ""),
        _seg("HL", "3", "1", "22", "0"),
        _seg("NM1", "IL", "1", sub.last_name or "", sub.first_name or "",
             "", "", "", "MI", sub.member_id),
    ]

    if resp.status is EligibilityStatus.NOT_FOUND:
        # 271 subscriber-not-found rejection.
        segs.append(_seg("AAA", "N", "", "75", "C"))
        return _control_envelope("".join(segs), "271")

    head = EB_ACTIVE if resp.status is EligibilityStatus.ACTIVE else EB_INACTIVE
    segs.append(_seg("EB", head, "IND", "30", "", resp.plan_name or ""))

    for b in resp.benefits:
        if b.copay is not None:
            segs.append(_seg("EB", EB_COPAY, "IND", b.service_type_code, "", "",
                             "", str(b.copay), "", _yn(b.in_network)))
        elif b.coinsurance_percent is not None:
            segs.append(_seg("EB", EB_COINSURANCE, "IND", b.service_type_code, "",
                             "", "", "", str(b.coinsurance_percent), _yn(b.in_network)))
        elif b.deductible_remaining is not None:
            segs.append(_seg("EB", EB_DEDUCTIBLE, "IND", b.service_type_code, "",
                             "", "", str(b.deductible_remaining), "", _yn(b.in_network)))
        else:
            segs.append(_seg("EB", head, "IND", b.service_type_code, "", "", "",
                             "", "", _yn(b.in_network)))
    return _control_envelope("".join(segs), "271")


def parse_271(edi: str) -> EligibilityResponse:
    """Parse an illustrative X12 271 back into an EligibilityResponse."""
    segments = [s for s in edi.split(SEGMENT) if s]
    status = EligibilityStatus.INACTIVE
    plan_name: str | None = None
    benefits: list[BenefitLine] = []

    for seg in segments:
        el = seg.split(ELEMENT)
        tag = el[0]
        if tag == "AAA" and _get(el, 1) == "N":
            return EligibilityResponse(
                status=EligibilityStatus.NOT_FOUND, raw=edi
            )
        if tag != "EB":
            continue

        eb01 = _get(el, 1)
        stc = _get(el, 3)
        if eb01 == EB_ACTIVE and stc in ("", "30"):
            status = EligibilityStatus.ACTIVE
            plan_name = _get(el, 5) or plan_name
            continue
        if eb01 == EB_INACTIVE and stc in ("", "30"):
            status = EligibilityStatus.INACTIVE
            plan_name = _get(el, 5) or plan_name
            continue
        benefits.append(_eb_to_benefit(eb01, el))

    return EligibilityResponse(
        status=status, plan_name=plan_name, benefits=benefits, raw=edi
    )


def _eb_to_benefit(eb01: str, el: list[str]) -> BenefitLine:
    stc = _get(el, 3)
    kwargs: dict = {
        "service_type_code": stc,
        "service_type": SERVICE_TYPE_NAMES.get(stc, "Unknown"),
        "in_network": _yn_parse(_get(el, 9)),
    }
    if eb01 == EB_COPAY:
        kwargs["coverage"] = "copay"
        kwargs["copay"] = _dec(_get(el, 7))
    elif eb01 == EB_COINSURANCE:
        kwargs["coverage"] = "coinsurance"
        kwargs["coinsurance_percent"] = _dec(_get(el, 8))
    elif eb01 == EB_DEDUCTIBLE:
        kwargs["coverage"] = "deductible"
        kwargs["deductible_remaining"] = _dec(_get(el, 7))
    else:
        kwargs["coverage"] = "active" if eb01 == EB_ACTIVE else "inactive"
    return BenefitLine(**kwargs)


def _get(el: list[str], idx: int) -> str:
    return el[idx] if idx < len(el) else ""


def _dec(value: str) -> Decimal | None:
    return Decimal(value) if value else None


def _yn(value: bool | None) -> str:
    return "" if value is None else ("Y" if value else "N")


def _yn_parse(value: str) -> bool | None:
    return None if value == "" else value == "Y"
