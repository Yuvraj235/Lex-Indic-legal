"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — SMS / WhatsApp alert channel (Day 25)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT
────
India-first push-notification layer.  Three providers:

  stdout  — Development mode.  Prints the message to stdout.  Zero config.
  msg91   — MSG91 is the dominant Indian SMS/WhatsApp gateway (~65% market
             share).  Supports DLT-registered templates (mandatory for Indian
             transactional SMS) and WhatsApp Business API.
  twilio  — Global fallback.  Same Twilio library used in the mailer module.

WHY SMS/WHATSAPP SPECIFICALLY FOR INDIA
────────────────────────────────────────
  - 70,000 NALSA panel advocates — many in Tier-2/3 cities where email
    open-rates are low but WhatsApp penetration is > 95%.
  - Supreme Court hearing date changes happen with < 24h notice — a push
    alert via WhatsApp is the only channel fast enough to matter.
  - Clients (not lawyers) also need case status updates — sharing a PDF
    link over WhatsApp is how Indian legal consumers actually work.

TEMPLATE SYSTEM
───────────────
Every SMS/WhatsApp must use a DLT-approved template in India (TRAI mandate).
We maintain a tiny template registry below.  Templates are approved once;
variable slots are filled at send time.

ENVIRONMENT VARIABLES
─────────────────────
  SMS_PROVIDER         — 'stdout' (default) | 'msg91' | 'twilio'
  MSG91_AUTH_KEY       — MSG91 API auth key
  MSG91_SENDER_ID      — 6-char DLT-registered sender ID (default LEXIND)
  MSG91_TEMPLATE_ID_*  — DLT template IDs (one per message type)
  TWILIO_ACCOUNT_SID   — Twilio account SID
  TWILIO_AUTH_TOKEN    — Twilio auth token
  TWILIO_FROM_NUMBER   — Twilio sending number (+91...)
  TWILIO_WA_FROM       — Twilio WhatsApp-enabled number (whatsapp:+14155...)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone


# ─── Result type ─────────────────────────────────────────────────────────────
@dataclass
class SmsResult:
    ok: bool
    provider: str
    message_id: str = ""
    error: str = ""


# ─── Template registry ────────────────────────────────────────────────────────
# Each template has a 'text' with {placeholders} and optional 'template_id'
# for DLT-registered MSG91 templates.  Placeholders are positional, matching
# the order expected by MSG91's variable substitution API.
TEMPLATES = {
    "digest_alert": {
        "text": (
            "Lex-Indic SC Monitor: {hits} Supreme Court ruling(s) matched "
            "your matter '{label}' today. View digest: {url}"
        ),
        "template_id": os.getenv("MSG91_TEMPLATE_ID_DIGEST", ""),
    },
    "case_update": {
        "text": (
            "Lex-Indic: Your matter {matter_id} status changed to '{status}'. "
            "Lawyer: {lawyer}. View: {url}"
        ),
        "template_id": os.getenv("MSG91_TEMPLATE_ID_CASE", ""),
    },
    "nalsa_welcome": {
        "text": (
            "Welcome to Lex-Indic! Your NALSA panel account is active. "
            "Get unlimited free legal AI at {url}. Panel ID: {panel_id}"
        ),
        "template_id": os.getenv("MSG91_TEMPLATE_ID_NALSA_WELCOME", ""),
    },
    "magic_link": {
        "text": (
            "Your Lex-Indic login code is {code}. Valid for {ttl} minutes. "
            "Do not share this code."
        ),
        "template_id": os.getenv("MSG91_TEMPLATE_ID_LOGIN", ""),
    },
}


def _provider() -> str:
    return os.getenv("SMS_PROVIDER", "stdout").lower().strip()


def _normalise_phone(phone: str) -> str:
    """Strip spaces/dashes, ensure +91 prefix for Indian numbers."""
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if digits.startswith("+"):
        return digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    return "+" + digits


# ─── Public send function ─────────────────────────────────────────────────────
def send(
    *,
    to: str,
    template: str,
    variables: dict[str, str] | None = None,
    channel: str = "sms",   # "sms" | "whatsapp"
) -> SmsResult:
    """
    Send an SMS or WhatsApp message using a registered template.

    Args:
        to:        Recipient phone number (10-digit or +91...)
        template:  Key in TEMPLATES dict
        variables: Dict of placeholder substitutions for the template text
        channel:   'sms' or 'whatsapp'
    """
    if not to:
        return SmsResult(ok=False, provider=_provider(), error="'to' phone number is required")
    if template not in TEMPLATES:
        return SmsResult(ok=False, provider=_provider(),
                         error=f"Unknown template '{template}'. Available: {list(TEMPLATES)}")

    phone = _normalise_phone(to)
    tmpl  = TEMPLATES[template]
    text  = tmpl["text"]
    if variables:
        try:
            text = text.format(**variables)
        except KeyError as e:
            return SmsResult(ok=False, provider=_provider(),
                             error=f"Missing template variable: {e}")

    p = _provider()
    if p == "msg91":
        return _send_msg91(phone, text, tmpl.get("template_id", ""), channel)
    elif p == "twilio":
        return _send_twilio(phone, text, channel)
    else:
        return _send_stdout(phone, text, channel)


# ─── Provider: stdout ─────────────────────────────────────────────────────────
def _send_stdout(phone: str, text: str, channel: str) -> SmsResult:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    channel_icon = "📱" if channel == "sms" else "💬"
    print(
        f"[{ts}] {channel_icon} SMS/stdout → {phone}\n"
        f"  {text}\n"
    )
    return SmsResult(ok=True, provider="stdout", message_id=f"stdout_{ts}")


# ─── Provider: MSG91 ─────────────────────────────────────────────────────────
def _send_msg91(phone: str, text: str, template_id: str, channel: str) -> SmsResult:
    auth_key   = os.getenv("MSG91_AUTH_KEY", "")
    sender_id  = os.getenv("MSG91_SENDER_ID", "LEXIND")
    if not auth_key:
        return SmsResult(ok=False, provider="msg91",
                         error="MSG91_AUTH_KEY not set")

    # Strip the leading + for MSG91 (expects 91XXXXXXXXXX)
    mobile = phone.lstrip("+")

    if channel == "whatsapp":
        # MSG91 WhatsApp API (v2)
        url  = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
        body = json.dumps({
            "integrated_number": os.getenv("MSG91_WA_NUMBER", ""),
            "content_type": "template",
            "payload": {
                "messaging_product": "whatsapp",
                "type": "template",
                "template": {
                    "name": template_id or "lex_indic_default",
                    "language": {"code": "en"},
                    "components": [{"type": "body", "parameters": [
                        {"type": "text", "text": text}
                    ]}],
                },
                "to": mobile,
            },
        }).encode("utf-8")
    else:
        # MSG91 SMS API (v5)
        url  = "https://api.msg91.com/api/v5/flow/"
        body = json.dumps({
            "template_id": template_id,
            "short_url":   "0",
            "realTimeResponse": "1",
            "recipients": [{"mobiles": mobile, "VAR1": text}],
        }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Content-Type":  "application/json",
                "authkey":       auth_key,
                "accept":        "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            msg_id = str(resp_data.get("request_id") or resp_data.get("message_id") or "")
            return SmsResult(ok=True, provider="msg91", message_id=msg_id)
    except urllib.error.HTTPError as e:
        body_err = ""
        try:
            body_err = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        return SmsResult(ok=False, provider="msg91",
                         error=f"HTTP {e.code}: {body_err}")
    except Exception as exc:
        return SmsResult(ok=False, provider="msg91", error=str(exc)[:200])


# ─── Provider: Twilio ─────────────────────────────────────────────────────────
def _send_twilio(phone: str, text: str, channel: str) -> SmsResult:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN",  "")
    if not account_sid or not auth_token:
        return SmsResult(ok=False, provider="twilio",
                         error="TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set")

    if channel == "whatsapp":
        from_num = os.getenv("TWILIO_WA_FROM", "")
        to_num   = f"whatsapp:{phone}"
    else:
        from_num = os.getenv("TWILIO_FROM_NUMBER", "")
        to_num   = phone

    if not from_num:
        return SmsResult(ok=False, provider="twilio",
                         error="TWILIO_FROM_NUMBER / TWILIO_WA_FROM not set")

    url  = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = urllib.parse.urlencode({"To": to_num, "From": from_num, "Body": text}).encode("utf-8")

    import base64
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    try:
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            return SmsResult(ok=True, provider="twilio",
                             message_id=resp_data.get("sid", ""))
    except urllib.error.HTTPError as e:
        err = ""
        try:
            err = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        return SmsResult(ok=False, provider="twilio",
                         error=f"HTTP {e.code}: {err}")
    except Exception as exc:
        return SmsResult(ok=False, provider="twilio", error=str(exc)[:200])


# ─── Convenience helpers ──────────────────────────────────────────────────────
def send_digest_alert(phone: str, label: str, hits: int,
                      url: str = "https://app.lex-indic.in/monitors",
                      channel: str = "whatsapp") -> SmsResult:
    return send(
        to=phone, template="digest_alert", channel=channel,
        variables={"hits": str(hits), "label": label, "url": url},
    )


def send_magic_link_sms(phone: str, code: str, ttl_minutes: int = 10) -> SmsResult:
    return send(
        to=phone, template="magic_link", channel="sms",
        variables={"code": code, "ttl": str(ttl_minutes)},
    )


def send_nalsa_welcome(phone: str, panel_id: str,
                       url: str = "https://app.lex-indic.in") -> SmsResult:
    return send(
        to=phone, template="nalsa_welcome", channel="whatsapp",
        variables={"url": url, "panel_id": panel_id},
    )
