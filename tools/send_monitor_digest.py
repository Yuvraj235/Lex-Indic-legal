#!/usr/bin/env python3
"""
Send today's SC precedent digest by email.  Schedule via cron, e.g.

  0 7 * * *  cd /opt/lex-indic && python3 tools/send_monitor_digest.py \\
             --to partner@firm.example,senior@firm.example

The `--to` list overrides MONITOR_DIGEST_TO from .env.  Multiple recipients
get one email each (BCC would be cleaner but most operators want to see
who else was on the distribution).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import monitors
import mailer


def main():
    p = argparse.ArgumentParser(description="Send today's SC precedent digest.")
    p.add_argument("--to", help="Comma-separated recipient emails. Falls back to MONITOR_DIGEST_TO env.")
    p.add_argument("--save", action="store_true",
                   help="Also save the digest JSON to outputs/monitors/digests/")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be sent; don't actually send.")
    args = p.parse_args()

    to_raw = args.to or os.getenv("MONITOR_DIGEST_TO", "")
    to_list = [t.strip() for t in to_raw.split(",") if t.strip()]
    if not to_list:
        print("ERROR: no recipients. Pass --to or set MONITOR_DIGEST_TO.")
        sys.exit(1)

    d = monitors.run_digest()
    if args.save:
        monitors.save_digest(d)

    txt = monitors.format_digest_text(d)

    if args.dry_run:
        print(f"(dry-run) Would send to: {', '.join(to_list)}")
        print(f"(dry-run) Subject: Lex-Indic SC precedent digest — {d['date']}")
        print("(dry-run) Body preview (first 30 lines):")
        for ln in txt.splitlines()[:30]:
            print("  " + ln)
        return

    sent = 0
    for addr in to_list:
        r = mailer.send_monitor_digest(addr, txt, date=d["date"])
        if r.ok:
            sent += 1
            print(f"  ✓ {addr}  ({r.provider})")
        else:
            print(f"  ✗ {addr}  ({r.provider}: {r.error})")
    print(f"Sent {sent}/{len(to_list)} digests.")


if __name__ == "__main__":
    main()
