"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          LEX-INDIC — AUDIT LOGGER                                            ║
║          Append-only JSONL audit trail (DPDP Act 2023 compliance)            ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS FILE DOES:
────────────────────
Logs every /analyze and /chat request to a daily rotating JSONL file. Designed
to satisfy DPDP Act 2023 audit-trail requirements that any law firm, NBFC
compliance team, or legal aid clinic will demand before deploying.

WHAT WE LOG (always):
  - request_id    : UUID; surfaced to the API response so users can reference
                    it in a support ticket
  - ts            : ISO-8601 UTC timestamp
  - endpoint      : "/analyze" or "/chat"
  - client_ip     : for security investigation (DPDP requires breach forensics)
  - user_agent    : truncated to 200 chars
  - story_hash    : SHA-256(deployment_salt + story); for duplicate detection
                    WITHOUT storing PII
  - story_length  : raw character count of the input
  - sources       : list of KB document IDs that RAG retrieved (e.g. "bns_304")
  - model         : the LLM used
  - status        : "ok" or "error"
  - duration_ms   : end-to-end request latency
  - response_chars: size of the model output
  - error         : error message if status=error
  - pdf_filename  : if /analyze produced a PDF

WHAT WE DO NOT LOG (deliberately):
  - The raw client story  — DPDP forbids unnecessary PII retention. The story
                            is already saved to outputs/case_analysis_*.txt
                            for the lawyer's matter file; logging it again
                            here would be a second copy with no purpose.
  - The model's response  — Same reasoning. PDF + .txt are the canonical copy.
  - Source raw text       — These are public BNS sections; logging the IDs is
                            enough to reconstruct what was shown to the user.

CONFIGURATION (.env):
    AUDIT_HASH_SALT  — unique per deployment, so hashes can't be cross-matched
                       across customers. CHANGE THIS for production.
    AUDIT_LOG_DIR    — defaults to outputs/audit/

DAILY ROTATION:
    Files are named outputs/audit/audit-YYYY-MM-DD.log (UTC). 365 files/year.
    Easy to ship to S3 / cold storage / SIEM with one cron job.

CONCURRENCY:
    All writes go through a module-level threading.Lock so two Flask threads
    never interleave a record. Each write is fsync'd so a crash can lose at
    most one in-flight record.
"""

import os
import json
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG (read once at import time)
# ──────────────────────────────────────────────────────────────────────────────

# Salt used when hashing the client story. Must be stable across restarts so
# duplicate-detection works, but unique per deployment so hashes don't collide
# across customers. Default is dev-only; production deployments MUST override.
_AUDIT_SALT = os.getenv(
    "AUDIT_HASH_SALT",
    "lex-indic-default-dev-salt-CHANGE-ME-IN-PRODUCTION",
)

_AUDIT_DIR = Path(os.getenv("AUDIT_LOG_DIR", "outputs/audit"))

_LOCK = threading.Lock()


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _today_log_path() -> Path:
    """Today's log file path. Files rotate at UTC midnight."""
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _AUDIT_DIR / f"audit-{today}.log"


def hash_story(story: str) -> str:
    """
    Salted SHA-256 of the client story, truncated to 32 hex chars for log
    compactness. Used for duplicate detection only — not reversible, not
    intended to resist cryptographic attacks.
    """
    h = hashlib.sha256()
    h.update(_AUDIT_SALT.encode("utf-8"))
    h.update(b"\x00")
    h.update((story or "").encode("utf-8"))
    return f"sha256:{h.hexdigest()[:32]}"


def _normalize_sources(sources) -> list:
    """Sources can come as a list of dicts (from /analyze) or already as IDs."""
    if not sources:
        return []
    out = []
    for s in sources:
        if isinstance(s, dict):
            sid = s.get("id") or s.get("section") or ""
            if sid:
                out.append(sid)
        else:
            out.append(str(s))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def log_request(
    endpoint: str,
    client_ip: str = "",
    user_agent: str = "",
    story: str = "",
    sources=None,
    status: str = "ok",
    duration_ms: int = 0,
    response_chars: int = 0,
    error: str = None,
    pdf_filename: str = None,
    model: str = "llama-3.3-70b-versatile",
    extra: dict = None,
) -> str:
    """
    Append a single audit record and return the request_id.

    Callers should pass the returned request_id back to the user as part of
    the JSON response, so it can be quoted in a support ticket or audit
    review. The request_id is also a join key against this log.
    """
    request_id = str(uuid4())
    record = {
        "request_id":     request_id,
        "ts":             datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "endpoint":       endpoint,
        "client_ip":      client_ip or "",
        "user_agent":     (user_agent or "")[:200],
        "story_hash":     hash_story(story),
        "story_length":   len(story or ""),
        "sources":        _normalize_sources(sources),
        "model":          model,
        "status":         status,
        "duration_ms":    int(duration_ms),
        "response_chars": int(response_chars),
        "error":          (error or None) and str(error)[:500],
        "pdf_filename":   pdf_filename,
    }
    if extra:
        # Keep extra small — this is an audit log, not a debug log
        record["extra"] = {k: v for k, v in extra.items() if v is not None}

    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    path = _today_log_path()

    with _LOCK:
        # Open with "a" (append) — POSIX guarantees atomic append for writes
        # under PIPE_BUF on a single FS, which our line is well under.
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    # fsync can fail on some FS (NFS, tmpfs); the flush still landed
                    pass
        except Exception:
            # Audit logging must NEVER break the request path. If the disk is
            # full or the dir is read-only, swallow the error and let the
            # request succeed. The operator will notice missing log lines.
            pass

    return request_id


def iter_records(date: str = None):
    """
    Yield audit records for a given date (YYYY-MM-DD, default = today, UTC).
    Used by the audit_report CLI.
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = _AUDIT_DIR / f"audit-{date}.log"
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines instead of crashing the report
                continue
