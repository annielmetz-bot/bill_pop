"""ILLUSTRATIVE X12 5010 837P (professional claim) serializer.

⚠️  A teaching implementation, NOT a certified EDI translator. It emits a
simplified, self-consistent subset of the 837P transaction so the claims
pipeline produces a real wire artifact end to end. A production clearinghouse
adapter would replace this with the vendor's certified translator or API.

Delimiters: ``*`` element, ``~`` segment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

ELEMENT = "*"
SEGMENT = "~"


@dataclass
class ServiceLine:
    code: str
    charge: Decimal
    units: int
    service_date: str | None = None  # YYYYMMDD


@dataclass
class Encounter:
    claim_control_number: str
    total_charge: Decimal
    payer_name: str
    member_id: str
    provider_npi: str
    provider_name: str = ""
    diagnosis_codes: list[str] = field(default_factory=list)
    lines: list[ServiceLine] = field(default_factory=list)


def _seg(*elements: str) -> str:
    parts = [e if e is not None else "" for e in elements]
    while len(parts) > 1 and parts[-1] == "":
        parts.pop()
    return ELEMENT.join(parts) + SEGMENT


def build_837(enc: Encounter, control: str = "000000001") -> str:
    """Serialize an encounter to an illustrative X12 837P claim."""
    body_segs = [
        _seg("BHT", "0019", "00", enc.claim_control_number, "20260801", "1200", "CH"),
        # 1000A submitter / 1000B receiver
        _seg("NM1", "41", "2", "BILL POP", "", "", "", "", "46", "BILLPOP"),
        _seg("NM1", "40", "2", enc.payer_name, "", "", "", "", "46", "CLEARINGHOUSE"),
        # 2000A / 2010AA billing provider
        _seg("HL", "1", "", "20", "1"),
        _seg("NM1", "85", "2", enc.provider_name or "RENDERING PROVIDER", "", "", "",
             "", "XX", enc.provider_npi),
        # 2000B / 2010BA subscriber + 2010BB payer
        _seg("HL", "2", "1", "22", "0"),
        _seg("SBR", "P", "18", "", "", "", "", "", "", "MC"),
        _seg("NM1", "IL", "1", "", "", "", "", "", "MI", enc.member_id),
        _seg("NM1", "PR", "2", enc.payer_name, "", "", "", "", "PI", "CLEARINGHOUSE"),
        # 2300 claim
        _seg("CLM", enc.claim_control_number, str(enc.total_charge), "", "", "11:B:1",
             "Y", "A", "Y", "Y"),
        _seg("HI", *[f"ABK:{d}" for d in enc.diagnosis_codes]) if enc.diagnosis_codes
        else "",
    ]
    # 2400 service lines
    for i, line in enumerate(enc.lines, start=1):
        body_segs.append(_seg("LX", str(i)))
        body_segs.append(
            _seg("SV1", f"HC:{line.code}", str(line.charge), "UN", str(line.units))
        )
        if line.service_date:
            body_segs.append(_seg("DTP", "472", "D8", line.service_date))

    body = "".join(s for s in body_segs if s)
    st = _seg("ST", "837", control, "005010X222A1")
    se = _seg("SE", str(body.count(SEGMENT) + 2), control)
    gs = _seg("GS", "HC", "BILLPOP", "RECEIVER", "20260801", "1200", control, "X",
              "005010X222A1")
    ge = _seg("GE", "1", control)
    isa = _seg("ISA", "00", "          ", "00", "          ", "ZZ",
               "BILLPOP        ", "ZZ", "CLEARINGHOUSE  ", "260801", "1200",
               "^", "00501", control.zfill(9), "0", "P", ":")
    iea = _seg("IEA", "1", control.zfill(9))
    return isa + gs + st + body + se + ge + iea
