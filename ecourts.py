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

PROVIDERS (set via ECOURTS_PROVIDER):
  - 'stub' (default)  small synthetic dataset of plausible CNRs so the UI flow
                      can be demoed offline.  Every row carries source='stub'.
  - 'live'            a REAL lookup against a third-party e-Courts API.  Default
                      target is ecourtsindia.com's partner API
                      (webapi.ecourtsindia.com) — a JSON mirror of
                      services.ecourts.gov.in case data.  It is keyed; new
                      accounts get free signup credits (no card).  Configure:
                          ECOURTS_PROVIDER=live
                          ECOURTS_API_KEY=eci_live_xxxxxxxx
                          ECOURTS_API_BASE=https://webapi.ecourtsindia.com  (optional)
                          ECOURTS_API_PATH=/api/partner/case/{cnr}          (optional)
                      In live mode there is NO stub fallback: a miss or failure
                      returns "not found", so fake data is never shown as real.

  No *official* free JSON API exists — the gov portal is CAPTCHA-gated.  Because
  base/path/auth are env-configurable, a different provider (e.g.
  court-api.kleopatra.io) can be swapped in without code changes.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
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
def _live_api_config() -> tuple[str, Optional[str], str]:
    base = os.getenv("ECOURTS_API_BASE", "https://webapi.ecourtsindia.com").rstrip("/")
    token = os.getenv("ECOURTS_API_KEY")
    path = os.getenv("ECOURTS_API_PATH", "/api/partner/case/{cnr}")
    return base, token, path


def _first(d: dict, *keys: str, default: str = "") -> str:
    """First non-empty value among `keys`, coerced to a trimmed string."""
    for k in keys:
        v = d.get(k)
        if isinstance(v, (str, int)) and str(v).strip():
            return str(v).strip()
    return default


def _join_names(items: list) -> str:
    """Provider returns parties/judges as either string arrays or {name:...}."""
    out: list[str] = []
    for x in items or []:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
        elif isinstance(x, dict):
            n = _first(x, "name", "fullName", "partyName")
            if n:
                out.append(n)
    return "; ".join(out)


def _map_live_response(payload: dict, cnr: str, source: str) -> Optional[CnrStatus]:
    """
    Map a provider's JSON envelope to CnrStatus.  Pure + defensive: returns None
    if the payload has no recognizable case object, so a malformed/empty response
    becomes an honest "not found" rather than fabricated data.

    Field names follow the ecourtsindia.com partner-API docs (June 2026); the
    `.get()` fallbacks tolerate minor shape differences across providers.
    Validate against a real response on first use.
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    c = data.get("courtCaseData") or data.get("caseDetails") or data
    if not isinstance(c, dict) or not (c.get("cnr") or c.get("caseNumber")):
        return None

    status_raw = _first(c, "caseStatus", "status").lower()
    status = ("disposed" if "dispos" in status_raw
              else "pending" if "pend" in status_raw
              else (status_raw or "unknown"))

    hearings: list[HearingEvent] = []
    for h in (c.get("historyOfCaseHearings") or c.get("hearings") or []):
        if isinstance(h, dict):
            hearings.append(HearingEvent(
                date=_first(h, "hearingDate", "businessDate", "date"),
                purpose=_first(h, "purpose", "hearingPurpose", "stage"),
                description=_first(h, "description", "businessOnDate", "cause"),
            ))

    sections: list[str] = []
    for a in (c.get("acts") or c.get("actsAndSections") or []):
        if isinstance(a, dict):
            s = _first(a, "section", "under_section", "sections")
            if s:
                sections.append(s)
        elif isinstance(a, str) and a.strip():
            sections.append(a.strip())

    court = (_first(c, "courtName", "court", "establishmentName")
             or ", ".join(p for p in (_first(c, "district"), _first(c, "state")) if p))

    return CnrStatus(
        cnr=c.get("cnr") or cnr,
        case_type=_first(c, "caseType", "type"),
        case_number=_first(c, "caseNumber", "caseNo"),
        filing_date=_first(c, "filingDate", "filing_date"),
        next_hearing_date=_first(c, "nextHearingDate", "next_hearing_date"),
        status=status,
        court=court,
        judge=_join_names(c.get("judges") or []) or _first(c, "judge"),
        petitioner=_join_names(c.get("petitioners") or []),
        respondent=_join_names(c.get("respondents") or []),
        sections=sections,
        hearings=hearings,
        last_order_date=_first(c, "decisionDate", "lastHearingDate"),
        last_order_summary=_first(c, "caseStage", "stage"),
        source=source,
    )


def _live_lookup(cnr: str) -> Optional[CnrStatus]:
    """
    Real CNR lookup against the configured provider (default:
    webapi.ecourtsindia.com).  Returns None on ANY failure — no key, network
    error, 404, or unparseable body — so the route degrades to "not found"
    instead of inventing data.
    """
    base, token, path = _live_api_config()
    if not token:
        print("[ecourts] ECOURTS_PROVIDER=live but ECOURTS_API_KEY is unset; "
              "cannot perform a real lookup.", file=sys.stderr)
        return None
    url = base + path.format(cnr=cnr)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Lex-Indic/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[ecourts] live lookup HTTP {e.code} for {cnr}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001 — network/JSON errors must not 500 the route
        print(f"[ecourts] live lookup failed for {cnr}: {e}", file=sys.stderr)
        return None
    host = urllib.parse.urlparse(base).netloc or "live"
    return _map_live_response(payload, cnr, host)


def fetch_cnr_status(cnr: str) -> Optional[dict]:
    """Single entry point used by the route.  Returns a JSON-ready dict or None."""
    cnr = normalize_cnr(cnr)
    if not is_valid_cnr(cnr):
        return None

    provider = os.getenv("ECOURTS_PROVIDER", "stub").lower()
    if provider == "live":
        # NO stub fallback in live mode — a missed/failed real lookup returns
        # "not found", so synthetic data is never presented as if it were real.
        result = _live_lookup(cnr)
    else:
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
