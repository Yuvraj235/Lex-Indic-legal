"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Multi-tenant auth (Day 10): magic-link login + session cookie  ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Email + 6-digit code login, HMAC-signed session cookies, user-to-firm
binding. Each successful login creates a session bound to a user_id; each
user is bound to one firm (the multi-tenant boundary).  Requests to
/analyze and /chat that carry a session cookie get tagged with the
firm_id in the audit log.

WHY: Multi-tenant auth is the gate every firm GC requires before they let
any associate log in.  Real production wants SAML/OIDC via Auth0 or Clerk;
this MVP gives us the data model + flow so we can swap the front-end of
the auth pipeline without changing the rest of the app.

STORAGE: SQLite (stdlib).  Zero external dependencies.  Schema lives in
auth_init_db() — single file at outputs/auth.db.

MAGIC LINK DELIVERY: In dev we print the code to the server log.
Production wires this to a real email provider (SES, Postmark, Sendgrid).
The plumbing point is _send_code() — replace its body.

SESSION COOKIE: 'lex_session' cookie set HttpOnly + SameSite=Lax + Secure
(in HTTPS mode).  Body is base64(user_id:expires_ts).hex(hmac_sha256).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import envmode

_DB_PATH       = Path("outputs") / "auth.db"
_CODE_TTL      = 600              # 10 minutes
_MAX_CODE_ATTEMPTS = 5            # wrong guesses before a code is burned
_MAX_CODES_PER_HOUR = 5           # codes one email can request per hour
_SESSION_TTL   = 60 * 60 * 24 * 14   # 14 days
_COOKIE_NAME   = "lex_session"
_INVITE_TTL    = 60 * 60 * 24 * 7    # 7 days
INVITE_ROLES   = ("partner", "senior_associate", "associate", "paralegal")


def _secret() -> bytes:
    """The HMAC key for session cookies, derived from the deployment secret
    (see envmode.secret_key). Raises in production when no secret is set."""
    return hashlib.sha256(b"lex-indic-auth-key|" + envmode.secret_key().encode()).digest()


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
    """Create tables on first run; idempotent."""
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           TEXT PRIMARY KEY,
            email        TEXT UNIQUE NOT NULL,
            firm_id      TEXT,
            full_name    TEXT,
            role         TEXT NOT NULL DEFAULT 'associate',
            created_at   TEXT NOT NULL,
            last_login   TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_users_firm  ON users(firm_id);

        CREATE TABLE IF NOT EXISTS login_codes (
            email        TEXT NOT NULL,
            code_hash    TEXT NOT NULL,
            expires_at   INTEGER NOT NULL,
            consumed     INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_codes_email ON login_codes(email);

        CREATE TABLE IF NOT EXISTS firm_invites (
            code_hash    TEXT PRIMARY KEY,
            firm_id      TEXT NOT NULL,
            role         TEXT NOT NULL,
            created_by   TEXT NOT NULL,
            expires_at   INTEGER NOT NULL,
            used_by      TEXT,
            used_at      TEXT
        );
        """)
        user_cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        if "session_epoch" not in user_cols:
            c.execute("ALTER TABLE users ADD COLUMN session_epoch INTEGER NOT NULL DEFAULT 0")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(login_codes)")}
        if "attempts" not in cols:
            c.execute("ALTER TABLE login_codes ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        if "issued_at" not in cols:
            c.execute("ALTER TABLE login_codes ADD COLUMN issued_at INTEGER NOT NULL DEFAULT 0")


# ─── User lookup / upsert ───────────────────────────────────────────────────
def get_user_by_email(email: str) -> Optional[dict]:
    with _db() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    with _db() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def upsert_user(email: str, *, firm_id: str = "", full_name: str = "",
                role: str = "associate") -> dict:
    init_db()
    email = email.lower().strip()
    if not email or "@" not in email:
        raise ValueError("Valid email is required.")
    existing = get_user_by_email(email)
    if existing:
        return existing
    user_id = "usr_" + secrets.token_hex(6)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db() as c:
        c.execute(
            "INSERT INTO users(id,email,firm_id,full_name,role,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, email, firm_id, full_name, role, now),
        )
    return get_user_by_email(email)


# ─── Magic-link / 6-digit code ──────────────────────────────────────────────
class RateLimited(Exception):
    """Too many login codes requested for one email."""


def _hash_code(code: str) -> str:
    return hashlib.sha256(b"lex-code|" + _secret() + b"|" + code.encode()).hexdigest()


def issue_code(email: str) -> str:
    """Generate a 6-digit code, store its hash, return the plaintext code.
    Caller is responsible for delivering it to the user (we just log in dev)."""
    init_db()
    email = email.lower().strip()
    if not email or "@" not in email:
        raise ValueError("Valid email is required.")
    now = int(time.time())
    with _db() as c:
        recent = c.execute(
            "SELECT COUNT(*) AS n FROM login_codes WHERE email = ? AND issued_at >= ?",
            (email, now - 3600),
        ).fetchone()["n"]
    if recent >= _MAX_CODES_PER_HOUR:
        raise RateLimited("Too many sign-in codes requested. Try again in an hour.")
    upsert_user(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    with _db() as c:
        # Only the newest code is valid: older live codes would multiply an
        # attacker's chance per guess.
        c.execute("UPDATE login_codes SET consumed = 1 WHERE email = ? AND consumed = 0",
                  (email,))
        c.execute(
            "INSERT INTO login_codes(email,code_hash,expires_at,consumed,attempts,issued_at) "
            "VALUES(?,?,?,0,0,?)",
            (email, _hash_code(code), now + _CODE_TTL, now),
        )
    _send_code(email, code)
    return code   # caller decides whether to expose this in the response (dev only)


def _send_code(email: str, code: str):
    """Day 17: delegates to the pluggable mailer.  In dev (MAIL_PROVIDER=stdout
    or unset), this still prints to the server log + appends to
    outputs/mail/sent.log.  In prod (MAIL_PROVIDER=smtp|ses), this actually
    delivers the email."""
    try:
        import mailer
        result = mailer.send_login_code(email, code, ttl_minutes=_CODE_TTL // 60)
        if not result.ok:
            # Fall back to stdout if the provider fails — login MUST work
            print(f"  [auth] mail send failed ({result.error}); code for {email}: {code}",
                  flush=True)
    except Exception as e:
        print(f"  [auth] mailer crashed ({e}); code for {email}: {code}", flush=True)


def verify_code(email: str, code: str) -> Optional[str]:
    """Returns user_id on success, None on bad/expired code. Each wrong guess
    counts against the email's live code; after _MAX_CODE_ATTEMPTS it's
    burned and the user must request a new one."""
    init_db()
    email = email.lower().strip()
    code_hash = _hash_code(code.strip())
    now = int(time.time())
    with _db() as c:
        row = c.execute(
            "SELECT rowid,* FROM login_codes "
            "WHERE email = ? AND code_hash = ? AND consumed = 0 AND expires_at >= ? "
            "ORDER BY expires_at DESC LIMIT 1",
            (email, code_hash, now),
        ).fetchone()
        if not row:
            c.execute(
                "UPDATE login_codes SET attempts = attempts + 1, "
                "consumed = CASE WHEN attempts + 1 >= ? THEN 1 ELSE consumed END "
                "WHERE email = ? AND consumed = 0",
                (_MAX_CODE_ATTEMPTS, email),
            )
            return None
        # Consume the code (single-use)
        c.execute("UPDATE login_codes SET consumed = 1 WHERE rowid = ?", (row["rowid"],))
        c.execute("UPDATE users SET last_login = ? WHERE email = ?",
                  (datetime.now(timezone.utc).isoformat(timespec="seconds"), email))
    user = get_user_by_email(email)
    return user["id"] if user else None


# ─── Session cookie helpers ─────────────────────────────────────────────────
def _session_epoch(user_id: str) -> int:
    """Bumped by revoke_sessions(); a token minted under an older epoch is dead."""
    init_db()
    with _db() as c:
        row = c.execute("SELECT session_epoch FROM users WHERE id = ?", (user_id,)).fetchone()
        return int(row["session_epoch"]) if row else 0


def revoke_sessions(user_id: str) -> None:
    """Invalidate every session token issued to this user so far (logout,
    account deletion). Stateless tokens can't be deleted, so they're outdated."""
    init_db()
    with _db() as c:
        c.execute("UPDATE users SET session_epoch = session_epoch + 1 WHERE id = ?", (user_id,))


def make_session_token(user_id: str) -> str:
    """Compact signed token: '<base64(user_id|expires|epoch)>.<hex(hmac)>'."""
    expires_at = int(time.time()) + _SESSION_TTL
    payload = f"{user_id}|{expires_at}|{_session_epoch(user_id)}".encode()
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str) -> Optional[str]:
    """Return user_id if the token is valid, unexpired and not revoked."""
    if not token or "." not in token:
        return None
    payload_b64, sig = token.split(".", 1)
    expected = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        pad = "=" * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(payload_b64 + pad).decode()
        user_id, expires_at, *rest = payload.split("|")
        epoch = int(rest[0]) if rest else 0
        if int(expires_at) < int(time.time()):
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    if epoch != _session_epoch(user_id):
        return None   # logged out (or deleted) after this token was issued
    return user_id


# ─── Firm invites ──────────────────────────────────────────────────────────
def _hash_invite(code: str) -> str:
    return hashlib.sha256(b"lex-invite|" + _secret() + b"|" + code.encode()).hexdigest()


def create_invite(firm_id: str, *, role: str = "associate", created_by: str) -> dict:
    """Single-use code that lets one person join `firm_id` with `role`.
    Only the hash is stored; the plaintext is returned once."""
    init_db()
    if role not in INVITE_ROLES:
        raise ValueError(f"role must be one of: {', '.join(INVITE_ROLES)}")
    code = secrets.token_urlsafe(16)
    expires_at = int(time.time()) + _INVITE_TTL
    with _db() as c:
        c.execute(
            "INSERT INTO firm_invites(code_hash,firm_id,role,created_by,expires_at) "
            "VALUES(?,?,?,?,?)",
            (_hash_invite(code), firm_id, role, created_by, expires_at),
        )
    return {
        "invite_code": code, "firm_id": firm_id, "role": role,
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(timespec="seconds"),
    }


def redeem_invite(code: str, user_id: str) -> Optional[str]:
    """Bind user_id to the invite's firm with the invite's role.
    Returns the firm_id, or None for an unknown / used / expired code."""
    init_db()
    h = _hash_invite(code.strip())
    with _db() as c:
        row = c.execute(
            "SELECT firm_id, role FROM firm_invites "
            "WHERE code_hash = ? AND used_by IS NULL AND expires_at >= ?",
            (h, int(time.time())),
        ).fetchone()
        if not row:
            return None
        claimed = c.execute(
            "UPDATE firm_invites SET used_by = ?, used_at = ? "
            "WHERE code_hash = ? AND used_by IS NULL",
            (user_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), h),
        )
        if claimed.rowcount != 1:   # lost a race with another redeemer
            return None
        c.execute("UPDATE users SET firm_id = ?, role = ? WHERE id = ?",
                  (row["firm_id"], row["role"], user_id))
    return row["firm_id"]


# ─── User-to-firm binding ──────────────────────────────────────────────────
def bind_user_to_firm(user_id: str, firm_id: str, *, role: str = "associate") -> bool:
    """Server-side only: firm creation and invite redemption call this.
    Never expose it to a caller-chosen firm_id or role."""
    init_db()
    with _db() as c:
        cur = c.execute(
            "UPDATE users SET firm_id = ?, role = ? WHERE id = ?",
            (firm_id, role, user_id),
        )
        return cur.rowcount > 0


# ─── Admin / stats ─────────────────────────────────────────────────────────
def list_users() -> list[dict]:
    init_db()
    with _db() as c:
        rows = c.execute("SELECT id,email,firm_id,full_name,role,created_at,last_login FROM users ORDER BY created_at DESC LIMIT 500").fetchall()
        return [dict(r) for r in rows]


def stats() -> dict:
    init_db()
    with _db() as c:
        total = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        bound = c.execute("SELECT COUNT(*) AS n FROM users WHERE firm_id != ''").fetchone()["n"]
        return {"total_users": total, "users_bound_to_firm": bound}
