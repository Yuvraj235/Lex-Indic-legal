"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Pluggable mail sender (Day 17 of extended roadmap)              ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: One `send()` function with 3 backends behind it:

  MAIL_PROVIDER=stdout   (default — dev mode, prints email to log)
  MAIL_PROVIDER=smtp     (any SMTP server — Gmail app password / SES SMTP / etc.)
  MAIL_PROVIDER=ses      (boto3.ses_v2 — best for AWS deployments)

Used by:
  - auth.py        — login codes (replaces the stdout `_send_code`)
  - monitors.py    — daily SC precedent digest
  - leads.py       — operator notification on new lead
  - matters.py     — optional welcome-email when a matter is created

ENV VARS (only need the ones for your chosen provider):

  Required for all:
    MAIL_FROM=Lex-Indic <noreply@lexindic.in>
    MAIL_REPLY_TO=yuvraj@lexindic.in        (optional but recommended)

  For smtp:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USERNAME=...
    SMTP_PASSWORD=...
    SMTP_USE_TLS=1                          (default 1; set 0 only for testing)

  For ses:
    AWS_REGION=ap-south-1                   (Mumbai)
    (Standard AWS creds chain — env, ~/.aws/credentials, IAM role, etc.)
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Optional


@dataclass
class SendResult:
    ok:        bool
    provider:  str
    message_id: str = ""
    error:     str = ""


def get_provider() -> str:
    return (os.getenv("MAIL_PROVIDER") or "stdout").lower()


def mail_from() -> str:
    return os.getenv("MAIL_FROM") or "Lex-Indic <noreply@lexindic.local>"


def mail_reply_to() -> str:
    return os.getenv("MAIL_REPLY_TO") or ""


def send(*, to: str | list[str], subject: str,
         text: str, html: Optional[str] = None,
         reply_to: Optional[str] = None) -> SendResult:
    """
    Dispatch to the configured provider.  Never raises — returns
    SendResult(ok=False, error=...) so the caller can decide whether to
    treat email failure as fatal (usually it isn't — log and move on).
    """
    if isinstance(to, str):
        to_list = [to]
    else:
        to_list = list(to)
    to_list = [t for t in to_list if t and "@" in t]
    if not to_list:
        return SendResult(False, get_provider(), error="no valid 'to' addresses")

    provider = get_provider()
    try:
        if provider == "stdout":
            return _send_stdout(to_list, subject, text, html, reply_to)
        if provider == "smtp":
            return _send_smtp(to_list, subject, text, html, reply_to)
        if provider == "ses":
            return _send_ses(to_list, subject, text, html, reply_to)
        return SendResult(False, provider, error=f"unknown MAIL_PROVIDER: {provider}")
    except Exception as e:
        return SendResult(False, provider, error=f"{type(e).__name__}: {str(e)[:200]}")


# ────────────────────────────── Providers ──────────────────────────────────
def _build_message(to_list: list[str], subject: str, text: str,
                   html: Optional[str], reply_to: Optional[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"]    = mail_from()
    msg["To"]      = ", ".join(to_list)
    msg["Subject"] = subject
    rt = reply_to or mail_reply_to()
    if rt:
        msg["Reply-To"] = rt
    msg["Date"]    = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _send_stdout(to_list, subject, text, html, reply_to) -> SendResult:
    """Dev: dump the email to stdout + append to outputs/mail/sent.log."""
    msg = _build_message(to_list, subject, text, html, reply_to)
    print("─" * 72, flush=True)
    print(f"  [MAIL → stdout] To: {msg['To']}  Subject: {subject}", flush=True)
    print("─" * 72, flush=True)
    print(text, flush=True)
    print("─" * 72, flush=True)
    # Persist a copy so the operator can review later
    try:
        log = Path("outputs") / "mail" / "sent.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"=== {datetime.now(timezone.utc).isoformat()} ===\n")
            f.write(str(msg))
            f.write("\n\n")
    except Exception:
        pass
    return SendResult(True, "stdout", message_id="local-stdout")


def _send_smtp(to_list, subject, text, html, reply_to) -> SendResult:
    """Standard SMTP — works with Gmail app passwords, SES SMTP creds, etc."""
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USERNAME")
    pwd  = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "1") != "0"
    if not host:
        return SendResult(False, "smtp", error="SMTP_HOST not set")
    msg = _build_message(to_list, subject, text, html, reply_to)

    # Pick implicit SSL for 465, STARTTLS for everything else if use_tls
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as s:
            if user: s.login(user, pwd or "")
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.ehlo()
            if use_tls:
                s.starttls(); s.ehlo()
            if user: s.login(user, pwd or "")
            s.send_message(msg)
    return SendResult(True, "smtp", message_id=msg.get("Message-ID", ""))


def _send_ses(to_list, subject, text, html, reply_to) -> SendResult:
    """AWS SES v2.  boto3 imported lazily so it isn't required in dev."""
    try:
        import boto3
    except ImportError:
        return SendResult(False, "ses",
                          error="boto3 not installed — pip install boto3")
    region = os.getenv("AWS_REGION", "ap-south-1")
    client = boto3.client("sesv2", region_name=region)
    rt = reply_to or mail_reply_to()
    body = {"Text": {"Data": text, "Charset": "UTF-8"}}
    if html:
        body["Html"] = {"Data": html, "Charset": "UTF-8"}
    payload = dict(
        FromEmailAddress=mail_from(),
        Destination={"ToAddresses": to_list},
        Content={"Simple": {"Subject": {"Data": subject, "Charset": "UTF-8"},
                            "Body": body}},
    )
    if rt:
        payload["ReplyToAddresses"] = [rt]
    resp = client.send_email(**payload)
    return SendResult(True, "ses", message_id=resp.get("MessageId", ""))


# ────────────────────────────── Conveniences ───────────────────────────────
def send_login_code(email: str, code: str, *, ttl_minutes: int = 10) -> SendResult:
    """Used by auth.py to deliver the magic-link 6-digit code."""
    text = (
        f"Your Lex-Indic login code is: {code}\n\n"
        f"It is valid for {ttl_minutes} minutes and may be used once.\n\n"
        "If you did not request this code, ignore this email — no further\n"
        "action is needed.\n\n"
        "— Lex-Indic\n"
        "https://github.com/Yuvraj235/Lex-Indic-legal"
    )
    html = f"""<div style="font-family:Inter,Helvetica,sans-serif;color:#0f2850;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="font-family:Georgia,serif;color:#0f2850">Your Lex-Indic login code</h2>
  <p style="font-size:15px;color:#2d3748;line-height:1.6">
    Enter this code at the login page to sign in:
  </p>
  <div style="font-family:ui-monospace,Menlo,monospace;font-size:36px;
              font-weight:700;letter-spacing:6px;color:#b48c28;
              text-align:center;padding:20px;background:#f6f7fb;border-radius:10px;
              margin:18px 0;">
    {code}
  </div>
  <p style="font-size:13px;color:#6b7280">
    Valid for {ttl_minutes} minutes, single use.  If you didn't request this,
    ignore this email.
  </p>
</div>"""
    return send(to=email, subject=f"Lex-Indic login code: {code}",
                text=text, html=html)


def send_lead_notification(operator_email: str, lead: dict) -> SendResult:
    """Used by /try/submit to notify the operator of a new prospect."""
    text = (
        "New Lex-Indic prospect:\n\n"
        f"  Name:   {lead.get('full_name')}\n"
        f"  Email:  {lead.get('email')}\n"
        f"  Firm:   {lead.get('firm_or_org') or '(not given)'}\n"
        f"  Role:   {lead.get('role') or '(not given)'}\n"
        f"  Heard:  {lead.get('how_heard') or '(not given)'}\n"
        f"  Wants:  {', '.join(lead.get('interests') or []) or '(not specified)'}\n\n"
        f"  Lead ID: {lead.get('id')}\n"
        f"  Captured: {lead.get('captured_at')}\n"
    )
    subj = f"New Lex-Indic lead — {lead.get('full_name')} ({lead.get('firm_or_org') or '?'})"
    return send(to=operator_email, subject=subj, text=text)


def send_monitor_digest(email: str, digest_text: str, *, date: str = "") -> SendResult:
    """Plain-text precedent digest — re-uses monitors.format_digest_text()."""
    subj = f"Lex-Indic SC precedent digest — {date or 'today'}"
    return send(to=email, subject=subj, text=digest_text)
