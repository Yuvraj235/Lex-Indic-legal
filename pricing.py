"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Pricing tier enforcement (Day 23)                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT
────
Three tiers for the Lex-Indic SaaS:

  free     — anonymous / unauthenticated users: 3 analyses per day, per IP
  nalsa    — NALSA-empanelled advocates (self-claimed): unlimited analyses
  firm     — law firms paying for a seat: configurable quota per API key
             (default 200 / day; firms can buy more via the sales process)
  internal — operator / admin: unlimited, no logging

WHY
───
Legora charges €50k/seat for law firms with no free tier.  Our moat is:
  1. NALSA free tier → 70,000 advocates try us for free, build the habit
  2. Firm paid tier → sell the admin an annual contract once their team
     is already hooked from the NALSA tier

HOW
───
The check is enforced at the /analyze endpoint (and /api/v1/analyze).
We use the audit log to count today's analyses per identity — so there's
no separate counter store; the existing JSONL audit log does double duty.

Identity priority:
  1. Valid API key  → tier = key['tier']  (firm | internal)
  2. Authenticated session (magic-link) AND is_registered(email)  → nalsa
  3. Authenticated session (not NALSA)  → free (per-session quota)
  4. Anonymous  → free (per-IP quota)

STORAGE: No new file — reads audit log + nalsa registry.

ENV OVERRIDES:
  FREE_DAILY_LIMIT     — override the free-tier daily cap (default 3)
  FIRM_DAILY_LIMIT     — override the firm-tier daily cap (default 200)
  DISABLE_RATE_LIMITS  — set to "1" to disable all limits (local dev)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import nalsa as nalsa_module

_AUDIT_DIR = Path("outputs") / "audit"

FREE_DAILY_LIMIT  = int(os.getenv("FREE_DAILY_LIMIT",  "3"))
FIRM_DAILY_LIMIT  = int(os.getenv("FIRM_DAILY_LIMIT",  "200"))
TIERS             = ("free", "nalsa", "firm", "internal")


def _disabled() -> bool:
    return os.getenv("DISABLE_RATE_LIMITS", "").strip() == "1"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _count_today(identity_key: str, identity_type: str) -> int:
    """Count /analyze calls today for this identity from the audit log."""
    today = _today()
    audit_file = _AUDIT_DIR / f"audit-{today}.log"
    if not audit_file.exists():
        return 0
    count = 0
    try:
        for line in audit_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("endpoint") not in ("/analyze", "/api/v1/analyze"):
                continue
            if rec.get("status") != "ok":
                continue
            extra = rec.get("extra") or {}
            if identity_type == "ip":
                if rec.get("client_ip") == identity_key:
                    count += 1
            elif identity_type == "email":
                if extra.get("user_email") == identity_key:
                    count += 1
            elif identity_type == "api_key":
                if extra.get("api_key_id") == identity_key:
                    count += 1
    except Exception:
        pass
    return count


def check(
    *,
    client_ip: str = "",
    user_email: str = "",
    api_key_id: str = "",
    api_key_tier: str = "",
) -> dict:
    """
    Determine whether a new /analyze request is allowed.

    Returns:
        {
            "allowed":  True | False,
            "tier":     "free" | "nalsa" | "firm" | "internal",
            "used":     <analyses used today>,
            "limit":    <daily limit | None for unlimited>,
            "reason":   <human-readable string, only when allowed=False>,
        }
    """
    if _disabled():
        return {"allowed": True, "tier": "internal", "used": 0, "limit": None, "reason": ""}

    # 1. API key tier
    if api_key_id and api_key_tier:
        if api_key_tier == "internal":
            return {"allowed": True, "tier": "internal", "used": 0, "limit": None, "reason": ""}
        if api_key_tier == "nalsa":
            return {"allowed": True, "tier": "nalsa", "used": 0, "limit": None, "reason": ""}
        # firm tier
        limit = FIRM_DAILY_LIMIT
        used  = _count_today(api_key_id, "api_key")
        if used >= limit:
            return {
                "allowed": False, "tier": "firm",
                "used": used, "limit": limit,
                "reason": (
                    f"Daily limit of {limit} analyses reached for this API key. "
                    "Contact sales@lex-indic.in to increase your quota."
                ),
            }
        return {"allowed": True, "tier": "firm", "used": used, "limit": limit, "reason": ""}

    # 2. Authenticated session — NALSA empanelled?
    if user_email and nalsa_module.is_registered(user_email):
        return {"allowed": True, "tier": "nalsa", "used": 0, "limit": None, "reason": ""}

    # 3. Authenticated session — not NALSA → free (session-level, track by email)
    if user_email:
        used  = _count_today(user_email, "email")
        if used >= FREE_DAILY_LIMIT:
            return {
                "allowed": False, "tier": "free",
                "used": used, "limit": FREE_DAILY_LIMIT,
                "reason": (
                    f"Free accounts get {FREE_DAILY_LIMIT} analyses per day. "
                    "Register your NALSA panel ID at /nalsa for unlimited free access, "
                    "or contact sales@lex-indic.in for a firm subscription."
                ),
            }
        return {"allowed": True, "tier": "free", "used": used, "limit": FREE_DAILY_LIMIT, "reason": ""}

    # 4. Anonymous — IP-based
    if client_ip:
        used = _count_today(client_ip, "ip")
        if used >= FREE_DAILY_LIMIT:
            return {
                "allowed": False, "tier": "free",
                "used": used, "limit": FREE_DAILY_LIMIT,
                "reason": (
                    f"Anonymous users get {FREE_DAILY_LIMIT} free analyses per day. "
                    "Sign up (free) to continue, or register your NALSA panel ID for unlimited access."
                ),
            }
        return {"allowed": True, "tier": "free", "used": used, "limit": FREE_DAILY_LIMIT, "reason": ""}

    # Fallback — no identity at all (shouldn't happen in prod with auth middleware)
    return {"allowed": True, "tier": "free", "used": 0, "limit": FREE_DAILY_LIMIT, "reason": ""}


def tier_label(tier: str) -> str:
    """Human-readable tier label for UI display."""
    return {
        "free":     "Free",
        "nalsa":    "NALSA Panel (Free)",
        "firm":     "Firm",
        "internal": "Internal",
    }.get(tier, tier)
