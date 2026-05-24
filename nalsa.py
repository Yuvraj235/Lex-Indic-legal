"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — NALSA panel onboarding (Day 5 of Legora teardown)               ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT
────
NALSA = National Legal Services Authority, the constitutional body that
administers free legal aid under Article 39A and the Legal Services
Authorities Act 1987.  Roughly 70,000 advocates are empanelled across
state legal-services authorities (SLSAs) and district authorities (DLSAs).
These advocates take legal-aid cases at flat fees of ₹500–₹3,000 — they
cannot afford a ₹50,000/seat tool like Legora and they desperately need
faster triage.

This module stores NALSA panel registrations and exposes a "Free for NALSA
empanelled advocates" tier:

  - /nalsa             marketing landing pitched specifically at panel lawyers
  - /nalsa/register    self-claim form (panel ID, state authority, contact)
  - /nalsa/api/...     CRUD for the registry

We DO NOT verify panel membership in this MVP — that requires SLSA
cooperation and a verification API that doesn't yet exist publicly.  Instead
we collect the panel ID + state and emit a CSV the firm can periodically
spot-check against published SLSA panel lists.

Storage: a single JSON file (outputs/nalsa/registry.json) — gitignored.
Schema is stable so a future move to Postgres is mechanical.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import db   # Day-21 dual-backend

_REGISTRY_PATH = Path("outputs") / "nalsa" / "registry.json"

# The 36 NALSA SLSA jurisdictions (28 states + 8 union territories).
# Used for the dropdown on the registration form.
SLSAS = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman & Nicobar Islands", "Chandigarh", "Dadra & Nagar Haveli and Daman & Diu",
    "Jammu & Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]


@dataclass
class NalsaRegistration:
    id: str
    full_name: str
    panel_id: str
    slsa: str                # e.g. "Maharashtra"
    bar_council_no: str
    email: str
    phone: str
    practice_areas: list[str] = field(default_factory=list)
    case_volume_monthly: int = 0
    consent_to_contact: bool = False
    registered_at: str = ""
    status: str = "self_claimed"   # self_claimed | verified | revoked

    def to_dict(self):
        return asdict(self)


# ── JSON-file backend (default) ─────────────────────────────────────────────
def _load_json() -> list[NalsaRegistration]:
    if not _REGISTRY_PATH.exists():
        return []
    raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return [NalsaRegistration(**r) for r in raw]


def _save_json(regs: list[NalsaRegistration]):
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REGISTRY_PATH.write_text(
        json.dumps([r.to_dict() for r in regs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── DB-backed helpers ───────────────────────────────────────────────────────
def _row_to_reg(row) -> NalsaRegistration:
    return NalsaRegistration(
        id=row.id, full_name=row.full_name, panel_id=row.panel_id or "",
        slsa=row.slsa, bar_council_no=row.bar_council_no or "",
        email=row.email, phone=row.phone or "",
        practice_areas=list(row.practice_areas or []),
        case_volume_monthly=int(row.case_volume_monthly or 0),
        consent_to_contact=bool(row.consent_to_contact),
        registered_at=row.registered_at.isoformat(timespec="seconds") if row.registered_at else "",
        status=row.status or "self_claimed",
    )


def _all() -> list[NalsaRegistration]:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.NalsaRegistration).order_by(db.NalsaRegistration.registered_at.asc()).all()
            return [_row_to_reg(r) for r in rows]
    return _load_json()


# ── Validation ──────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[0-9 \-]{10,15}$")
_BCI_RE   = re.compile(r"^[A-Z]{2,4}/\d{1,6}/\d{4}$|^\d{1,7}$")
_PANEL_RE = re.compile(r"^[A-Za-z0-9 /\-_]{3,40}$")


def validate(payload: dict) -> tuple[bool, str | None]:
    if not payload.get("full_name", "").strip():
        return False, "Full name is required."
    if not _EMAIL_RE.match(payload.get("email", "")):
        return False, "Please provide a valid email."
    if not _PHONE_RE.match(payload.get("phone", "")):
        return False, "Please provide a valid 10-15 digit phone number."
    if payload.get("slsa") not in SLSAS:
        return False, "Please select a valid SLSA from the list."
    if not _BCI_RE.match(payload.get("bar_council_no", "")):
        return False, "Bar Council number looks invalid. Use the format MAH/1234/2010 or your registration number."
    if not _PANEL_RE.match(payload.get("panel_id", "")):
        return False, "Panel ID looks invalid."
    if not payload.get("consent_to_contact"):
        return False, "Consent to contact is required so the SLSA verification can be completed."
    return True, None


def register(payload: dict) -> NalsaRegistration:
    """Save a new self-claimed registration.  Caller must validate() first."""
    new = NalsaRegistration(
        id=f"nalsa_{int(datetime.now(timezone.utc).timestamp())}",
        full_name=payload["full_name"].strip()[:120],
        panel_id=payload["panel_id"].strip()[:40],
        slsa=payload["slsa"].strip(),
        bar_council_no=payload["bar_council_no"].strip().upper()[:30],
        email=payload["email"].strip().lower()[:120],
        phone=payload["phone"].strip()[:20],
        practice_areas=[a.strip().lower() for a in payload.get("practice_areas", []) if a.strip()][:8],
        case_volume_monthly=int(payload.get("case_volume_monthly") or 0),
        consent_to_contact=bool(payload.get("consent_to_contact")),
        registered_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="self_claimed",
    )
    if db.is_enabled():
        with db.session() as s:
            s.add(db.NalsaRegistration(
                id=new.id, full_name=new.full_name, panel_id=new.panel_id,
                slsa=new.slsa, bar_council_no=new.bar_council_no,
                email=new.email, phone=new.phone,
                practice_areas=new.practice_areas,
                case_volume_monthly=new.case_volume_monthly,
                consent_to_contact=new.consent_to_contact,
                registered_at=datetime.now(timezone.utc),
                status=new.status,
            ))
        return new
    regs = _load_json()
    regs.append(new)
    _save_json(regs)
    return new


def list_all() -> list[dict]:
    return [r.to_dict() for r in _all()]


def stats() -> dict:
    regs = _all()
    by_slsa: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total_volume = 0
    for r in regs:
        by_slsa[r.slsa] = by_slsa.get(r.slsa, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
        total_volume += r.case_volume_monthly
    return {
        "total_registrations": len(regs),
        "by_slsa": dict(sorted(by_slsa.items(), key=lambda x: -x[1])),
        "by_status": by_status,
        "monthly_case_volume_claimed": total_volume,
    }


def export_csv() -> str:
    """Spot-check CSV for SLSA verification.  Caller should restrict access."""
    regs = _all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "id", "full_name", "panel_id", "slsa", "bar_council_no",
        "email", "phone", "case_volume_monthly", "registered_at", "status",
    ])
    for r in regs:
        w.writerow([
            r.id, r.full_name, r.panel_id, r.slsa, r.bar_council_no,
            r.email, r.phone, r.case_volume_monthly, r.registered_at, r.status,
        ])
    return buf.getvalue()


def is_registered(email: str) -> bool:
    if not email:
        return False
    email = email.lower().strip()
    if db.is_enabled():
        with db.session() as s:
            row = (s.query(db.NalsaRegistration)
                    .filter(db.NalsaRegistration.email == email,
                            db.NalsaRegistration.status != "revoked")
                    .first())
            return row is not None
    return any(r.email == email and r.status != "revoked" for r in _load_json())


def backend() -> str:
    if not db.is_enabled():
        return "json"
    scheme = db.database_url().split(":")[0].lower()
    return "postgres" if "postgres" in scheme else ("sqlite" if "sqlite" in scheme else scheme)
