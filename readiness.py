"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Go-live readiness audit                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Every integration in Lex-Indic is real but sits behind a stub-default env
flag (LLM_PROVIDER, ECOURTS_PROVIDER, STRIPE_MODE, MAIL_PROVIDER, SMS_PROVIDER,
DATABASE_URL).  That's great for dev, but it means a prospect can't tell what's
actually wired — and an operator can't tell what's left to flip before launch.

This module answers both: gather_readiness() reports, for each subsystem, whether
it is in DEMO (stub) or LIVE mode and whether it is production-ready (mode flipped
AND the required key present).  It drives /admin/readiness and tools/readiness.py,
and the same `mode` is what the UI uses to show a "Demo data" badge.

Pure: reads os.environ only, no I/O — easy to unit-test.
"""

from __future__ import annotations

import os


def _live_subsystem(name: str, mode: str, *, live: bool, ready: bool,
                    detail: str) -> dict:
    return {"subsystem": name, "mode": mode, "live": live, "ready": ready,
            "detail": detail}


def gather_readiness() -> dict:
    """Return per-subsystem demo/live + production-ready status, plus a summary."""
    items: list[dict] = []

    llm = (os.getenv("LLM_PROVIDER") or "groq").lower()
    items.append(_live_subsystem(
        "LLM", llm, live=llm in ("groq", "ollama"),
        ready=bool(os.getenv("GROQ_API_KEY")) if llm == "groq" else True,
        detail="groq (cloud) needs GROQ_API_KEY; ollama (local) is self-hosted."))

    ec = (os.getenv("ECOURTS_PROVIDER") or "stub").lower()
    items.append(_live_subsystem(
        "e-Courts CNR lookup", ec, live=ec == "live",
        ready=ec == "live" and bool(os.getenv("ECOURTS_API_KEY")),
        detail="stub = 3 demo cases. live needs ECOURTS_API_KEY."))

    sm = (os.getenv("STRIPE_MODE") or "stub").lower()
    items.append(_live_subsystem(
        "Billing (Stripe)", sm, live=sm == "live",
        ready=sm == "live" and bool(os.getenv("STRIPE_SECRET_KEY")),
        detail="stub = no real charges. live needs STRIPE_SECRET_KEY."))

    mp = (os.getenv("MAIL_PROVIDER") or "stdout").lower()
    items.append(_live_subsystem(
        "Email", mp, live=mp in ("smtp", "ses"), ready=mp in ("smtp", "ses"),
        detail="stdout prints to console; use smtp or ses for real delivery."))

    sp = (os.getenv("SMS_PROVIDER") or "stdout").lower()
    items.append(_live_subsystem(
        "SMS / WhatsApp", sp, live=sp in ("msg91", "twilio"),
        ready=sp in ("msg91", "twilio"),
        detail="stdout prints; msg91 needs DLT templates; twilio needs SID/token."))

    db_url = os.getenv("DATABASE_URL") or ""
    db_mode = ("postgres" if "postgres" in db_url
               else "sqlite" if db_url else "json")
    items.append(_live_subsystem(
        "Database", db_mode, live=db_mode in ("postgres", "sqlite"),
        ready=db_mode == "postgres",
        detail="json files (dev) / sqlite / postgres (recommended for prod)."))

    salt = os.getenv("AUDIT_HASH_SALT") or ""
    weak = (not salt) or "dev" in salt.lower() or len(salt) < 16
    items.append(_live_subsystem(
        "Audit-log salt", "weak" if weak else "set", live=not weak, ready=not weak,
        detail="AUDIT_HASH_SALT must be a long random per-deployment secret."))

    admin = os.getenv("ADMIN_TOKEN") or ""
    items.append(_live_subsystem(
        "Admin token", "set" if admin else "unset", live=bool(admin),
        ready=bool(admin),
        detail="ADMIN_TOKEN gates /admin, /dashboard and /cron in production."))

    ready = sum(1 for i in items if i["ready"])
    stubbed = sum(1 for i in items if not i["live"])
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "ready": ready,
            "stubbed": stubbed,
            "go_live": ready == len(items),
        },
    }
