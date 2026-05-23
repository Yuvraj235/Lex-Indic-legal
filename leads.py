"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Lead capture (/try)                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: When a prospect lands on the public demo URL without context, /try
gives them a 3-field form (name / email / firm) so we don't lose the
introduction.  Stored as JSON to outputs/leads/leads.json; webhook fires
'lead.captured' so the operator can pipe it into Slack / Notion / CRM.

This is sales infrastructure, not a feature.  Whatever lawyer hits the
shared demo URL is a real prospect — capture them.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

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


def _load() -> list[Lead]:
    if not _LEADS_PATH.exists():
        return []
    return [Lead(**r) for r in json.loads(_LEADS_PATH.read_text(encoding="utf-8"))]


def _save(leads: list[Lead]):
    _LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LEADS_PATH.write_text(
        json.dumps([asdict(l) for l in leads], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def validate(payload: dict) -> tuple[bool, str | None]:
    if not (payload.get("full_name") or "").strip():
        return False, "Please tell us your name."
    if not _EMAIL_RE.match(payload.get("email", "")):
        return False, "Please provide a valid email."
    return True, None


def capture(payload: dict, *, referrer: str = "", user_agent: str = "") -> Lead:
    """Caller validates first."""
    leads = _load()
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
    leads.append(new)
    _save(leads)
    return new


def list_all() -> list[dict]:
    return [asdict(l) for l in _load()]


def stats() -> dict:
    leads = _load()
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
        "latest":       [asdict(l) for l in leads[-10:][::-1]],
    }


def is_captured(email: str) -> bool:
    if not email:
        return False
    email = email.lower().strip()
    return any(l.email == email for l in _load())
