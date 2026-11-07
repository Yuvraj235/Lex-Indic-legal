"""
Who may read a generated case file (the case_analysis_*.txt + CaseBrief_*.pdf
pair written by /analyze).

Ownership is recorded when /analyze saves the files: the signed-in user and
their firm (the tenant boundary). A firm-bound user can open their own files
and their firm's; nobody else can, and files with no ownership record
(generated before this existed) are visible to nobody until claimed with
tools/claim_case_files.py.

Anonymous free-tier runs have no user to own them, so /analyze also returns a
short-lived signed download token for the PDF it just generated. The token is
bound to one filename, so it can't be replayed against another case.

STORAGE: outputs/case_access.db (SQLite, stdlib).
"""

from __future__ import annotations

import hashlib
import hmac
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import envmode

_DB_PATH = Path("outputs") / "case_access.db"
DOWNLOAD_TTL = 24 * 60 * 60   # 24 hours


@contextmanager
def _db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_files (
                txt_file   TEXT PRIMARY KEY,
                pdf_file   TEXT,
                user_id    TEXT,
                firm_id    TEXT,
                created_at TEXT NOT NULL
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_case_pdf ON case_files(pdf_file)")
        yield conn
        conn.commit()
    finally:
        conn.close()


def record(txt_file: str, pdf_file: Optional[str], *, user_id: Optional[str],
           firm_id: Optional[str]) -> None:
    with _db() as c:
        c.execute(
            "INSERT OR REPLACE INTO case_files(txt_file,pdf_file,user_id,firm_id,created_at) "
            "VALUES(?,?,?,?,?)",
            (txt_file, pdf_file or None, user_id or None, firm_id or None,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def lookup(filename: str) -> Optional[dict]:
    """The ownership record for a .txt or .pdf filename, or None."""
    with _db() as c:
        row = c.execute(
            "SELECT * FROM case_files WHERE txt_file = ? OR pdf_file = ? LIMIT 1",
            (filename, filename),
        ).fetchone()
        return dict(row) if row else None


def can_access(user: Optional[dict], filename: str) -> bool:
    if not user:
        return False
    rec = lookup(filename)
    if not rec:
        return False
    if rec["user_id"] and rec["user_id"] == user.get("id"):
        return True
    return bool(rec["firm_id"]) and rec["firm_id"] == user.get("firm_id")


def files_for(user: dict) -> list[dict]:
    """Every case file this user may open, newest first."""
    with _db() as c:
        firm_id = user.get("firm_id") or None
        rows = c.execute(
            "SELECT * FROM case_files WHERE user_id = ? "
            "OR (firm_id IS NOT NULL AND firm_id = ?) ORDER BY txt_file DESC",
            (user.get("id"), firm_id),
        ).fetchall()
        return [dict(r) for r in rows]


def unclaimed(txt_files: list[str]) -> list[str]:
    """The subset of txt_files that have no ownership record."""
    with _db() as c:
        known = {r["txt_file"] for r in c.execute("SELECT txt_file FROM case_files")}
    return [f for f in txt_files if f not in known]


# ─── Signed download tokens ─────────────────────────────────────────────────
def _key() -> bytes:
    return hashlib.sha256(b"lex-indic-download|" + envmode.secret_key().encode()).digest()


def _sign(filename: str, expires_at: int) -> str:
    return hmac.new(_key(), f"{filename}|{expires_at}".encode(), hashlib.sha256).hexdigest()


def make_download_token(filename: str, ttl: int = DOWNLOAD_TTL) -> str:
    expires_at = int(time.time()) + ttl
    return f"{expires_at}.{_sign(filename, expires_at)}"


def verify_download_token(filename: str, token: str) -> bool:
    if not token or "." not in token:
        return False
    exp_s, sig = token.split(".", 1)
    try:
        expires_at = int(exp_s)
    except ValueError:
        return False
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(sig, _sign(filename, expires_at))
