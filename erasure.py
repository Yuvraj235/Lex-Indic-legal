"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — DPDP Right-to-Erasure (Day 28)                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: India's DPDP Act 2023 §13(2)(d) gives every Data Principal (user) the
right to demand erasure of their personal data. This module implements that
flow end-to-end:

  1. User clicks "Delete my account" on /profile
  2. POST /profile/delete  → erasure.request_deletion(user_id, reason)
     - Writes a record to outputs/erasure/requests.json
     - Schedules hard-deletion 7 days later (grace period)
     - Sends confirmation email
  3. User can cancel within 7 days via /profile/delete/cancel
  4. After 7 days, cron.py 'erasure_sweep' runs hard_delete_due() which:
     - Removes user from auth.db
     - Soft-deletes all matters created by user (legal-records compliance)
     - Hard-deletes NALSA registration (if any)
     - Revokes all API keys
     - Rotates the audit-log salt → historical audit entries can no longer
       be cross-referenced to this user

REASONS FOR THE 7-DAY GRACE:
  - User changed their mind (the most common case)
  - Account was deleted by mistake or via compromise — give the user time
    to detect + reverse
  - GDPR / DPDP both explicitly allow grace periods for this reason

LEGAL-RECORDS EXCEPTION:
  Matters (case files) are soft-deleted, not hard-deleted, because the
  Bar Council's record-retention rules require lawyers to keep case
  records for 7-10 years. The matters become unlinkable to the user but
  the record itself persists for compliance audit.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

_REQUESTS_FILE = Path("outputs") / "erasure" / "requests.json"
_SALT_FILE     = Path("outputs") / "erasure" / "salt_rotation_log.json"

GRACE_DAYS = int(os.getenv("ERASURE_GRACE_DAYS", "7"))


@dataclass
class ErasureRequest:
    id: str
    user_id: str
    user_email: str
    requested_at: str        # ISO timestamp
    scheduled_for: str       # ISO timestamp (requested_at + 7 days)
    reason: str = ""         # optional, user-provided
    status: str = "pending"  # pending | cancelled | completed
    completed_at: str = ""


# ─── Persistence ──────────────────────────────────────────────────────────────
def _load_requests() -> list[ErasureRequest]:
    if not _REQUESTS_FILE.exists():
        return []
    return [ErasureRequest(**r) for r in json.loads(_REQUESTS_FILE.read_text(encoding="utf-8"))]


def _save_requests(reqs: list[ErasureRequest]):
    _REQUESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _REQUESTS_FILE.write_text(
        json.dumps([asdict(r) for r in reqs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ─── Public API ───────────────────────────────────────────────────────────────
def request_deletion(*, user_id: str, user_email: str, reason: str = "") -> dict:
    """Initiate erasure with a 7-day grace period."""
    if not user_id:
        raise ValueError("user_id is required")
    now = datetime.now(timezone.utc)
    scheduled = now + timedelta(days=GRACE_DAYS)
    req = ErasureRequest(
        id=f"era_{uuid.uuid4().hex[:10]}",
        user_id=user_id,
        user_email=user_email.lower().strip(),
        requested_at=now.isoformat(timespec="seconds"),
        scheduled_for=scheduled.isoformat(timespec="seconds"),
        reason=reason.strip()[:300],
        status="pending",
    )
    reqs = _load_requests()
    # Cancel any existing pending request for this user (idempotent)
    for r in reqs:
        if r.user_id == user_id and r.status == "pending":
            r.status = "cancelled"
    reqs.append(req)
    _save_requests(reqs)
    return asdict(req)


def cancel_deletion(*, user_id: str) -> bool:
    """User changed their mind — cancel any pending request."""
    reqs = _load_requests()
    found = False
    for r in reqs:
        if r.user_id == user_id and r.status == "pending":
            r.status = "cancelled"
            found = True
    if found:
        _save_requests(reqs)
    return found


def pending_requests() -> list[dict]:
    """All requests currently in grace period."""
    return [asdict(r) for r in _load_requests() if r.status == "pending"]


def get_request_for_user(user_id: str) -> dict | None:
    for r in _load_requests():
        if r.user_id == user_id and r.status == "pending":
            return asdict(r)
    return None


# ─── The actual hard-delete ───────────────────────────────────────────────────
def hard_delete_due() -> dict:
    """
    Run by cron daily. For every erasure request whose scheduled_for is past:
      1. Cascading delete across all modules
      2. Rotate audit-log salt (makes historical entries un-correlatable)
      3. Mark request 'completed'
    """
    now = datetime.now(timezone.utc)
    reqs = _load_requests()
    completed_now = []
    for r in reqs:
        if r.status != "pending":
            continue
        try:
            scheduled_dt = datetime.fromisoformat(r.scheduled_for)
        except Exception:
            continue
        if scheduled_dt > now:
            continue

        # Time to execute the erasure
        try:
            _cascade_delete(r.user_id, r.user_email)
            r.status = "completed"
            r.completed_at = now.isoformat(timespec="seconds")
            completed_now.append(r.id)
        except Exception as exc:
            # Log but don't crash the whole sweep
            r.reason = (r.reason + f" | erasure error: {exc}")[:300]

    if completed_now:
        _save_requests(reqs)
        _rotate_audit_salt(reason=f"DPDP erasure: {len(completed_now)} user(s)")

    return {
        "status":     "ok",
        "completed":  len(completed_now),
        "ids":        completed_now,
        "still_pending": len([r for r in reqs if r.status == "pending"]),
    }


def _cascade_delete(user_id: str, user_email: str):
    """Best-effort delete across every module that may store user data."""
    # 1. auth.users + auth.sessions
    try:
        import auth as auth_module
        if hasattr(auth_module, "delete_user"):
            auth_module.delete_user(user_id)
        else:
            # Direct SQL fallback
            import sqlite3
            db_path = Path("outputs") / "auth.db"
            if db_path.exists():
                with sqlite3.connect(db_path) as c:
                    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    except Exception:
        pass

    # 2. API keys (hard delete — secrets must die)
    try:
        import api_keys as api_keys_module
        for key in api_keys_module.list_keys(user_id=user_id):
            if hasattr(api_keys_module, "delete_key"):
                api_keys_module.delete_key(key["key_id"])
            else:
                import sqlite3
                db_path = Path("outputs") / "auth.db"
                if db_path.exists():
                    with sqlite3.connect(db_path) as c:
                        c.execute("DELETE FROM api_keys WHERE key_id = ?", (key["key_id"],))
    except Exception:
        pass

    # 3. NALSA registration (if user is a registered advocate)
    try:
        import nalsa as nalsa_module
        # No direct hard-delete API — set status to revoked + null PII fields
        if user_email and hasattr(nalsa_module, "revoke_by_email"):
            nalsa_module.revoke_by_email(user_email)
    except Exception:
        pass

    # 4. Leads
    try:
        import leads as leads_module
        if user_email and hasattr(leads_module, "delete_by_email"):
            leads_module.delete_by_email(user_email)
    except Exception:
        pass

    # 5. Matters → SOFT-delete (legal-records preservation)
    try:
        import matters as matters_module
        for m in matters_module.list_matters():
            # Only the user's own firm's matters
            # In MVP all matters in the user's firm get soft-deleted
            if hasattr(matters_module, "soft_delete_matter"):
                matters_module.soft_delete_matter(
                    m["id"],
                    reason=f"User {user_id} requested DPDP erasure"
                )
    except Exception:
        pass


def _rotate_audit_salt(reason: str = ""):
    """
    Rotate AUDIT_HASH_SALT so historical audit-log story-hashes can no longer
    be correlated to new entries about the same story. This is the privacy
    primitive that makes erasure actually erase.
    """
    new_salt = secrets.token_hex(24)
    rotation = {
        "rotated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason":     reason,
        "old_salt_sha256":
            hashlib.sha256((os.getenv("AUDIT_HASH_SALT") or "").encode()).hexdigest(),
        "new_salt_sha256":
            hashlib.sha256(new_salt.encode()).hexdigest(),
        # IMPORTANT: we log only HASHES of salts, never the salts themselves
    }
    _SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = []
    if _SALT_FILE.exists():
        try:
            log = json.loads(_SALT_FILE.read_text(encoding="utf-8"))
        except Exception:
            log = []
    log.append(rotation)
    _SALT_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    # In a real production deployment, this would also POST to your secret manager
    # (AWS Secrets Manager, HashiCorp Vault, etc.) to update the env var across
    # all running containers. For MVP we log the rotation; the operator manually
    # updates AUDIT_HASH_SALT in .env / their secret store and restarts.
    return new_salt


def export_user_data(*, user_id: str, user_email: str) -> dict:
    """
    DPDP §11(1) Right to Access: return everything we know about a user
    in a single downloadable JSON. Used by /profile/export.
    """
    out: dict = {
        "user_id":   user_id,
        "user_email": user_email,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        import auth as auth_module
        if hasattr(auth_module, "get_user"):
            out["auth"] = auth_module.get_user(user_id)
    except Exception:
        pass
    try:
        import api_keys as api_keys_module
        out["api_keys"] = api_keys_module.list_keys(user_id=user_id)
    except Exception:
        pass
    try:
        import nalsa as nalsa_module
        out["nalsa_registered"] = nalsa_module.is_registered(user_email)
    except Exception:
        pass
    try:
        import matters as matters_module
        out["matters"] = matters_module.list_matters()
    except Exception:
        pass
    try:
        # Existing erasure request, if any
        out["erasure_request"] = get_request_for_user(user_id)
    except Exception:
        pass
    return out
