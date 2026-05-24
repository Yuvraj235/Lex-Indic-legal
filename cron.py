"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Scheduled jobs / cron runner (Day 24)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT
────
Three scheduled jobs, all run by adding lines to the server's crontab or
by calling them from a container entrypoint:

  1. digest_email      — Run the SC-monitor digest and email it to every
                         registered user who has at least one watch-matter.
                         Recommended: 07:00 IST every day.

  2. nalsa_csv_export  — Export the NALSA registry to
                         outputs/nalsa/registry_<date>.csv for spot-checking.
                         Recommended: 00:00 every Sunday.

  3. cleanup_audit     — Delete audit logs older than AUDIT_RETENTION_DAYS
                         (default 90).  Recommended: 02:00 every day.

HOW TO WIRE IN PRODUCTION
─────────────────────────
Add to /etc/cron.d/lex-indic (or equivalent):

    # IST = UTC+5:30, so 07:00 IST = 01:30 UTC
    30 1 * * *  www-data  cd /opt/lex-indic && python3 cron.py digest_email >> /var/log/lex-indic-cron.log 2>&1
    0  0 * * 0  www-data  cd /opt/lex-indic && python3 cron.py nalsa_csv   >> /var/log/lex-indic-cron.log 2>&1
    0  2 * * *  www-data  cd /opt/lex-indic && python3 cron.py cleanup     >> /var/log/lex-indic-cron.log 2>&1

Or use the --all flag to run all three (useful in a Celery beat / APScheduler setup):

    python3 cron.py --all

ENVIRONMENT VARIABLES
─────────────────────
  DIGEST_EMAIL_TO      — Comma-separated override list of email addresses.
                         If unset, digest is sent to all users with ≥1 watch-matter.
  AUDIT_RETENTION_DAYS — Default 90. Logs older than this are deleted.
  MAIL_PROVIDER        — Inherited from mailer.py (stdout | smtp | ses).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import monitors as monitors_module
import nalsa as nalsa_module
import mailer as mailer_module
import auth as auth_module


# ─── 1. Daily digest email ────────────────────────────────────────────────────
def digest_email(*, dry_run: bool = False) -> dict:
    """
    Run the SC-monitor digest and email it to users who have watch-matters.
    Returns a summary dict for logging.
    """
    digest = monitors_module.run_digest()
    total_hits = digest.get("totals", {}).get("total_hits", 0)
    matters_with_hits = digest.get("totals", {}).get("matters_with_hits", 0)

    # Format the plain-text email body
    text_body = _format_digest_email(digest)

    # Recipients: DIGEST_EMAIL_TO override, or all users who have watch-matters
    override = os.getenv("DIGEST_EMAIL_TO", "").strip()
    if override:
        recipients = [e.strip() for e in override.split(",") if e.strip()]
    else:
        recipients = _get_digest_recipients()

    if not recipients:
        return {"status": "no_recipients", "hits": total_hits, "sent": 0}

    subject = (
        f"Lex-Indic SC Monitor | {matters_with_hits} matter(s) flagged today"
        if total_hits > 0
        else "Lex-Indic SC Monitor | No new rulings matched today"
    )

    sent = 0
    errors = []
    for email in recipients:
        if dry_run:
            print(f"[DRY RUN] Would email {email}: {subject}")
            sent += 1
            continue
        result = mailer_module.send(to=email, subject=subject, text=text_body)
        if result.ok:
            sent += 1
        else:
            errors.append(f"{email}: {result.error}")

    return {
        "status": "ok" if not errors else "partial",
        "hits":   total_hits,
        "matters_with_hits": matters_with_hits,
        "sent":   sent,
        "errors": errors,
        "date":   digest["date"],
    }


def _get_digest_recipients() -> list[str]:
    """Return emails of users with at least one watch-matter registered."""
    # If auth module has a user list, use it; else fall back to NALSA registrants
    emails: set[str] = set()
    try:
        users = auth_module.list_users() if hasattr(auth_module, "list_users") else []
        for u in users:
            e = (u.get("email") or "").strip().lower()
            if e:
                emails.add(e)
    except Exception:
        pass
    # Always include NALSA registrants who consented to contact
    try:
        for reg in nalsa_module.list_all():
            if reg.get("consent_to_contact") and reg.get("email"):
                emails.add(reg["email"].strip().lower())
    except Exception:
        pass
    return sorted(emails)


def _format_digest_email(digest: dict) -> str:
    """Format the monitor digest as a plain-text email body."""
    lines = [
        "LEX-INDIC — DAILY SUPREME COURT MONITOR DIGEST",
        f"Date: {digest['date']}",
        "=" * 60,
        "",
    ]
    matters = digest.get("matters", [])
    if not matters:
        lines += [
            "No watch-matters registered yet.",
            "",
            "Register matters to watch at: /monitors",
        ]
    else:
        for block in matters:
            m = block.get("matter", {})
            hits = block.get("hits", [])
            lines.append(f"MATTER: {m.get('label', 'Untitled')}")
            lines.append(f"Keywords: {', '.join(m.get('keywords', []))}")
            lines.append(f"Sections: {', '.join(m.get('sections', []))}")
            if hits:
                lines.append(f"  {len(hits)} ruling(s) matched:")
                for h in hits[:5]:
                    r = h.get("ruling", {})
                    score = h.get("score", 0)
                    lines.append(
                        f"  [{int(score*100):3d}%] {r.get('date','?')} — "
                        f"{r.get('title','?')} ({r.get('neutral_citation','')})"
                    )
                    reasons = h.get("reasons", [])
                    if reasons:
                        lines.append(f"         ↳ {reasons[0]}")
                if len(hits) > 5:
                    lines.append(f"  ... and {len(hits)-5} more")
            else:
                lines.append("  No new matching rulings today.")
            lines.append("")

    totals = digest.get("totals", {})
    lines += [
        "-" * 60,
        f"Total matters watched: {totals.get('matters_count', 0)}",
        f"Total ruling hits: {totals.get('total_hits', 0)}",
        "",
        "View full digest: http://localhost:8080/monitors",
        "Unsubscribe: reply STOP or update your preferences at /profile",
        "",
        "— Lex-Indic by Lex-Indic Technologies",
        "  Building the AI Junior Associate for Indian Law Firms",
    ]
    return "\n".join(lines)


# ─── 2. NALSA CSV export ──────────────────────────────────────────────────────
def nalsa_csv_export() -> dict:
    """Export the NALSA registry to a dated CSV file."""
    csv_data = nalsa_module.export_csv()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = Path("outputs") / "nalsa"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"registry_{today}.csv"
    out_path.write_text(csv_data, encoding="utf-8")
    row_count = csv_data.count("\n") - 1  # subtract header
    return {
        "status": "ok",
        "path":   str(out_path),
        "rows":   max(row_count, 0),
    }


# ─── 3. Audit log cleanup ─────────────────────────────────────────────────────
def cleanup_audit() -> dict:
    """Delete audit log files older than AUDIT_RETENTION_DAYS."""
    retention_days = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    audit_dir = Path("outputs") / "audit"
    if not audit_dir.exists():
        return {"status": "ok", "deleted": 0}

    deleted = 0
    for f in audit_dir.glob("audit-*.log"):
        # filename: audit-YYYY-MM-DD.log
        try:
            date_str = f.stem.split("-", maxsplit=1)[1]  # "YYYY-MM-DD"
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                f.unlink()
                deleted += 1
        except Exception:
            continue
    return {"status": "ok", "deleted": deleted, "retention_days": retention_days}


# ─── CLI entry point ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Lex-Indic scheduled jobs runner (Day 24)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "job",
        nargs="?",
        choices=["digest_email", "nalsa_csv", "cleanup", "all"],
        default="all",
        help=(
            "digest_email  — Run SC monitor digest + send emails\n"
            "nalsa_csv     — Export NALSA registry to CSV\n"
            "cleanup       — Delete old audit logs\n"
            "all           — Run all three (default)"
        ),
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print emails instead of sending them")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{ts}] Lex-Indic cron — job={args.job} dry_run={args.dry_run}")

    jobs_to_run = (
        ["digest_email", "nalsa_csv", "cleanup"] if args.job == "all" else [args.job]
    )

    exit_code = 0
    for job in jobs_to_run:
        try:
            if job == "digest_email":
                result = digest_email(dry_run=args.dry_run)
            elif job == "nalsa_csv":
                result = nalsa_csv_export()
            elif job == "cleanup":
                result = cleanup_audit()
            else:
                result = {"status": "unknown_job"}

            status = result.get("status", "?")
            ok_sym = "✓" if status in ("ok", "no_recipients", "partial") else "✗"
            print(f"  {ok_sym} {job}: {result}")
            if status == "partial" and result.get("errors"):
                for err in result["errors"][:5]:
                    print(f"    ⚠ {err}")
        except Exception as exc:
            print(f"  ✗ {job}: EXCEPTION — {exc}", file=sys.stderr)
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
