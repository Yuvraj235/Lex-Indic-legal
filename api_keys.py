"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — API key auth (Day 16 of extended roadmap)                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: HMAC-secured API keys so a firm's IT team can hit the `/api/v1/*`
endpoints from their case-management backend without dealing with the
magic-link session-cookie flow.

A key is `lex_live_` + 32 hex chars (public id) + a separate 48-hex-char
secret.  Format: `lex_live_<id>:<secret>`.  We store only a SHA-256 of
the secret — losing the DB never reveals plaintext keys.

Same SQLite database as auth.py — single source of truth for identity.
Keys are bound to a user_id and (optionally) a firm_id; rate limits and
audit-log enrichment flow through both.

RATE LIMITS (per key, sliding 60s window):
  - default: 60 req/min
  - configurable per-key when issued
A token bucket is kept in memory; cleared on restart (good enough for v1).

ROTATION: never edit a key — revoke + issue a new one.  Old key keeps
working for a `grace_period_minutes` so the integration can roll.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

_DB_PATH = Path("outputs") / "auth.db"   # shares the auth.py SQLite DB
_LOCK = Lock()


@contextmanager
def _db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id           TEXT PRIMARY KEY,            -- lex_live_<32 hex>
            secret_hash      TEXT NOT NULL,               -- sha256(secret + salt)
            user_id          TEXT NOT NULL,               -- joins auth.users
            firm_id          TEXT,                        -- multi-tenant scope
            label            TEXT,                        -- human label, e.g. "Singhania integration"
            tier             TEXT NOT NULL DEFAULT 'firm',-- free | nalsa | firm | internal
            daily_limit      INTEGER,                     -- NULL = use tier default
            rate_per_min     INTEGER NOT NULL DEFAULT 60,
            created_at       TEXT NOT NULL,
            last_used_at     TEXT,
            revoked_at       TEXT,                        -- NULL = active
            grace_period_min INTEGER NOT NULL DEFAULT 60
        );
        CREATE INDEX IF NOT EXISTS idx_keys_user ON api_keys(user_id);
        """)
        # Non-destructive column migrations for existing DBs
        existing_cols = {row[1] for row in c.execute("PRAGMA table_info(api_keys)").fetchall()}
        if "tier" not in existing_cols:
            c.execute("ALTER TABLE api_keys ADD COLUMN tier TEXT NOT NULL DEFAULT 'firm'")
        if "daily_limit" not in existing_cols:
            c.execute("ALTER TABLE api_keys ADD COLUMN daily_limit INTEGER")


def _hash_secret(secret: str) -> str:
    """SHA-256 of secret + deployment salt; reuses AUDIT_HASH_SALT."""
    salt = os.getenv("AUDIT_HASH_SALT", "lex-indic-dev")
    return hashlib.sha256(f"lex-api|{salt}|{secret}".encode()).hexdigest()


# ─── Public API ─────────────────────────────────────────────────────────────
def issue_key(user_id: str, *, firm_id: str = "", label: str = "",
              tier: str = "firm", daily_limit: int | None = None,
              rate_per_min: int = 60) -> dict:
    """Mint a new key. Returns {key_id, secret, full_key}.
    The plaintext secret is shown ONCE; store it on the caller side.
    tier: 'free' | 'nalsa' | 'firm' | 'internal'
    """
    init_db()
    if not user_id:
        raise ValueError("user_id is required")
    if tier not in ("free", "nalsa", "firm", "internal"):
        raise ValueError("tier must be one of: free, nalsa, firm, internal")
    if rate_per_min <= 0 or rate_per_min > 6000:
        raise ValueError("rate_per_min must be 1..6000")
    key_id = "lex_live_" + secrets.token_hex(16)
    secret = secrets.token_hex(24)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db() as c:
        c.execute(
            "INSERT INTO api_keys(key_id, secret_hash, user_id, firm_id, label,"
            " tier, daily_limit, rate_per_min, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (key_id, _hash_secret(secret), user_id, firm_id, label[:120],
             tier, daily_limit, int(rate_per_min), now),
        )
    return {
        "key_id":       key_id,
        "secret":       secret,
        "full_key":     f"{key_id}:{secret}",
        "user_id":      user_id,
        "firm_id":      firm_id,
        "label":        label,
        "tier":         tier,
        "daily_limit":  daily_limit,
        "rate_per_min": rate_per_min,
        "created_at":   now,
        "warning":      "Save this secret now — it will never be shown again.",
    }


def verify_key(full_key: str) -> Optional[dict]:
    """Validate `lex_live_<id>:<secret>` and return the key record (sans secret)
    or None.  Also enforces revocation + grace period."""
    if not full_key or ":" not in full_key:
        return None
    key_id, _, secret = full_key.partition(":")
    if not key_id.startswith("lex_live_") or not secret:
        return None
    init_db()
    expected = _hash_secret(secret)
    with _db() as c:
        row = c.execute(
            "SELECT * FROM api_keys WHERE key_id = ?", (key_id,)
        ).fetchone()
    if not row:
        return None
    if not hmac.compare_digest(row["secret_hash"], expected):
        return None
    # Revocation check (with grace period)
    if row["revoked_at"]:
        revoked = datetime.fromisoformat(row["revoked_at"])
        grace_end = revoked.timestamp() + (row["grace_period_min"] * 60)
        if time.time() > grace_end:
            return None
    # Mark last_used
    with _db() as c:
        c.execute("UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
                  (datetime.now(timezone.utc).isoformat(timespec="seconds"), key_id))
    out = dict(row)
    out.pop("secret_hash")
    return out


def list_keys(*, user_id: str = "") -> list[dict]:
    init_db()
    with _db() as c:
        if user_id:
            rows = c.execute(
                "SELECT key_id, user_id, firm_id, label, tier, daily_limit, "
                "rate_per_min, created_at, last_used_at, revoked_at "
                "FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT key_id, user_id, firm_id, label, tier, daily_limit, "
                "rate_per_min, created_at, last_used_at, revoked_at "
                "FROM api_keys ORDER BY created_at DESC LIMIT 500"
            ).fetchall()
    return [dict(r) for r in rows]


def revoke_key(key_id: str, *, grace_period_min: int = 60) -> bool:
    init_db()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db() as c:
        cur = c.execute(
            "UPDATE api_keys SET revoked_at = ?, grace_period_min = ? "
            "WHERE key_id = ? AND revoked_at IS NULL",
            (now, int(grace_period_min), key_id),
        )
        return cur.rowcount > 0


# ─── In-memory rate limiter ─────────────────────────────────────────────────
# Token-bucket per key_id: sliding 60s window of timestamps.
_RATE_BUCKETS: dict[str, deque] = {}


def check_rate_limit(key_id: str, rate_per_min: int) -> tuple[bool, int]:
    """Returns (allowed, remaining_in_window). Caller should 429 on False."""
    now = time.time()
    cutoff = now - 60
    with _LOCK:
        bucket = _RATE_BUCKETS.setdefault(key_id, deque())
        # Drop expired timestamps
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= rate_per_min:
            return False, 0
        bucket.append(now)
        return True, rate_per_min - len(bucket)
