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
import ipaddress
import json
import secrets
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import db   # Day-21 dual-backend; transparent when DATABASE_URL unset
import envmode

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
            live_ids = {s.id for s in _all_subs()} if jobs else set()
            for job in jobs:
                if job["sub_id"] not in live_ids:   # unsubscribed since: stop retrying
                    _rq_delete(job["id"])
                    continue
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
        except Exception as e:  # noqa: BLE001 — the drainer must keep running
            print(f"  [webhooks] retry drain failed: {e}", flush=True)
        time.sleep(5)   # poll every 5 s


def _ensure_drainer():
    global _drainer_started
    with _drainer_lock:
        if not _drainer_started:
            threading.Thread(target=_drain_loop, daemon=True, name="webhook-drainer").start()
            _drainer_started = True


def _secret() -> bytes:
    """Deployment-wide signing key — only for subscriptions created before
    per-subscription secrets existed."""
    return hashlib.sha256(b"lex-indic-webhook-key|" + envmode.secret_key().encode()).digest()


# ─── Target validation (SSRF guard) ─────────────────────────────────────────
# A subscriber chooses the URL our server POSTs to, so without these checks a
# subscription could point at http://169.254.169.254/ (cloud metadata), a
# database on localhost, or the office LAN. Rules: https only, no credentials
# in the URL, and every address the host resolves to must be public. The check
# runs at subscribe time and again before every delivery (DNS can change), and
# redirects are never followed (a public URL could 302 to a private one).
def _resolve_host(host: str, port: int) -> list[str]:
    try:
        return sorted({ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except socket.gaierror:
        raise ValueError(f"Could not resolve host {host!r}.")


def _is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%", 1)[0])
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_target(url: str) -> str:
    """Return the cleaned URL, or raise ValueError saying why it's refused.
    LEX_ENV=development also allows http:// and private addresses so a
    receiver on the developer's own machine can be tested."""
    url = (url or "").strip()
    parts = urllib.parse.urlsplit(url)
    dev = envmode.is_dev()
    if parts.scheme != "https" and not (dev and parts.scheme == "http"):
        raise ValueError("URL must start with https://")
    if not parts.hostname:
        raise ValueError("URL must include a host name.")
    if parts.username or parts.password:
        raise ValueError("URL must not contain a username or password.")
    if not dev:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if not all(_is_public(a) for a in _resolve_host(parts.hostname, port)):
            raise ValueError("URL must resolve to a public internet address.")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None   # a 3xx surfaces as an HTTPError → failed delivery


_OPENER = urllib.request.build_opener(_NoRedirect)


# ─── Subscription model ─────────────────────────────────────────────────────
@dataclass
class Subscription:
    id: str
    url: str
    events: list[str]            # which events to fire on this URL
    description: str = ""
    active: bool = True
    created_at: str = ""
    # Tenant: the firm that owns this subscription, or "*" for the operator
    # (admin token), which receives every event. "" = legacy, receives none.
    firm_id: str = ""
    # Per-subscription signing secret, shown to the creator once. Legacy
    # subscriptions without one are signed with the deployment-wide key.
    secret: str = ""


def _public(sub: "Subscription") -> dict:
    """A subscription as the API lists it — never the signing secret."""
    d = asdict(sub)
    d.pop("secret", None)
    return d


def _signing_key(sub: "Subscription") -> bytes:
    return sub.secret.encode() if sub.secret else _secret()


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
        firm_id=getattr(row, "firm_id", "") or "",
        secret=getattr(row, "secret", "") or "",
    )


def _visible(sub: "Subscription", firm_id: str | None) -> bool:
    """firm_id=None is the operator's view (everything)."""
    return firm_id is None or sub.firm_id == firm_id


# ── Public API ──────────────────────────────────────────────────────────────
def _all_subs() -> list[Subscription]:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.WebhookSub).order_by(db.WebhookSub.created_at.asc()).all()
            return [_row_to_sub(r) for r in rows]
    return _load_json()


def list_subs(firm_id: str | None = None) -> list[dict]:
    return [_public(s) for s in _all_subs() if _visible(s, firm_id)]


def add_sub(url: str, events: list[str], description: str = "", *,
            firm_id: str) -> dict:
    """Create a subscription owned by firm_id ("*" = operator). The returned
    dict is the only time the signing secret is shown."""
    if not firm_id:
        raise ValueError("A subscription must belong to a firm.")
    url = validate_target(url)
    valid_events = {"analysis.completed", "monitor.digest.ready", "matter.created",
                    "nalsa.registered", "lead.captured",
                    # Day 32: billing event types
                    "firm.subscribed", "firm.cancelled", "payment.failed",
                    "subscription.tier_changed"}
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
        firm_id=firm_id,
        secret="whsec_" + secrets.token_hex(24),
    )
    if db.is_enabled():
        with db.session() as s:
            s.add(db.WebhookSub(
                id=new.id, url=new.url, events=new.events,
                description=new.description, active=new.active,
                created_at=datetime.now(timezone.utc),
                firm_id=new.firm_id, secret=new.secret,
            ))
        return asdict(new)
    subs = _load_json()
    subs.append(new)
    _save_json(subs)
    return asdict(new)


def remove_sub(sub_id: str, firm_id: str | None = None) -> bool:
    """Delete a subscription the caller owns (firm_id=None: operator, any)."""
    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.WebhookSub).filter(db.WebhookSub.id == sub_id).first()
            if not row or not _visible(_row_to_sub(row), firm_id):
                return False
            s.delete(row)
            return True
    subs = _load_json()
    target = next((s for s in subs if s.id == sub_id), None)
    if not target or not _visible(target, firm_id):
        return False
    _save_json([s for s in subs if s.id != sub_id])
    return True


def backend() -> str:
    if not db.is_enabled():
        return "json"
    scheme = db.database_url().split(":")[0].lower()
    return "postgres" if "postgres" in scheme else ("sqlite" if "sqlite" in scheme else scheme)


# ─── Dispatch ──────────────────────────────────────────────────────────────
def _load_active_for_event(event: str, firm_id: str | None) -> list[Subscription]:
    """Active subs for `event` that may see it: the operator's ("*") always,
    a firm's only for that firm's own events."""
    return [s for s in _all_subs()
            if s.active and event in s.events
            and (s.firm_id == "*" or (firm_id and s.firm_id == firm_id))]


def _attempt_http(sub: "Subscription", body: bytes, sig: str, event_id: str) -> tuple[bool, int, str]:
    """Single HTTP attempt. Returns (success, http_status, error_message)."""
    status = 0
    error = ""
    # Receiver should reject deliveries where X-Lex-Timestamp is older than 5 minutes
    # to prevent replay attacks. Timestamp is included inside the signed body too.
    ts_header = str(int(time.time()))
    try:
        validate_target(sub.url)   # re-check: the host's DNS may have changed
    except ValueError as e:
        return False, 0, f"blocked: {e}"
    try:
        req = urllib.request.Request(
            sub.url,
            data=body,
            headers={
                "Content-Type":       "application/json",
                "User-Agent":         "Lex-Indic-Webhook/1.6",
                "X-Lex-Signature":    sig,
                "X-Lex-Event-Id":     event_id,
                "X-Lex-Subscription": sub.id,
                "X-Lex-Timestamp":    ts_header,
            },
            method="POST",
        )
        with _OPENER.open(req, timeout=10) as resp:
            status = resp.status
            return (200 <= status < 300), status, ""
    except urllib.error.HTTPError as e:
        status = e.code
        error = str(e)
    except Exception as e:
        error = str(e)
    return False, status, error


def verify_signature(body: bytes, signature_header: str,
                     timestamp_header: str = "", max_age_seconds: int = 300,
                     secret: str = "") -> bool:
    """Receiver-side helper. Returns True iff:
       1. HMAC-SHA256(secret, body) matches X-Lex-Signature header
          (constant-time compare), AND
       2. X-Lex-Timestamp is within max_age_seconds of now (replay protection).

    `secret` is the subscription's whsec_… value (shown once at creation);
    omit it only for legacy subscriptions signed with the deployment key.
    """
    if not signature_header:
        return False
    key = secret.encode() if secret else _secret()
    expected = hmac.new(key, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        return False
    if timestamp_header:
        try:
            ts = int(timestamp_header)
            if abs(time.time() - ts) > max_age_seconds:
                return False
        except ValueError:
            return False
    return True


def emit(event: str, payload: dict, *, firm_id: str | None = None):
    """Emit an event to the subscribers allowed to see it: the firm the event
    belongs to (firm_id) plus operator subscriptions. Events with no firm
    (anonymous runs, leads, billing) go to operator subscriptions only.

    Day 22: First attempt is synchronous-ish (on a thread); on failure the
    job is written to the SQLite retry queue and the drainer thread handles
    exponential backoff up to MAX_RETRIES times.
    """
    _ensure_drainer()
    subs = _load_active_for_event(event, firm_id)
    if not subs:
        return
    body = {
        "event": event,
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": payload,
    }
    encoded = json.dumps(body, default=str).encode("utf-8")

    for sub in subs:
        sig = hmac.new(_signing_key(sub), encoded, hashlib.sha256).hexdigest()
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


def recent_deliveries(limit: int = 50, firm_id: str | None = None) -> list[dict]:
    """The last N delivery records, newest first — only for the caller's own
    subscriptions unless firm_id is None (operator)."""
    if not _LOG_PATH.exists():
        return []
    own = None if firm_id is None else {s["id"] for s in list_subs(firm_id)}
    out = []
    for line in reversed(_LOG_PATH.read_text(encoding="utf-8").splitlines()):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if own is None or rec.get("sub_id") in own:
            out.append(rec)
            if len(out) >= limit:
                break
    return out
