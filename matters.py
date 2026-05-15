"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Matter intake registry (Day 9)                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Lightweight firm/lawyer/matter triple registry stored as JSON on disk.
A "matter" is a unique case file inside a firm; every /analyze call may be
optionally tagged with a matter_id so analyses, PDFs, and audit records are
threaded under one case folder.

WHY: A real firm runs hundreds of cases in parallel. Saving artefacts as
flat timestamped files in outputs/ doesn't scale; case-management is the
first thing a partner asks about during demos.  This module lets the firm
register matters once, then file every subsequent analysis under that ID
with a conflict-check + status field.

This is deliberately NOT a Postgres-backed full case-management system.
Day-10 adds multi-tenant auth on top; eventual move to Postgres is
mechanical because the dataclass schema is the same shape as a SQL row.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

_FIRMS_PATH    = Path("outputs") / "matters" / "firms.json"
_LAWYERS_PATH  = Path("outputs") / "matters" / "lawyers.json"
_MATTERS_PATH  = Path("outputs") / "matters" / "matters.json"


@dataclass
class Firm:
    id: str
    name: str                  # "Singhania & Partners"
    address: str = ""
    created_at: str = ""

@dataclass
class Lawyer:
    id: str
    firm_id: str
    full_name: str
    bar_council_no: str = ""
    email: str = ""
    role: str = "associate"    # partner | senior_associate | associate | paralegal
    created_at: str = ""

@dataclass
class Matter:
    id: str                    # human-friendly: FIRM/2026/0042
    firm_id: str
    lawyer_id: str
    client_name: str           # the firm's client
    opposing_party: str = ""   # for conflict-of-interest checks
    matter_type: str = ""      # 'criminal', 'matrimonial', 'POCSO', etc.
    status: str = "open"       # open | filed | settled | closed
    description: str = ""
    created_at: str = ""
    updated_at: str = ""


# ─── Persistence helpers ────────────────────────────────────────────────────
def _load(path: Path, cls):
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [cls(**r) for r in raw]


def _save(path: Path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(i) for i in items], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_firms()   -> list[dict]: return [asdict(f) for f in _load(_FIRMS_PATH, Firm)]
def list_lawyers() -> list[dict]: return [asdict(l) for l in _load(_LAWYERS_PATH, Lawyer)]
def list_matters() -> list[dict]: return [asdict(m) for m in _load(_MATTERS_PATH, Matter)]


# ─── Firm CRUD ──────────────────────────────────────────────────────────────
def add_firm(name: str, address: str = "") -> dict:
    firms = _load(_FIRMS_PATH, Firm)
    if not name.strip():
        raise ValueError("Firm name is required.")
    if any(f.name.lower() == name.strip().lower() for f in firms):
        raise ValueError("A firm with that name already exists.")
    new = Firm(
        id=f"firm_{uuid.uuid4().hex[:10]}",
        name=name.strip()[:120],
        address=address.strip()[:200],
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    firms.append(new)
    _save(_FIRMS_PATH, firms)
    return asdict(new)


# ─── Lawyer CRUD ────────────────────────────────────────────────────────────
def add_lawyer(firm_id: str, full_name: str, bar_council_no: str = "",
               email: str = "", role: str = "associate") -> dict:
    firms = _load(_FIRMS_PATH, Firm)
    if not any(f.id == firm_id for f in firms):
        raise ValueError("Unknown firm.")
    if not full_name.strip():
        raise ValueError("Lawyer name is required.")
    if role not in ("partner", "senior_associate", "associate", "paralegal"):
        raise ValueError("Invalid role.")
    lawyers = _load(_LAWYERS_PATH, Lawyer)
    new = Lawyer(
        id=f"lwy_{uuid.uuid4().hex[:10]}",
        firm_id=firm_id,
        full_name=full_name.strip()[:120],
        bar_council_no=bar_council_no.strip()[:30],
        email=email.strip().lower()[:120],
        role=role,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    lawyers.append(new)
    _save(_LAWYERS_PATH, lawyers)
    return asdict(new)


# ─── Matter CRUD ────────────────────────────────────────────────────────────
def _next_matter_seq(firm_id: str, year: int) -> int:
    matters = _load(_MATTERS_PATH, Matter)
    pat = re.compile(rf"^[A-Z]+/{year}/(\d+)$")
    seq = 0
    for m in matters:
        if m.firm_id != firm_id:
            continue
        match = pat.match(m.id)
        if match:
            seq = max(seq, int(match.group(1)))
    return seq + 1


def add_matter(firm_id: str, lawyer_id: str, client_name: str,
               opposing_party: str = "", matter_type: str = "",
               description: str = "") -> dict:
    firms = _load(_FIRMS_PATH, Firm)
    firm = next((f for f in firms if f.id == firm_id), None)
    if not firm:
        raise ValueError("Unknown firm.")
    lawyers = _load(_LAWYERS_PATH, Lawyer)
    if not any(l.id == lawyer_id and l.firm_id == firm_id for l in lawyers):
        raise ValueError("Lawyer not registered with this firm.")
    if not client_name.strip():
        raise ValueError("Client name is required.")

    # Build a human-friendly matter ID like "SINGHANIA/2026/0042"
    year = datetime.now(timezone.utc).year
    firm_abbr = re.sub(r"[^A-Z]", "", firm.name.upper())[:8] or "FIRM"
    seq = _next_matter_seq(firm_id, year)
    matter_id = f"{firm_abbr}/{year}/{seq:04d}"

    matters = _load(_MATTERS_PATH, Matter)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = Matter(
        id=matter_id,
        firm_id=firm_id,
        lawyer_id=lawyer_id,
        client_name=client_name.strip()[:120],
        opposing_party=opposing_party.strip()[:120],
        matter_type=matter_type.strip().lower()[:40],
        description=description.strip()[:500],
        status="open",
        created_at=now,
        updated_at=now,
    )
    matters.append(new)
    _save(_MATTERS_PATH, matters)
    return asdict(new)


def get_matter(matter_id: str) -> dict | None:
    for m in _load(_MATTERS_PATH, Matter):
        if m.id == matter_id:
            return asdict(m)
    return None


def update_matter_status(matter_id: str, status: str) -> bool:
    if status not in ("open", "filed", "settled", "closed"):
        return False
    matters = _load(_MATTERS_PATH, Matter)
    found = False
    for m in matters:
        if m.id == matter_id:
            m.status = status
            m.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            found = True
            break
    if found:
        _save(_MATTERS_PATH, matters)
    return found


# ─── Conflict-of-interest check ─────────────────────────────────────────────
def check_conflict(firm_id: str, client_name: str,
                   opposing_party: str = "") -> list[dict]:
    """
    Quick conflict-of-interest scan: returns any existing matters in the
    same firm where:
      - The opposing party in an existing matter matches the new client, OR
      - The client of an existing matter matches the new opposing party.

    Empty list = no conflict.  Non-empty = the firm should review before
    accepting the new instruction.
    """
    client_lo = (client_name or "").strip().lower()
    opp_lo    = (opposing_party or "").strip().lower()
    if not client_lo and not opp_lo:
        return []

    hits = []
    for m in _load(_MATTERS_PATH, Matter):
        if m.firm_id != firm_id:
            continue
        m_client = m.client_name.lower()
        m_opp    = m.opposing_party.lower()
        # Existing opposing party = new client?
        if client_lo and m_opp and (client_lo in m_opp or m_opp in client_lo):
            hits.append({
                "matter_id": m.id,
                "reason": f"You previously represented {m.client_name} against {m.opposing_party}",
            })
            continue
        # Existing client = new opposing party?
        if opp_lo and m_client and (opp_lo in m_client or m_client in opp_lo):
            hits.append({
                "matter_id": m.id,
                "reason": f"You previously represented {m.client_name} (now the opposing party)",
            })
    return hits
