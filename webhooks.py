"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Outbound webhooks (Day 15)                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Lets a firm register URLs that will receive a signed HTTP POST when
events happen inside Lex-Indic.  Two events implemented:

  - analysis.completed   — every /analyze call that returns OK
  - monitor.digest.ready — when /monitors/api/digest is computed
  - matter.created       — when a new matter is created via /matters/api/matters
  - nalsa.registered     — when a NALSA registration is recorded

Why a customer asks for this: They want to thread Lex-Indic into their
existing systems — Slack channel notifications, Jira ticket creation,
Glific WhatsApp alerts to the SLSA secretariat, internal SIEM ingestion.

DELIVERY: Pure stdlib HTTP POST (urllib).  Each webhook fires
asynchronously via a Python `Thread` so the originating request isn't
blocked.  A HMAC-SHA256 signature is sent in the `X-Lex-Signature` header
so the receiver can verify the payload wasn't tampered with.

STORAGE: outputs/webhooks/subscriptions.json (gitignored — single source
of truth).  No DB, no Postgres yet; the v2.0 migration is mechanical.

RETRY POLICY: Single fire-and-forget for v1.4.  v1.5 should add a
retry queue with exponential backoff — the right abstraction is to
swap the Thread for a Celery task or a small sqlite-backed queue.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SUBS_PATH = Path("outputs") / "webhooks" / "subscriptions.json"
_LOG_PATH  = Path("outputs") / "webhooks" / "deliveries.log"


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


def _load() -> list[Subscription]:
    if not _SUBS_PATH.exists():
        return []
    return [Subscription(**r) for r in json.loads(_SUBS_PATH.read_text(encoding="utf-8"))]


def _save(subs: list[Subscription]):
    _SUBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SUBS_PATH.write_text(
        json.dumps([asdict(s) for s in subs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_subs() -> list[dict]:
    return [asdict(s) for s in _load()]


def add_sub(url: str, events: list[str], description: str = "") -> dict:
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    valid_events = {"analysis.completed", "monitor.digest.ready", "matter.created", "nalsa.registered"}
    events = [e for e in events if e in valid_events]
    if not events:
        raise ValueError("Provide at least one valid event.")
    subs = _load()
    new = Subscription(
        id=f"wh_{uuid.uuid4().hex[:10]}",
        url=url.strip()[:500],
        events=events,
        description=description.strip()[:200],
        active=True,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    subs.append(new)
    _save(subs)
    return asdict(new)


def remove_sub(sub_id: str) -> bool:
    subs = _load()
    n = len(subs)
    subs = [s for s in subs if s.id != sub_id]
    if len(subs) == n:
        return False
    _save(subs)
    return True


# ─── Dispatch ──────────────────────────────────────────────────────────────
def emit(event: str, payload: dict):
    """Fire-and-forget delivery to every active subscription for this event.
    Returns immediately; deliveries happen on a daemon thread."""
    subs = [s for s in _load() if s.active and event in s.events]
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
            target=_deliver,
            args=(sub, encoded, sig, body["id"]),
            daemon=True,
            name=f"webhook-{sub.id}",
        ).start()


def _deliver(sub: Subscription, body: bytes, sig: str, event_id: str):
    """Single attempt.  Failures get logged to deliveries.log but no retry."""
    start = time.monotonic()
    status = 0
    error = ""
    try:
        req = urllib.request.Request(
            sub.url,
            data=body,
            headers={
                "Content-Type":      "application/json",
                "User-Agent":        "Lex-Indic-Webhook/1.0",
                "X-Lex-Signature":   sig,
                "X-Lex-Event-Id":    event_id,
                "X-Lex-Subscription": sub.id,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        error = str(e)
    except Exception as e:
        error = str(e)

    duration_ms = int((time.monotonic() - start) * 1000)
    _log_delivery({
        "sub_id":    sub.id,
        "url":       sub.url,
        "event_id":  event_id,
        "status":    status,
        "duration_ms": duration_ms,
        "error":     error[:200] if error else "",
        "ts":        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


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
