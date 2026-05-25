"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — User notification preferences (Day 34)                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Per-user opt-in/opt-out settings for the SC monitor digest, WhatsApp
alerts, and product updates. Honoured by cron.py (digest_email) and sms.py.

WHY: Spammy emails kill trust. Some lawyers want a weekly summary, some
want daily, some want SMS only. Defaults are conservative (weekly digest,
no SMS) so we err on the side of NOT bothering people.

STORAGE: outputs/prefs/preferences.json — one row per email.
Dual-backed-ready (extends if/when we add to db.py).

DEFAULTS for new users:
  digest_frequency = 'weekly'
  digest_channel   = 'email'
  product_updates  = True
  sms_alerts       = False
  language         = 'en'
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

_PREFS_FILE = Path("outputs") / "prefs" / "preferences.json"

VALID_FREQUENCIES = ("off", "daily", "weekly")
VALID_CHANNELS    = ("email", "sms", "whatsapp")
VALID_LANGUAGES   = ("en", "hi")


@dataclass
class UserPrefs:
    email: str
    digest_frequency: str = "weekly"
    digest_channel:   str = "email"
    product_updates:  bool = True
    sms_alerts:       bool = False
    language:         str = "en"
    updated_at:       str = ""


# ─── Persistence ──────────────────────────────────────────────────────────────
def _load() -> dict[str, UserPrefs]:
    if not _PREFS_FILE.exists():
        return {}
    raw = json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
    return {k: UserPrefs(**v) for k, v in raw.items()}


def _save(prefs: dict[str, UserPrefs]):
    _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_FILE.write_text(
        json.dumps({k: asdict(v) for k, v in prefs.items()},
                    indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ─── Public API ───────────────────────────────────────────────────────────────
def get_prefs(email: str) -> dict:
    """Return preferences for a user. New users get safe defaults."""
    if not email:
        return asdict(UserPrefs(email=""))
    email = email.lower().strip()
    p = _load().get(email)
    if not p:
        return asdict(UserPrefs(email=email))
    return asdict(p)


def set_prefs(email: str, **updates) -> dict:
    """Update specific preference fields. Returns the new full prefs dict."""
    if not email:
        raise ValueError("email is required")
    email = email.lower().strip()

    # Validate inputs
    if "digest_frequency" in updates and updates["digest_frequency"] not in VALID_FREQUENCIES:
        raise ValueError(f"digest_frequency must be one of: {VALID_FREQUENCIES}")
    if "digest_channel" in updates and updates["digest_channel"] not in VALID_CHANNELS:
        raise ValueError(f"digest_channel must be one of: {VALID_CHANNELS}")
    if "language" in updates and updates["language"] not in VALID_LANGUAGES:
        raise ValueError(f"language must be one of: {VALID_LANGUAGES}")

    all_prefs = _load()
    current = all_prefs.get(email, UserPrefs(email=email))

    for k, v in updates.items():
        if hasattr(current, k):
            setattr(current, k, v)
    current.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    all_prefs[email] = current
    _save(all_prefs)
    return asdict(current)


def wants_digest(email: str, when: str = "daily") -> bool:
    """Called by cron.digest_email — should this user get today's digest?"""
    p = _load().get((email or "").lower().strip())
    if not p:
        # Default: weekly digest on Mondays
        return when == "weekly_monday"
    if p.digest_frequency == "off":
        return False
    if p.digest_frequency == "daily":
        return True
    if p.digest_frequency == "weekly":
        return when == "weekly_monday"
    return False


def wants_sms(email: str) -> bool:
    p = _load().get((email or "").lower().strip())
    return bool(p and p.sms_alerts)


def wants_product_updates(email: str) -> bool:
    p = _load().get((email or "").lower().strip())
    return p.product_updates if p else True


def list_all() -> list[dict]:
    """Operator view of all preferences."""
    return [asdict(p) for p in _load().values()]


def stats() -> dict:
    """Quick aggregate for the dashboard."""
    all_p = list(_load().values())
    return {
        "total":          len(all_p),
        "daily_digest":   sum(1 for p in all_p if p.digest_frequency == "daily"),
        "weekly_digest":  sum(1 for p in all_p if p.digest_frequency == "weekly"),
        "off_digest":     sum(1 for p in all_p if p.digest_frequency == "off"),
        "sms_alerts":     sum(1 for p in all_p if p.sms_alerts),
        "hindi_language": sum(1 for p in all_p if p.language == "hi"),
    }
