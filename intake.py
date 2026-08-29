"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — WhatsApp intake state machine                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: A small multi-turn intake bot. A client messages on WhatsApp; the bot asks
what/when/where/who one question at a time, and once it has enough it composes a
story the drafting pipeline can act on.

  pure (tested):  parse_inbound(), handle_message(), compose_story(), next_prompt()
  I/O:            load_session() / save_session()  (JSON under outputs/intake/)

Provider-agnostic: parse_inbound understands both Twilio (form: From/Body) and
MSG91-style (JSON) inbound webhooks.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_STORE = Path("outputs/intake")

# Ordered slots the bot collects before a draft can be prepared.
SLOTS = [
    ("incident", "In a sentence or two — what happened?"),
    ("when", "When did this happen? (a date, or roughly)"),
    ("where", "Where did it happen? (city / area / police station)"),
    ("parties", "Who is involved? (names or roles — reply 'skip' if unsure)"),
]
WELCOME = ("Namaste \U0001f64f This is the Lex-Indic intake assistant. "
           "I'll ask a few quick questions to prepare a draft.\n\n")
DONE_MSG = ("Thank you — I have enough to prepare a draft. It will be filed to your "
            "matter and your advocate will review it shortly. ✅")


def parse_inbound(form: dict | None, json_body: dict | None) -> tuple[str | None, str | None]:
    """Extract (sender, text) from a Twilio (form) or MSG91/generic (JSON) webhook."""
    form = form or {}
    jb = json_body or {}
    if form.get("From") or form.get("Body"):                     # Twilio
        sender = (form.get("From") or "").replace("whatsapp:", "").strip()
        return (sender or None), ((form.get("Body") or "").strip() or None)
    sender = (jb.get("mobile") or jb.get("from") or jb.get("sender")
              or jb.get("waNumber") or "")
    text = (jb.get("message") or jb.get("text") or jb.get("content")
            or jb.get("body") or "")
    if isinstance(text, dict):                                   # nested {text:{body}}
        text = text.get("body") or text.get("content") or ""
    return (str(sender).strip() or None), (str(text).strip() or None)


@dataclass
class IntakeSession:
    sender: str
    step: int = 0
    greeted: bool = False
    answers: dict = field(default_factory=dict)
    done: bool = False
    updated_at: float = 0.0


def is_ready(s: IntakeSession) -> bool:
    return s.step >= len(SLOTS)


def next_prompt(s: IntakeSession) -> str:
    return DONE_MSG if is_ready(s) else SLOTS[s.step][1]


def handle_message(s: IntakeSession, text: str) -> tuple[IntakeSession, str]:
    """Advance the intake by one inbound message. Returns (session, reply)."""
    text = (text or "").strip()
    if not s.greeted:                          # first contact → greet + ask slot 0
        s.greeted = True
        return s, WELCOME + SLOTS[0][1]
    if is_ready(s):
        return s, DONE_MSG
    key = SLOTS[s.step][0]
    if text and text.lower() != "skip":
        s.answers[key] = text
    s.step += 1
    if is_ready(s):
        s.done = True
    return s, next_prompt(s)


def compose_story(s: IntakeSession) -> str:
    """Build a free-text story from the collected answers (for the draft pipeline)."""
    a = s.answers
    parts = []
    if a.get("incident"):
        parts.append(a["incident"].rstrip("."))
    if a.get("when"):
        parts.append(f"This happened {a['when']}")
    if a.get("where"):
        parts.append(f"at/near {a['where']}")
    story = ". ".join(parts)
    if a.get("parties"):
        story += f". Parties involved: {a['parties']}"
    return (story + ".").strip()


# ──────────────────────────────────────────────────────────────────────────────
# Session store (JSON)
# ──────────────────────────────────────────────────────────────────────────────
def _safe(sender: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "_", sender or "unknown")


def load_session(sender: str) -> IntakeSession:
    p = _STORE / f"{_safe(sender)}.json"
    if p.exists():
        try:
            return IntakeSession(**json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — corrupt session → start fresh
            pass
    return IntakeSession(sender=sender)


def save_session(s: IntakeSession) -> None:
    _STORE.mkdir(parents=True, exist_ok=True)
    s.updated_at = time.time()
    (_STORE / f"{_safe(s.sender)}.json").write_text(
        json.dumps(asdict(s), ensure_ascii=False), encoding="utf-8")


def clear_session(sender: str) -> None:
    p = _STORE / f"{_safe(sender)}.json"
    if p.exists():
        p.unlink()
