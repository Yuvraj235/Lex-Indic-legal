"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Centralized response shape + validation (Polish sprint)         ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: One module that normalizes:
  - JSON error response shape  (always {error, code, request_id})
  - Currency formatting        (₹1,23,456 Indian grouping)
  - Timestamp formatting       (always ISO 8601 UTC)
  - Input validation helpers   (email, phone, positive int, enum, length)
  - Request ID generation      (UUID injected into every API response)

WHY: Before this module, errors looked different on every endpoint, dates
were sometimes 'now' and sometimes raw datetime objects, currency was raw
integers, and 5 different validation regexes existed. This is the
'one true' helper module.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import jsonify, request


# ─── Request ID middleware ────────────────────────────────────────────────────
def get_or_create_request_id() -> str:
    """Returns the request_id for this Flask request. Generates one if missing."""
    if request and hasattr(request, "request_id"):
        return request.request_id  # type: ignore
    # Caller's responsibility to attach it via @app.before_request
    return f"req_{uuid.uuid4().hex[:14]}"


# ─── Standard JSON response shape ─────────────────────────────────────────────
def ok(data: dict | None = None, status: int = 200):
    """Standard OK response shape: {ok: true, data: {...}, request_id: ...}"""
    body = dict(data or {})
    body.setdefault("ok", True)
    body["request_id"] = get_or_create_request_id()
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["X-Request-Id"] = body["request_id"]
    return resp


def error(message: str, status: int = 400, code: str = "", extra: dict | None = None):
    """Standard error shape: {error, code, status, request_id}"""
    body = {
        "ok":         False,
        "error":      message,
        "code":       code or _default_code_for_status(status),
        "status":     status,
        "request_id": get_or_create_request_id(),
    }
    if extra:
        body.update(extra)
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["X-Request-Id"] = body["request_id"]
    return resp


def _default_code_for_status(status: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        422: "validation_failed",
        429: "rate_limited",
        500: "internal_error",
        502: "bad_gateway",
        503: "service_unavailable",
    }.get(status, "error")


# ─── Validation helpers ───────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[0-9 \-]{10,15}$")
# Allow safe-ish unicode + punctuation, reject control chars + null bytes
_PRINTABLE_RE = re.compile(r"^[^\x00-\x1f\x7f]+$")


def require_string(payload: dict, field: str, *,
                   min_len: int = 1, max_len: int = 5000,
                   strip: bool = True) -> tuple[str | None, str | None]:
    """Returns (value, error). One of the two is None."""
    raw = payload.get(field)
    if raw is None:
        return None, f"Field '{field}' is required."
    if not isinstance(raw, str):
        return None, f"Field '{field}' must be a string."
    val = raw.strip() if strip else raw
    if len(val) < min_len:
        return None, f"Field '{field}' must be at least {min_len} characters."
    if len(val) > max_len:
        return None, f"Field '{field}' must be at most {max_len} characters."
    if not _PRINTABLE_RE.match(val):
        return None, f"Field '{field}' contains invalid control characters."
    return val, None


def require_email(payload: dict, field: str = "email") -> tuple[str | None, str | None]:
    val, err = require_string(payload, field, min_len=4, max_len=200)
    if err:
        return None, err
    if not _EMAIL_RE.match(val):
        return None, f"Field '{field}' is not a valid email address."
    return val.lower(), None


def require_phone(payload: dict, field: str = "phone") -> tuple[str | None, str | None]:
    val, err = require_string(payload, field, min_len=10, max_len=20)
    if err:
        return None, err
    if not _PHONE_RE.match(val):
        return None, f"Field '{field}' must be a 10-15 digit phone number."
    return val, None


def require_enum(payload: dict, field: str,
                 choices: tuple[str, ...]) -> tuple[str | None, str | None]:
    val = payload.get(field)
    if val not in choices:
        return None, f"Field '{field}' must be one of: {list(choices)}"
    return val, None


def require_positive_int(payload: dict, field: str,
                         *, min_val: int = 0, max_val: int = 10**9
                         ) -> tuple[int | None, str | None]:
    raw = payload.get(field)
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return None, f"Field '{field}' must be an integer."
    if val < min_val:
        return None, f"Field '{field}' must be >= {min_val}."
    if val > max_val:
        return None, f"Field '{field}' must be <= {max_val}."
    return val, None


def require_list_of_strings(payload: dict, field: str, *,
                             max_items: int = 50, max_item_len: int = 200
                             ) -> tuple[list[str] | None, str | None]:
    raw = payload.get(field, [])
    if not isinstance(raw, list):
        return None, f"Field '{field}' must be a list."
    if len(raw) > max_items:
        return None, f"Field '{field}' must have at most {max_items} items."
    out: list[str] = []
    for i, x in enumerate(raw):
        if not isinstance(x, str):
            return None, f"Field '{field}[{i}]' must be a string."
        x = x.strip()
        if len(x) > max_item_len:
            return None, f"Field '{field}[{i}]' too long (max {max_item_len})."
        if x:
            out.append(x)
    return out, None


# ─── Formatting helpers ───────────────────────────────────────────────────────
def now_iso() -> str:
    """Current UTC time as ISO 8601 with seconds precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fmt_inr(amount_inr: int | float | None) -> str:
    """₹1,23,456 — Indian grouping (lakh / crore style)."""
    if amount_inr is None:
        return "—"
    try:
        n = int(amount_inr)
    except (TypeError, ValueError):
        return str(amount_inr)
    if n == 0:
        return "₹0"
    # Indian grouping: last 3 digits, then every 2
    s = str(abs(n))
    if len(s) <= 3:
        out = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        # Group rest in 2s
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        out = ",".join(parts) + "," + last3
    return f"{'-' if n < 0 else ''}₹{out}"


def safe_str(val: Any, fallback: str = "—") -> str:
    """Render any value as a string, swallowing None and empty."""
    if val is None or val == "":
        return fallback
    return str(val)
