"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — e-Courts CNR lookup (Day 12 of teardown extension)              ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Look up Indian case-status by CNR (Case Number Record) number.

A CNR is the 16-character national identifier assigned by the e-Courts
project to every case filed in India.  Format:

    SCCC NN NNNNNN YYYY
    └──┘ └─┘ └────┘ └──┘
     │    │    │     └── filing year (e.g. 2024)
     │    │    └──────── 6-digit case number within the unit
     │    └───────────── 2-digit unit code (district / taluka court)
     └────────────────── 4-char state-court code (e.g. MHCC for Mumbai City Civil)

Examples:  MHCC010012342024 — Mumbai City Civil, case 1234/2024
           DLST020056782023 — Delhi Saket, case 5678/2023

REAL INTEGRATION:
  e-Courts publishes case-status data at https://services.ecourts.gov.in/
  but no official JSON API exists yet — scraping or paid third-party
  providers (ekosystems, courtroom IndIA) are the production paths.
  This module exposes a `fetch_cnr_status()` function with a documented
  hook (`_PROVIDER`) so the real scraper / API call can be wired in
  without touching the rest of the app.

For dev / demo, we ship a small synthetic dataset of plausible CNRs so
the UI flow can be developed and demoed without depending on a flaky
network call.  Set ECOURTS_PROVIDER=stub (default) or 'live' (when a
real adapter is registered).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# CNR format validation regex.  Strict — rejects obviously bad input.
CNR_RE = re.compile(r"^[A-Z]{4}\d{2}\d{6}\d{4}$")


def is_valid_cnr(cnr: str) -> bool:
    if not cnr:
        return False
    return bool(CNR_RE.match(cnr.strip().upper()))


def normalize_cnr(cnr: str) -> str:
    """Strip whitespace, uppercase, remove dashes/slashes."""
    return re.sub(r"[^A-Z0-9]", "", (cnr or "").upper())


@dataclass
class HearingEvent:
    date: str          # YYYY-MM-DD
    purpose: str       # 'Filed', 'Notice issued', 'Charge framed', 'Hearing', etc.
    description: str = ""


@dataclass
class CnrStatus:
    cnr: str
    case_type: str           # 'Criminal Misc.', 'CC' (Criminal Complaint), 'SC' (Sessions Case), etc.
    case_number: str         # 'CC/1234/2024'
    filing_date: str
    next_hearing_date: str
    status: str              # 'pending' | 'disposed' | 'transferred'
    court: str
    judge: str
    petitioner: str
    respondent: str
    sections: list[str] = field(default_factory=list)   # BNS / BNSS / BSA sections invoked
    hearings: list[HearingEvent] = field(default_factory=list)
    last_order_date: str = ""
    last_order_summary: str = ""
    fetched_at: str = ""
    source: str = "stub"     # 'stub' | 'ecourts.gov.in' | 'provider-X'

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hearings"] = [asdict(h) for h in self.hearings]
        return d


# ════════════════════════════════════════════════════════════════════════════
# Stub provider — small synthetic dataset for dev/demos.
# ════════════════════════════════════════════════════════════════════════════
_STUB_CASES: dict[str, CnrStatus] = {
    "MHCC010012342024": CnrStatus(
        cnr="MHCC010012342024",
        case_type="Sessions Case",
        case_number="SC/1234/2024",
        filing_date="2024-08-14",
        next_hearing_date="2026-05-22",
        status="pending",
        court="Sessions Court, Mumbai City",
        judge="Hon'ble Smt. Anjali Deshmukh, ASJ",
        petitioner="State of Maharashtra",
        respondent="Suresh Patil",
        sections=["BNS 304", "BNS 309", "BNSS 480"],
        last_order_date="2026-04-30",
        last_order_summary="Bail application of accused rejected. Charge to be framed on next date.",
        hearings=[
            HearingEvent("2024-08-14", "Filed",         "FIR filed at MG Road PS, registered as CR 482/2024"),
            HearingEvent("2024-09-02", "Notice issued", "Summons under BNSS 63 to accused"),
            HearingEvent("2024-11-18", "Bail rejected", "Magistrate denied bail; remand extended"),
            HearingEvent("2025-02-04", "Charge sheet",  "Charge sheet filed under BNS 304, 309"),
            HearingEvent("2025-08-15", "Charge framed", "Charge framed by Sessions Court"),
            HearingEvent("2026-04-30", "Bail (HC)",     "HC bail application also rejected"),
        ],
        source="stub",
    ),
    "DLST020056782023": CnrStatus(
        cnr="DLST020056782023",
        case_type="Criminal Complaint",
        case_number="CC/5678/2023",
        filing_date="2023-04-22",
        next_hearing_date="2026-06-10",
        status="pending",
        court="MM Court, Saket, Delhi",
        judge="Hon'ble Sh. Rakesh Sharma, MM",
        petitioner="Priya Sharma",
        respondent="Vikram Mehta",
        sections=["BNS 85", "BNS 84", "BNSS 528"],
        last_order_date="2026-04-12",
        last_order_summary="Quashing application under BNSS 528 listed; parties to file written submissions.",
        hearings=[
            HearingEvent("2023-04-22", "Filed",         "Private complaint under BNS 85 (matrimonial cruelty)"),
            HearingEvent("2023-07-14", "Cognizance",    "Magistrate took cognizance; summons issued"),
            HearingEvent("2024-01-05", "Mediation",     "Referred to mediation; matter not settled"),
            HearingEvent("2025-09-30", "Quash filed",   "Accused filed quashing petition in HC under BNSS 528"),
        ],
        source="stub",
    ),
    "KAHC030098762022": CnrStatus(
        cnr="KAHC030098762022",
        case_type="Criminal Misc.",
        case_number="Crl.M.P./9876/2022",
        filing_date="2022-11-08",
        next_hearing_date="",
        status="disposed",
        court="High Court of Karnataka, Bengaluru",
        judge="Hon'ble Sh. Justice K. Rao",
        petitioner="Aarti N.",
        respondent="State of Karnataka",
        sections=["BNS 143", "BNSS 482"],
        last_order_date="2024-03-27",
        last_order_summary="Anticipatory bail granted with conditions. Petition disposed of.",
        hearings=[
            HearingEvent("2022-11-08", "Filed",         "Anticipatory bail under CrPC 438 (now BNSS 482)"),
            HearingEvent("2023-01-19", "Notice",        "Notice to State"),
            HearingEvent("2024-03-27", "AB granted",    "Anticipatory bail granted; surety ₹1L"),
        ],
        source="stub",
    ),
}


def _stub_lookup(cnr: str) -> Optional[CnrStatus]:
    return _STUB_CASES.get(cnr)


# ════════════════════════════════════════════════════════════════════════════
# Provider dispatch — swap _PROVIDER to 'live' once a real adapter ships.
# ════════════════════════════════════════════════════════════════════════════
def _live_lookup(cnr: str) -> Optional[CnrStatus]:
    """
    Production hook.  Wire one of:
      - Direct scrape of services.ecourts.gov.in (fragile, may need CAPTCHA solving)
      - Paid third-party (Kanoon Pro, Civics, others)
      - Internal e-Courts API once they publish JSON

    Returns None if not configured so the UI gracefully falls back to the stub.
    """
    return None


def fetch_cnr_status(cnr: str) -> Optional[dict]:
    """Single entry point used by the route.  Returns a JSON-ready dict or None."""
    cnr = normalize_cnr(cnr)
    if not is_valid_cnr(cnr):
        return None

    provider = os.getenv("ECOURTS_PROVIDER", "stub").lower()
    result = None
    if provider == "live":
        result = _live_lookup(cnr)
    if not result:
        result = _stub_lookup(cnr)
    if not result:
        return None

    result.fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result.to_dict()


# ════════════════════════════════════════════════════════════════════════════
# Convenience — list demo CNRs the UI can suggest as "Try one of these".
# ════════════════════════════════════════════════════════════════════════════
def demo_cnrs() -> list[dict]:
    return [
        {
            "cnr": cnr,
            "label": f"{c.case_type} · {c.petitioner} v {c.respondent}",
            "court": c.court,
            "next_hearing_date": c.next_hearing_date,
        }
        for cnr, c in _STUB_CASES.items()
    ]
