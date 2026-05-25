"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Incident tracking (gap fix from Day 15 status page)             ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Replaces the hardcoded incident list in templates/status.html with a
real JSON-backed CRUD store. Status page now reads live data; operator can
add/resolve incidents via the admin API.

STATUSES:
  - investigating  (yellow)
  - identified     (orange)
  - monitoring     (blue)
  - resolved       (green)

SEVERITIES:
  - critical (red)
  - major    (orange)
  - minor    (yellow)
  - info     (grey)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

_PATH = Path("outputs") / "incidents" / "incidents.json"

VALID_STATUSES   = ("investigating", "identified", "monitoring", "resolved")
VALID_SEVERITIES = ("critical", "major", "minor", "info")
VALID_COMPONENTS = ("web", "database", "llm", "monitor_scraper", "webhooks", "sms", "email")


@dataclass
class Incident:
    id: str
    title: str
    component: str
    severity: str               # critical | major | minor | info
    status: str                 # investigating | identified | monitoring | resolved
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str = ""
    updates: list[dict] = field(default_factory=list)   # [{ts, status, message}]


def _load() -> list[Incident]:
    if not _PATH.exists():
        return []
    raw = json.loads(_PATH.read_text(encoding="utf-8"))
    return [Incident(**r) for r in raw]


def _save(items: list[Incident]):
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(
        json.dumps([asdict(i) for i in items], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_recent(limit: int = 5) -> list[dict]:
    """Newest first."""
    items = _load()
    items.sort(key=lambda i: i.created_at, reverse=True)
    return [asdict(i) for i in items[:limit]]


def list_open() -> list[dict]:
    """All incidents whose status is not 'resolved'."""
    items = _load()
    return [asdict(i) for i in items if i.status != "resolved"]


def open_incident(*, title: str, component: str, severity: str,
                  description: str = "") -> dict:
    """Create a new incident. Returns the saved record."""
    if not title.strip():
        raise ValueError("title is required")
    if component not in VALID_COMPONENTS:
        raise ValueError(f"component must be one of: {VALID_COMPONENTS}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"severity must be one of: {VALID_SEVERITIES}")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inc = Incident(
        id=f"inc_{uuid.uuid4().hex[:10]}",
        title=title.strip()[:160],
        component=component,
        severity=severity,
        status="investigating",
        description=description.strip()[:1000],
        created_at=now,
        updated_at=now,
        updates=[{"ts": now, "status": "investigating",
                  "message": "Incident opened."}],
    )
    items = _load()
    items.append(inc)
    _save(items)
    return asdict(inc)


def update_incident(incident_id: str, *, status: str, message: str = "") -> dict | None:
    """Append an update + change status. Set status='resolved' to close."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of: {VALID_STATUSES}")
    items = _load()
    for inc in items:
        if inc.id == incident_id:
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            inc.status = status
            inc.updated_at = now
            if status == "resolved" and not inc.resolved_at:
                inc.resolved_at = now
            inc.updates.append({"ts": now, "status": status, "message": message})
            _save(items)
            return asdict(inc)
    return None


def overall_status() -> dict:
    """Compute the banner status (operational / degraded / outage)."""
    open_incs = [i for i in _load() if i.status != "resolved"]
    if not open_incs:
        return {"label": "All systems operational", "color": "green",
                "open_count": 0}
    severities = {i.severity for i in open_incs}
    if "critical" in severities:
        return {"label": "Major outage", "color": "red",
                "open_count": len(open_incs)}
    if "major" in severities:
        return {"label": "Degraded performance", "color": "orange",
                "open_count": len(open_incs)}
    return {"label": "Minor issues being investigated", "color": "yellow",
            "open_count": len(open_incs)}
