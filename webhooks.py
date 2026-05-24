"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Outbound webhooks (Day 15 → Day 22 retry queue)                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Lets a firm register URLs that will receive a signed HTTP POST when
events happen inside Lex-Indic.  Events implemented:

  - analysis.completed   — every /analyze call that returns OK
  - monitor.digest.ready — when /monitors/api/digest is computed
  - matter.created       — when a new matter is created via /matters/api/matters
  - nalsa.registered     — when a NALSA registration is recorded
  - lead.captured        — when a prospect submits /try

Why a customer asks for this: They want to thread Lex-Indic into their
existing systems — Slack channel notifications, Jira ticket creation,
Glific WhatsApp alerts to the SLSA secretariat, internal SIEM ingestion.

DELIVERY: Pure stdlib HTTP POST (urllib).  Each webhook fires
asynchronously via a Python `Thread` so the originating request isn't
blocked.  A HMAC-SHA256 signature is sent in the `X-Lex-Signature` header
so the receiver can verify the payload wasn't tampered with.

STORAGE: outputs/webhooks/subscriptions.json (gitignored — single source
of truth).  No Postgres yet; the v2.0 migration is mechanical.

RETRY POLICY (Day 22): SQLite-backed retry queue with exponential backoff.
Failed deliveries (non-2xx or network error) are written to
outputs/webhooks/retry_queue.db and retried up to MAX_RETRIES times with
delays of 10 s, 60 s, 300 s, 900 s, 3600 s.  A background daemon thread
drains the queue continuously.  This replaces the v1.4 fire-and-forget.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import db   # Day-21 dual-backend; transparent when DATABASE_URL unset

_SUBS_PATH   = Path("outputs") / "webhooks" / "subscriptions.json"
_LOG_PATH    = Path("outputs") / "webhooks" / "deliveries.log"
_RETRY_DB    = Path("outputs") / "webhooks" / "retry_queue.db"

# Exponential backoff delays in seconds: 10 s, 1 min, 5 min, 15 min, 1 h
_BACKOFF_DELAYS = [10, 60, 300, 900, 3600]
MAX_RETRIES     = len(_BACKOFF_DELAYS)

# ─── Retry queue (SQLite, always local regardless of DATABASE_URL) ───────────
_rq_lock = threading.Lock()

def _rq_conn() -> sqlite3.Connection:
    """Open (or create) the retry-queue DB. WAL mode for concurrent access."""
    _RETRY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_RETRY_DB), check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS retry_queue (
            id          TEXT PRIMARY KEY,
            sub_id      TEXT NOT NULL,
            sub_url     TEXT NOT NULL,
            event_id    TEXT NOT NULL,
            body        BLOB NOT NULL,
            sig         TEXT NOT NULL,
            attempt     INTEGER DEFAULT 0,
            next_try_at REAL NOT NULL,  -- epoch seconds
            created_at  REAL NOT NULL,
            last_error  TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


def _rq_enqueue(sub: "Subscription", body: bytes, sig: str, event_id: str):
    """Add a delivery attempt to the retry queue."""
    with _rq_lock:
        conn = _rq_conn()
        conn.execute(
            "INSERT OR REPLACE INTO retry_queue "
            "(id, sub_id, sub_url, event_id, body, sig, attempt, next_try_at, created_at) "
            "VALUES (?,?,?,?,?,?,0,?,?)",
            (f"{event_id}_{sub.id}", sub.id, sub.url, event_id,
             body, sig, time.time(), time.time()),
        )
        conn.commit()
        conn.close()


def _rq_dequeue_due(limit: int = 20) -> list[dict]:
    """Return up to `limit` jobs whose next_try_at is in the past."""
    with _rq_lock:
        if not _RETRY_DB.exists():
            return []
        conn = _rq_conn()
        rows = conn.execute(
            "SELECT id, sub_id, sub_url, event_id, body, sig, attempt, last_error "
            "FROM retry_queue WHERE next_try_at <= ? ORDER BY next_try_at LIMIT ?",
            (time.time(), limit),
        ).fetchall()
        conn.close()
    return [
        {"id": r[0], "sub_id": r[1], "sub_url": r[2], "event_id": r[3],
         "body": r[4], "sig": r[5], "attempt": r[6], "last_error": r[7]}
        for r in rows
    ]


def _rq_reschedule(job_id: str, attempt: int, error: str):
    """Back off failed job; delete if max retries exceeded."""
    with _rq_lock:
        conn = _rq_conn()
        if attempt >= MAX_RETRIES:
            conn.execute("DELETE FROM retry_queue WHERE id=?", (job_id,))
        else:
            delay = _BACKOFF_DELAYS[attempt]
            conn.execute(
                "UPDATE retry_queue SET attempt=?, next_try_at=?, last_error=? WHERE id=?",
                (attempt + 1, time.time() + delay, error[:300], job_id),
            )
        conn.commit()
        conn.close()


def _rq_delete(job_id: str):
    """Remove a successfully delivered job."""
    with _rq_lock:
        conn = _rq_conn()
        conn.execute("DELETE FROM retry_queue WHERE id=?", (job_id,))
        conn.commit()
        conn.close()


def retry_queue_stats() -> dict:
    """Return queue depth and oldest pending job — for the dashboard."""
    if not _RETRY_DB.exists():
        return {"pending": 0, "oldest": None}
    with _rq_lock:
        conn = _rq_conn()
        pending = conn.execute("SELECT COUNT(*) FROM retry_queue").fetchone()[0]
        oldest  = conn.execute("SELECT MIN(created_at) FROM retry_queue").fetchone()[0]
        conn.close()
    return {
        "pending": pending,
        "oldest":  datetime.fromtimestamp(oldest, tz=timezone.utc).isoformat(timespec="seconds") if oldest else None,
    }


# ─── Background queue drainer ─────────────────────────────────────────────────
_drainer_started = False
_drainer_lock    = threading.Lock()


def _drain_loop():
    """Daemon thread: continuously checks for due retries, sleeps between runs."""
    while True:
        try:
            jobs = _rq_dequeue_due()
            for job in jobs:
                sub = Subscription(
                    id=job["sub_id"], url=job["sub_url"], events=[], active=True,
                )
                ok, status, error = _attempt_http(sub, job["body"], job["sig"], job["event_id"])
                if ok:
                    _rq_delete(job["id"])
                    _log_delivery({
                        "sub_id": job["sub_id"], "url": job["sub_url"],
                        "event_id": job["event_id"], "status": status,
                        "duration_ms": 0, "error": "", "attempt": job["attempt"],
                        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    })
                else:
                    _rq_reschedule(job["id"], job["attempt"], error)
                    _log_delivery({
                        "sub_id": job["sub_id"], "url": job["sub_url"],
                        "event_id": job["event_id"], "status": status,
                        "duration_ms": 0, "error": error, "attempt": job["attempt"],
                        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    })
        except Exception:
            pass
        time.sleep(5)   # poll every 5 s


def _ensure_drainer():
    global _drainer_started
    with _drainer_lock:
        if not _drainer_started:
            threading.Thread(target=_drain_loop, daemon=True, name="webhook-drainer").start()
            _drainer_started = True


def _secret() -> bytes:
    """Reuse the audit hash salt so the operator only manages one secret."""
    s = os.getenv("AUDIT_HASH_SALT") or "lex-indic-dev-only-do-not-deploy"
    return hashlib.sha256(b"lex-indic-webhook-key|" + s.encode()).digest()


# ─── Subscription model ─────────────────────────────────────────────────────
@dataclass
class Subscription:
    id: str
    url: str
    events: list[str]            # which events to fire on this URL
    description: str = ""
    active: bool = True
    created_at: str = ""


# ── JSON-file backend (default) ─────────────────────────────────────────────
def _load_json() -> list[Subscription]:
    if not _SUBS_PATH.exists():
        return []
    return [Subscription(**r) for r in json.loads(_SUBS_PATH.read_text(encoding="utf-8"))]


def _save_json(subs: list[Subscription]):
    _SUBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SUBS_PATH.write_text(
        json.dumps([asdict(s) for s in subs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── DB-backed helpers ───────────────────────────────────────────────────────
def _row_to_sub(row) -> Subscription:
    return Subscription(
        id=row.id, url=row.url, events=list(row.events or []),
        description=row.description or "",
        active=bool(row.active),
        created_at=row.created_at.isoformat(timespec="seconds") if row.created_at else "",
    )


# ── Public API ──────────────────────────────────────────────────────────────
def list_subs() -> list[dict]:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.WebhookSub).order_by(db.WebhookSub.created_at.asc()).all()
            return [asdict(_row_to_sub(r)) for r in rows]
    return [asdict(s) for s in _load_json()]


def add_sub(url: str, events: list[str], description: str = "") -> dict:
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    valid_events = {"analysis.completed", "monitor.digest.ready", "matter.created",
                    "nalsa.registered", "lead.captured"}
    events = [e for e in events if e in valid_events]
    if not events:
        raise ValueError("Provide at least one valid event.")
    new = Subscription(
        id=f"wh_{uuid.uuid4().hex[:10]}",
        url=url.strip()[:500],
        events=events,
        description=description.strip()[:200],
        active=True,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    if db.is_enabled():
        with db.session() as s:
            s.add(db.WebhookSub(
                id=new.id, url=new.url, events=new.events,
                description=new.description, active=new.active,
                created_at=datetime.now(timezone.utc),
            ))
        return asdict(new)
    subs = _load_json()
    subs.append(new)
    _save_json(subs)
    return asdict(new)


def remove_sub(sub_id: str) -> bool:
    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.WebhookSub).filter(db.WebhookSub.id == sub_id).first()
            if not row:
                return False
            s.delete(row)
            return True
    subs = _load_json()
    n = len(subs)
    subs = [s for s in subs if s.id != sub_id]
    if len(subs) == n:
        return False
    _save_json(subs)
    return True


def backend() -> str:
    if not db.is_enabled():
        return "json"
    scheme = db.database_url().split(":")[0].lower()
    return "postgres" if "postgres" in scheme else ("sqlite" if "sqlite" in scheme else scheme)


# ─── Dispatch ──────────────────────────────────────────────────────────────
def _load_active_for_event(event: str) -> list[Subscription]:
    """Backend-aware: returns active subs subscribed to `event`."""
    if db.is_enabled():
        with db.session() as s:
            rows = (s.query(db.WebhookSub)
                     .filter(db.WebhookSub.active == True)  # noqa: E712
                     .all())
            return [_row_to_sub(r) for r in rows if event in (r.events or [])]
    return [s for s in _load_json() if s.active and event in s.events]


def _attempt_http(sub: "Subscription", body: bytes, sig: str, event_id: str) -> tuple[bool, int, str]:
    """Single HTTP attempt. Returns (success, http_status, error_message)."""
    start = time.monotonic()
    status = 0
    error = ""
    try:
        req = urllib.request.Request(
            sub.url,
            data=body,
            headers={
                "Content-Type":       "application/json",
                "User-Agent":         "Lex-Indic-Webhook/1.5",
                "X-Lex-Signature":    sig,
                "X-Lex-Event-Id":     event_id,
                "X-Lex-Subscription": sub.id,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            return (200 <= status < 300), status, ""
    except urllib.error.HTTPError as e:
        status = e.code
        error = str(e)
    except Exception as e:
        error = str(e)
    return False, status, error


def emit(event: str, payload: dict):
    """Emit an event to all active subscribers.

    Day 22: First attempt is synchronous-ish (on a thread); on failure the
    job is written to the SQLite retry queue and the drainer thread handles
    exponential backoff up to MAX_RETRIES times.
    """
    _ensure_drainer()
    subs = _load_active_for_event(event)
    if not subs:
        return
    body = {
        "event": event,
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": payload,
    }
    encoded = json.dumps(body, default=str).encode("utf-8")
    sig = hmac.new(_secret(), encoded, hashlib.sha256).hexdigest()

    for sub in subs:
        threading.Thread(
            target=_first_attempt,
            args=(sub, encoded, sig, body["id"]),
            daemon=True,
            name=f"webhook-{sub.id}",
        ).start()


def _first_attempt(sub: "Subscription", body: bytes, sig: str, event_id: str):
    """First delivery attempt — on failure, enqueue for retry."""
    ok, status, error = _attempt_http(sub, body, sig, event_id)
    duration_ms = 0   # timing inside _attempt_http; not critical for log
    if ok:
        _log_delivery({
            "sub_id": sub.id, "url": sub.url, "event_id": event_id,
            "status": status, "duration_ms": duration_ms,
            "error": "", "attempt": 0,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    else:
        _log_delivery({
            "sub_id": sub.id, "url": sub.url, "event_id": event_id,
            "status": status, "duration_ms": duration_ms,
            "error": error[:200], "attempt": 0,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        # Enqueue for retry — drainer picks it up within 5 s
        _rq_enqueue(sub, body, sig, event_id)


def _log_delivery(record: dict):
    """Append a one-line JSONL record per delivery attempt."""
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def recent_deliveries(limit: int = 50) -> list[dict]:
    """Read the last N entries from deliveries.log — for the dashboard."""
    if not _LOG_PATH.exists():
        return []
    lines = _LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(out))   # newest first
