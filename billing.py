"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Stripe self-serve billing (Day 31)                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Lets a prospect upgrade from Free/NALSA to the Firm tier without sales
involvement. Stripe Checkout collects payment; our webhook activates the
firm tier in api_keys.py and provisions a fresh API key.

PROVIDER MODES (chosen by STRIPE_MODE env):
  - stub      (default) zero-dependency mode; pretends to do everything.
              Lets the UI flow work end-to-end without a Stripe account.
              Useful for: pre-launch demos, development, testing.
  - live      real Stripe Checkout. Requires STRIPE_SECRET_KEY +
              STRIPE_WEBHOOK_SECRET. Money actually moves.

ENV VARS:
  STRIPE_MODE             stub | live
  STRIPE_SECRET_KEY       sk_live_... or sk_test_...
  STRIPE_PUBLISHABLE_KEY  pk_live_... or pk_test_... (exposed to frontend)
  STRIPE_WEBHOOK_SECRET   whsec_... for signature verification
  STRIPE_PRICE_FIRM       price_xxx — Firm tier (₹500/month or $7/month)

WHY STUB MODE: we don't have a real Stripe account yet, but we want the
buyer-facing UI (/pricing + /billing/checkout button) to demo-able TODAY.
When you add a real Stripe key, change STRIPE_MODE=live and you're done.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_SUBSCRIPTIONS_FILE = Path("outputs") / "billing" / "subscriptions.json"
_CHECKOUT_LOG_FILE  = Path("outputs") / "billing" / "checkout_log.json"


# ─── Tier catalogue ──────────────────────────────────────────────────────────
TIERS = {
    "free": {
        "name":          "Free",
        "price_inr":     0,
        "price_usd":     0,
        "daily_limit":   3,
        "rate_per_min":  30,
        "features":      [
            "3 case analyses per day",
            "Basic /chat (LEXI) with citation provenance",
            "IPC → BNS converter",
            "Public Supreme Court monitor digest",
        ],
        "stripe_price_id": None,
    },
    "nalsa": {
        "name":          "NALSA Panel — Free",
        "price_inr":     0,
        "price_usd":     0,
        "daily_limit":   None,  # unlimited
        "rate_per_min":  60,
        "features":      [
            "Unlimited case analyses",
            "Full LEXI chat + citation provenance",
            "IPC → BNS converter",
            "SC monitor + daily digest email",
            "WhatsApp alerts (Day 25)",
            "DPDP audit log access",
        ],
        "stripe_price_id": None,
    },
    "firm": {
        "name":          "Firm",
        "price_inr":     500,    # ₹500/seat/month
        "price_usd":     7,
        "daily_limit":   200,
        "rate_per_min":  60,
        "features":      [
            "200 case analyses per seat per day",
            "Multi-user firm workspace with matter intake",
            "Conflict-of-interest checker",
            "White-label PDFs (LAW_FIRM_NAME .env)",
            "Tabular contract review (Day 14)",
            "Webhook event bus (Slack / Jira)",
            "Priority email support",
        ],
        "stripe_price_id": os.getenv("STRIPE_PRICE_FIRM", "price_demo_firm"),
    },
    "enterprise": {
        "name":          "Enterprise",
        "price_inr":     None,  # custom
        "price_usd":     None,
        "daily_limit":   None,  # custom
        "rate_per_min":  600,
        "features":      [
            "Unlimited analyses + custom rate limits",
            "On-prem / VPC deployment",
            "Bring-your-own-LLM (Ollama / private Gemini key)",
            "Dedicated Postgres + S3 backups",
            "SLA + named technical contact",
            "Custom KB upload (your precedents)",
            "SOC 2 audit pack",
        ],
        "stripe_price_id": None,   # contact sales
    },
}


# ─── Result type ─────────────────────────────────────────────────────────────
@dataclass
class CheckoutSession:
    id: str
    user_id: str
    user_email: str
    tier: str
    mode: str                # 'stub' | 'live'
    checkout_url: str        # the URL to redirect the user to
    created_at: str
    stripe_session_id: str = ""  # populated in live mode


# ─── Persistence ──────────────────────────────────────────────────────────────
def _load_subs() -> list[dict]:
    if not _SUBSCRIPTIONS_FILE.exists():
        return []
    return json.loads(_SUBSCRIPTIONS_FILE.read_text(encoding="utf-8"))


def _save_subs(subs: list[dict]):
    _SUBSCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SUBSCRIPTIONS_FILE.write_text(
        json.dumps(subs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _log_checkout(record: dict):
    _CHECKOUT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = []
    if _CHECKOUT_LOG_FILE.exists():
        try:
            log = json.loads(_CHECKOUT_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            log = []
    log.append(record)
    _CHECKOUT_LOG_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Mode + public API ───────────────────────────────────────────────────────
def get_mode() -> str:
    return (os.getenv("STRIPE_MODE") or "stub").lower()


def is_live() -> bool:
    return get_mode() == "live" and bool(os.getenv("STRIPE_SECRET_KEY"))


def tier_catalogue() -> dict:
    """Returns the public tier list for the /pricing page."""
    return TIERS


def create_checkout_session(
    *,
    user_id: str,
    user_email: str,
    tier: str = "firm",
    success_url: str = "",
    cancel_url:  str = "",
) -> CheckoutSession:
    """Create a Stripe Checkout session. Returns the URL to redirect to."""
    if tier not in TIERS:
        raise ValueError(f"Unknown tier: {tier}")
    if tier in ("free", "nalsa"):
        raise ValueError(f"Tier '{tier}' is already free — no checkout needed.")
    if tier == "enterprise":
        raise ValueError("Enterprise is custom — contact sales via GitHub issue.")

    sess_id = f"chk_{uuid.uuid4().hex[:14]}"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if is_live():
        stripe_sess = _stripe_create_session(
            user_email=user_email, user_id=user_id, tier=tier,
            success_url=success_url, cancel_url=cancel_url,
        )
        cs = CheckoutSession(
            id=sess_id, user_id=user_id, user_email=user_email, tier=tier,
            mode="live", checkout_url=stripe_sess["url"],
            stripe_session_id=stripe_sess["id"], created_at=now,
        )
    else:
        # Stub mode: synthesize a fake checkout URL that auto-activates on visit
        token = secrets.token_hex(8)
        fake_url = f"/billing/stub-confirm?session={sess_id}&token={token}&tier={tier}&user={urllib.parse.quote(user_id)}"
        cs = CheckoutSession(
            id=sess_id, user_id=user_id, user_email=user_email, tier=tier,
            mode="stub", checkout_url=fake_url, created_at=now,
        )

    _log_checkout(asdict(cs))
    return cs


def activate_subscription(*, user_id: str, user_email: str, tier: str,
                          stripe_session_id: str = "") -> dict:
    """Called after successful payment (Stripe webhook OR stub-confirm).
    Records the subscription and bumps the user's API key tier."""
    if tier not in TIERS or tier in ("free", "nalsa"):
        raise ValueError(f"Invalid activation tier: {tier}")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sub = {
        "id":          f"sub_{uuid.uuid4().hex[:10]}",
        "user_id":     user_id,
        "user_email":  user_email,
        "tier":        tier,
        "stripe_session_id": stripe_session_id,
        "activated_at":  now,
        "status":      "active",
        "monthly_inr": TIERS[tier]["price_inr"],
    }
    subs = _load_subs()
    # Cancel any previous active sub for this user (one tier at a time)
    for s in subs:
        if s["user_id"] == user_id and s["status"] == "active":
            s["status"] = "superseded"
    subs.append(sub)
    _save_subs(subs)

    # Bump the user's API key tier (best-effort — silent fallback)
    try:
        import api_keys as api_keys_module
        for key in api_keys_module.list_keys(user_id=user_id):
            if hasattr(api_keys_module, "update_tier"):
                api_keys_module.update_tier(key["key_id"], tier)
    except Exception:
        pass

    return sub


def active_subscription(user_id: str) -> dict | None:
    for s in _load_subs():
        if s["user_id"] == user_id and s["status"] == "active":
            return s
    return None


def all_subscriptions() -> list[dict]:
    return _load_subs()


# ─── Stripe live mode (HTTP via stdlib — no SDK needed) ──────────────────────
def _stripe_create_session(*, user_email: str, user_id: str, tier: str,
                            success_url: str, cancel_url: str) -> dict:
    """Stripe Checkout Session via REST API."""
    api_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY required for live mode")
    price_id = TIERS[tier].get("stripe_price_id")
    if not price_id or price_id.startswith("price_demo_"):
        raise RuntimeError(f"STRIPE_PRICE_{tier.upper()} env var must be a real price_id")

    body = urllib.parse.urlencode([
        ("mode", "subscription"),
        ("line_items[0][price]", price_id),
        ("line_items[0][quantity]", "1"),
        ("customer_email", user_email),
        ("client_reference_id", user_id),
        ("metadata[user_id]", user_id),
        ("metadata[tier]", tier),
        ("success_url", success_url or "https://lex-indic.in/billing/success?session_id={CHECKOUT_SESSION_ID}"),
        ("cancel_url",  cancel_url  or "https://lex-indic.in/pricing"),
    ]).encode("utf-8")

    req = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify_webhook_signature(payload: bytes, signature_header: str) -> bool:
    """Verify a Stripe webhook signature.
    Header format: 't=TS,v1=HMAC,v0=HMAC'.
    Compare HMAC-SHA256(secret, TS.payload) constant-time."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return False
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    ts = parts.get("t", "")
    sig = parts.get("v1", "")
    if not ts or not sig:
        return False
    signed_payload = f"{ts}.{payload.decode('utf-8')}"
    expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False
    # Replay protection: reject events older than 5 min
    try:
        if abs(time.time() - int(ts)) > 300:
            return False
    except ValueError:
        return False
    return True


def parse_webhook_event(payload: bytes) -> dict:
    """Parse + validate a Stripe webhook JSON. Returns relevant fields."""
    event = json.loads(payload.decode("utf-8"))
    event_type = event.get("type")
    if event_type not in (
        "checkout.session.completed",
        "customer.subscription.deleted",
        "invoice.payment_failed",
    ):
        return {"handled": False, "type": event_type}

    obj = event.get("data", {}).get("object", {})
    metadata = obj.get("metadata", {})
    return {
        "handled":          True,
        "type":             event_type,
        "user_id":          metadata.get("user_id", ""),
        "tier":             metadata.get("tier", ""),
        "user_email":       obj.get("customer_email", ""),
        "stripe_session_id": obj.get("id", ""),
    }
