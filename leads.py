"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Lead capture (/try)                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: When a prospect lands on the public demo URL without context, /try
gives them a 3-field form (name / email / firm) so we don't lose the
introduction.  Webhook fires 'lead.captured' so the operator can pipe
it into Slack / Notion / CRM.

STORAGE (Day 21): Dual-backed.
  - DATABASE_URL unset → outputs/leads/leads.json (default, dev mode)
  - DATABASE_URL set   → Postgres / SQLite via db.py ORM

The switch is transparent — every public function dispatches based on
db.is_enabled().  Callers don't care which path is active.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import db  # lazy backend; db.is_enabled() is False unless DATABASE_URL is set

_LEADS_PATH = Path("outputs") / "leads" / "leads.json"
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


@dataclass
class Lead:
    id: str
    full_name: str
    email: str
    firm_or_org: str = ""
    role: str = ""              # 'partner', 'associate', 'in-house', 'NALSA panel', etc
    practice_areas: list[str] = field(default_factory=list)
    how_heard: str = ""         # free-text "how did you find Lex-Indic"
    interests: list[str] = field(default_factory=list)  # which features they care about
    referrer: str = ""          # HTTP Referer header
    user_agent: str = ""
    captured_at: str = ""


# ── JSON-file backend (default / dev) ───────────────────────────────────────
def _load_json() -> list[Lead]:
    if not _LEADS_PATH.exists():
        return []
    return [Lead(**r) for r in json.loads(_LEADS_PATH.read_text(encoding="utf-8"))]


def _save_json(leads: list[Lead]):
    _LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LEADS_PATH.write_text(
        json.dumps([asdict(l) for l in leads], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── DB-backed helpers ───────────────────────────────────────────────────────
def _row_to_lead(row) -> Lead:
    """SQLAlchemy ORM row → dataclass."""
    return Lead(
        id=row.id, full_name=row.full_name, email=row.email,
        firm_or_org=row.firm_or_org or "", role=row.role or "",
        practice_areas=list(row.practice_areas or []),
        how_heard=row.how_heard or "",
        interests=list(row.interests or []),
        referrer=row.referrer or "", user_agent=row.user_agent or "",
        captured_at=row.captured_at.isoformat(timespec="seconds") if row.captured_at else "",
    )


# ── Public API ──────────────────────────────────────────────────────────────
def validate(payload: dict) -> tuple[bool, str | None]:
    if not (payload.get("full_name") or "").strip():
        return False, "Please tell us your name."
    if not _EMAIL_RE.match(payload.get("email", "")):
        return False, "Please provide a valid email."
    return True, None


def capture(payload: dict, *, referrer: str = "", user_agent: str = "") -> Lead:
    """Caller validates first."""
    new = Lead(
        id="lead_" + uuid.uuid4().hex[:10],
        full_name=payload["full_name"].strip()[:120],
        email=payload["email"].strip().lower()[:120],
        firm_or_org=(payload.get("firm_or_org") or "").strip()[:120],
        role=(payload.get("role") or "").strip()[:40],
        practice_areas=[a.strip().lower() for a in (payload.get("practice_areas") or []) if a.strip()][:10],
        how_heard=(payload.get("how_heard") or "").strip()[:300],
        interests=[i.strip() for i in (payload.get("interests") or []) if i.strip()][:10],
        referrer=referrer[:300],
        user_agent=user_agent[:200],
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    if db.is_enabled():
        with db.session() as s:
            s.add(db.Lead(
                id=new.id, full_name=new.full_name, email=new.email,
                firm_or_org=new.firm_or_org, role=new.role,
                practice_areas=new.practice_areas, how_heard=new.how_heard,
                interests=new.interests, referrer=new.referrer,
                user_agent=new.user_agent,
                captured_at=datetime.now(timezone.utc),
            ))
        return new

    leads = _load_json()
    leads.append(new)
    _save_json(leads)
    return new


def list_all() -> list[dict]:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.Lead).order_by(db.Lead.captured_at.asc()).all()
            return [asdict(_row_to_lead(r)) for r in rows]
    return [asdict(l) for l in _load_json()]


def stats() -> dict:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.Lead).order_by(db.Lead.captured_at.desc()).all()
            leads = [_row_to_lead(r) for r in rows]
    else:
        leads = _load_json()

    by_role: dict[str, int] = {}
    by_interest: dict[str, int] = {}
    for l in leads:
        if l.role:
            by_role[l.role] = by_role.get(l.role, 0) + 1
        for i in l.interests:
            by_interest[i] = by_interest.get(i, 0) + 1
    return {
        "total":        len(leads),
        "by_role":      dict(sorted(by_role.items(), key=lambda x: -x[1])),
        "by_interest":  dict(sorted(by_interest.items(), key=lambda x: -x[1])),
        # `latest` is the 10 newest captured leads
        "latest":       [asdict(l) for l in sorted(leads, key=lambda x: x.captured_at, reverse=True)[:10]],
    }


def is_captured(email: str) -> bool:
    if not email:
        return False
    email = email.lower().strip()
    if db.is_enabled():
        with db.session() as s:
            return s.query(db.Lead).filter(db.Lead.email == email).first() is not None
    return any(l.email == email for l in _load_json())


def backend() -> str:
    """Returns 'postgres' / 'sqlite' / 'json' so the dashboard can show
    the operator which mode this module is in."""
    if not db.is_enabled():
        return "json"
    scheme = db.database_url().split(":")[0].lower()
    if "postgres" in scheme: return "postgres"
    if "sqlite"   in scheme: return "sqlite"
    return scheme or "db"
