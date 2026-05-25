"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Matter intake registry (Day 9 → Day 21 dual-backend)            ║
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

Day 21: Dual-backed — DATABASE_URL unset → JSON files (default dev mode);
DATABASE_URL set → Postgres / SQLite via db.py ORM.  Zero-touch switch.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import db   # Day-21 dual-backend

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
    deleted_at: str = ""       # Day 26: soft-delete (admin-only). Non-empty = hidden but recoverable.
    deleted_reason: str = ""   # Why it was deleted (audit trail)


# ─── JSON-file backend helpers ──────────────────────────────────────────────
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


# ─── DB-backed row converters ────────────────────────────────────────────────
def _row_to_firm(row) -> Firm:
    return Firm(
        id=row.id, name=row.name, address=row.address or "",
        created_at=row.created_at.isoformat(timespec="seconds") if row.created_at else "",
    )

def _row_to_lawyer(row) -> Lawyer:
    return Lawyer(
        id=row.id, firm_id=row.firm_id, full_name=row.full_name,
        bar_council_no=row.bar_council_no or "", email=row.email or "",
        role=row.role or "associate",
        created_at=row.created_at.isoformat(timespec="seconds") if row.created_at else "",
    )

def _row_to_matter(row) -> Matter:
    return Matter(
        id=row.id, firm_id=row.firm_id, lawyer_id=row.lawyer_id or "",
        client_name=row.client_name, opposing_party=row.opposing_party or "",
        matter_type=row.matter_type or "", description=row.description or "",
        status=row.status or "open",
        created_at=row.created_at.isoformat(timespec="seconds") if row.created_at else "",
        updated_at=row.updated_at.isoformat(timespec="seconds") if row.updated_at else "",
        # Day 26: soft-delete fields (DB might not have columns; default empty)
        deleted_at=(getattr(row, "deleted_at", None).isoformat(timespec="seconds")
                     if getattr(row, "deleted_at", None) else ""),
        deleted_reason=getattr(row, "deleted_reason", "") or "",
    )


# ─── backend indicator ───────────────────────────────────────────────────────
def backend() -> str:
    if not db.is_enabled():
        return "json"
    scheme = db.database_url().split(":")[0].lower()
    return "postgres" if "postgres" in scheme else ("sqlite" if "sqlite" in scheme else scheme)


# ─── List helpers ─────────────────────────────────────────────────────────────
def list_firms() -> list[dict]:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.Firm).order_by(db.Firm.created_at.asc()).all()
            return [asdict(_row_to_firm(r)) for r in rows]
    return [asdict(f) for f in _load(_FIRMS_PATH, Firm)]


def list_lawyers() -> list[dict]:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.Lawyer).order_by(db.Lawyer.created_at.asc()).all()
            return [asdict(_row_to_lawyer(r)) for r in rows]
    return [asdict(l) for l in _load(_LAWYERS_PATH, Lawyer)]


def list_matters(*, include_deleted: bool = False) -> list[dict]:
    """List matters. By default soft-deleted matters are excluded (Day 26)."""
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.Matter).order_by(db.Matter.created_at.asc()).all()
            data = [asdict(_row_to_matter(r)) for r in rows]
    else:
        data = [asdict(m) for m in _load(_MATTERS_PATH, Matter)]
    if not include_deleted:
        data = [m for m in data if not m.get("deleted_at")]
    return data


# ─── Firm CRUD ──────────────────────────────────────────────────────────────
def add_firm(name: str, address: str = "") -> dict:
    if not name.strip():
        raise ValueError("Firm name is required.")

    if db.is_enabled():
        with db.session() as s:
            # duplicate check
            existing = s.query(db.Firm).filter(
                db.Firm.name == name.strip()
            ).first()
            if existing:
                raise ValueError("A firm with that name already exists.")
            new_id = f"firm_{uuid.uuid4().hex[:10]}"
            now = datetime.now(timezone.utc)
            s.add(db.Firm(
                id=new_id, name=name.strip()[:120],
                address=address.strip()[:200], created_at=now,
            ))
        return {
            "id": new_id, "name": name.strip()[:120],
            "address": address.strip()[:200],
            "created_at": now.isoformat(timespec="seconds"),
        }

    firms = _load(_FIRMS_PATH, Firm)
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
    if role not in ("partner", "senior_associate", "associate", "paralegal"):
        raise ValueError("Invalid role.")
    if not full_name.strip():
        raise ValueError("Lawyer name is required.")

    if db.is_enabled():
        with db.session() as s:
            firm = s.query(db.Firm).filter(db.Firm.id == firm_id).first()
            if not firm:
                raise ValueError("Unknown firm.")
            new_id = f"lwy_{uuid.uuid4().hex[:10]}"
            now = datetime.now(timezone.utc)
            s.add(db.Lawyer(
                id=new_id, firm_id=firm_id,
                full_name=full_name.strip()[:120],
                bar_council_no=bar_council_no.strip()[:30],
                email=email.strip().lower()[:120],
                role=role, created_at=now,
            ))
        return {
            "id": new_id, "firm_id": firm_id,
            "full_name": full_name.strip()[:120],
            "bar_council_no": bar_council_no.strip()[:30],
            "email": email.strip().lower()[:120],
            "role": role,
            "created_at": now.isoformat(timespec="seconds"),
        }

    firms = _load(_FIRMS_PATH, Firm)
    if not any(f.id == firm_id for f in firms):
        raise ValueError("Unknown firm.")
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
def _next_matter_seq_json(firm_id: str, year: int) -> int:
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


def _next_matter_seq_db(s, firm_id: str, year: int) -> int:
    """Count existing matters for this firm+year to derive next seq."""
    pat = f"%/{year}/%"
    rows = s.query(db.Matter).filter(
        db.Matter.firm_id == firm_id,
        db.Matter.id.like(pat),
    ).all()
    seq = 0
    pat_re = re.compile(rf"^[A-Z]+/{year}/(\d+)$")
    for r in rows:
        m = pat_re.match(r.id)
        if m:
            seq = max(seq, int(m.group(1)))
    return seq + 1


def add_matter(firm_id: str, lawyer_id: str, client_name: str,
               opposing_party: str = "", matter_type: str = "",
               description: str = "") -> dict:
    if not client_name.strip():
        raise ValueError("Client name is required.")

    year = datetime.now(timezone.utc).year

    if db.is_enabled():
        with db.session() as s:
            firm = s.query(db.Firm).filter(db.Firm.id == firm_id).first()
            if not firm:
                raise ValueError("Unknown firm.")
            lawyer = s.query(db.Lawyer).filter(
                db.Lawyer.id == lawyer_id,
                db.Lawyer.firm_id == firm_id,
            ).first()
            if not lawyer:
                raise ValueError("Lawyer not registered with this firm.")
            firm_abbr = re.sub(r"[^A-Z]", "", firm.name.upper())[:8] or "FIRM"
            seq = _next_matter_seq_db(s, firm_id, year)
            matter_id = f"{firm_abbr}/{year}/{seq:04d}"
            now = datetime.now(timezone.utc)
            s.add(db.Matter(
                id=matter_id, firm_id=firm_id, lawyer_id=lawyer_id,
                client_name=client_name.strip()[:120],
                opposing_party=opposing_party.strip()[:120],
                matter_type=matter_type.strip().lower()[:40],
                description=description.strip()[:500],
                status="open", created_at=now, updated_at=now,
            ))
        return {
            "id": matter_id, "firm_id": firm_id, "lawyer_id": lawyer_id,
            "client_name": client_name.strip()[:120],
            "opposing_party": opposing_party.strip()[:120],
            "matter_type": matter_type.strip().lower()[:40],
            "description": description.strip()[:500],
            "status": "open",
            "created_at": now.isoformat(timespec="seconds"),
            "updated_at": now.isoformat(timespec="seconds"),
        }

    firms = _load(_FIRMS_PATH, Firm)
    firm = next((f for f in firms if f.id == firm_id), None)
    if not firm:
        raise ValueError("Unknown firm.")
    lawyers = _load(_LAWYERS_PATH, Lawyer)
    if not any(l.id == lawyer_id and l.firm_id == firm_id for l in lawyers):
        raise ValueError("Lawyer not registered with this firm.")

    firm_abbr = re.sub(r"[^A-Z]", "", firm.name.upper())[:8] or "FIRM"
    seq = _next_matter_seq_json(firm_id, year)
    matter_id = f"{firm_abbr}/{year}/{seq:04d}"

    matters = _load(_MATTERS_PATH, Matter)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = Matter(
        id=matter_id, firm_id=firm_id, lawyer_id=lawyer_id,
        client_name=client_name.strip()[:120],
        opposing_party=opposing_party.strip()[:120],
        matter_type=matter_type.strip().lower()[:40],
        description=description.strip()[:500],
        status="open", created_at=now, updated_at=now,
    )
    matters.append(new)
    _save(_MATTERS_PATH, matters)
    return asdict(new)


def get_matter(matter_id: str) -> dict | None:
    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.Matter).filter(db.Matter.id == matter_id).first()
            return asdict(_row_to_matter(row)) if row else None
    for m in _load(_MATTERS_PATH, Matter):
        if m.id == matter_id:
            return asdict(m)
    return None


def update_matter_status(matter_id: str, status: str) -> bool:
    if status not in ("open", "filed", "settled", "closed"):
        return False

    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.Matter).filter(db.Matter.id == matter_id).first()
            if not row:
                return False
            row.status = status
            row.updated_at = datetime.now(timezone.utc)
        return True

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

    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.Matter).filter(
                db.Matter.firm_id == firm_id
            ).all()
            matters_data = [_row_to_matter(r) for r in rows]
    else:
        matters_data = _load(_MATTERS_PATH, Matter)

    hits = []
    for m in matters_data:
        if m.firm_id != firm_id:
            continue
        m_client = m.client_name.lower()
        m_opp    = m.opposing_party.lower()
        if client_lo and m_opp and (client_lo in m_opp or m_opp in client_lo):
            hits.append({
                "matter_id": m.id,
                "reason": f"You previously represented {m.client_name} against {m.opposing_party}",
            })
            continue
        if opp_lo and m_client and (opp_lo in m_client or m_client in opp_lo):
            hits.append({
                "matter_id": m.id,
                "reason": f"You previously represented {m.client_name} (now the opposing party)",
            })
    return hits


# ─── Day 26: Soft-delete with admin override ────────────────────────────────
def soft_delete_matter(matter_id: str, reason: str = "") -> bool:
    """Hide a matter without losing the record (legal-records preservation).
    Admin-only. To restore, call restore_matter()."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    clean_reason = (reason or "").strip()[:300]

    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.Matter).filter(db.Matter.id == matter_id).first()
            if not row:
                return False
            # ORM might not have deleted_at column on older schemas; fall back to
            # status='deleted' as a marker.  Setting the attribute works either way.
            try:
                row.deleted_at = datetime.now(timezone.utc)
                row.deleted_reason = clean_reason
            except Exception:
                row.status = "deleted"
            row.updated_at = datetime.now(timezone.utc)
        return True

    matters = _load(_MATTERS_PATH, Matter)
    found = False
    for m in matters:
        if m.id == matter_id:
            m.deleted_at = now
            m.deleted_reason = clean_reason
            m.updated_at = now
            found = True
            break
    if found:
        _save(_MATTERS_PATH, matters)
    return found


def restore_matter(matter_id: str) -> bool:
    """Reverse a soft_delete_matter(). Admin-only."""
    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.Matter).filter(db.Matter.id == matter_id).first()
            if not row:
                return False
            try:
                row.deleted_at = None
                row.deleted_reason = ""
            except Exception:
                if row.status == "deleted":
                    row.status = "open"
            row.updated_at = datetime.now(timezone.utc)
        return True

    matters = _load(_MATTERS_PATH, Matter)
    found = False
    for m in matters:
        if m.id == matter_id:
            m.deleted_at = ""
            m.deleted_reason = ""
            m.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            found = True
            break
    if found:
        _save(_MATTERS_PATH, matters)
    return found
