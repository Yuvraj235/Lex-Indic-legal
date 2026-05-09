#!/usr/bin/env python3
"""
Lex-Indic — Audit Report CLI

Reads the JSONL audit log written by audit.py and prints a daily summary.
Designed for the kind of data a compliance officer or sales call wants:
total volume, error rate, latency distribution, top BNS sections retrieved,
top error messages.

USAGE:
    python3 tools/audit_report.py                # today (UTC)
    python3 tools/audit_report.py 2026-05-09     # specific UTC date
    python3 tools/audit_report.py --week         # last 7 days, aggregated
    python3 tools/audit_report.py --tail 20      # last 20 records, raw
"""

import sys
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make audit module importable when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit  # noqa: E402


# ────────────────────────────────────────────────────────────────────────────
def _percentile(sorted_values: list, pct: float) -> int:
    if not sorted_values:
        return 0
    k = max(0, min(len(sorted_values) - 1, int(round((pct / 100.0) * (len(sorted_values) - 1)))))
    return sorted_values[k]


def _summarize(records: list, label: str):
    if not records:
        print(f"\n  ── {label} ────────────────────────────────")
        print("  (no records)")
        return

    total = len(records)
    by_status = Counter(r.get("status") for r in records)
    by_endpoint = Counter(r.get("endpoint") for r in records)
    durations = sorted(int(r.get("duration_ms", 0)) for r in records if r.get("status") == "ok")
    errors = [r for r in records if r.get("status") == "error"]

    section_hits = Counter()
    for r in records:
        for sid in r.get("sources", []) or []:
            section_hits[sid] += 1

    error_msgs = Counter((r.get("error") or "")[:80] for r in errors)
    unique_users = len({r.get("client_ip") for r in records if r.get("client_ip")})
    unique_stories = len({r.get("story_hash") for r in records if r.get("story_hash")})

    print(f"\n  ── {label} ────────────────────────────────")
    print(f"  Total requests        : {total}")
    print(f"    /analyze            : {by_endpoint.get('/analyze', 0)}")
    print(f"    /chat               : {by_endpoint.get('/chat', 0)}")
    print(f"  Status                : ok={by_status.get('ok',0)}  error={by_status.get('error',0)}")
    if total:
        err_pct = 100.0 * by_status.get('error', 0) / total
        print(f"  Error rate            : {err_pct:.1f}%")
    print(f"  Unique client IPs     : {unique_users}")
    print(f"  Unique story hashes   : {unique_stories}  (proxy for distinct cases)")

    if durations:
        print(f"  Latency (ok requests) :")
        print(f"    p50 {_percentile(durations,50):>6} ms")
        print(f"    p95 {_percentile(durations,95):>6} ms")
        print(f"    max {durations[-1]:>6} ms")

    if section_hits:
        print(f"  Top retrieved sources :")
        for sid, n in section_hits.most_common(8):
            print(f"    {n:>4}× {sid}")

    if error_msgs:
        print(f"  Top errors            :")
        for msg, n in error_msgs.most_common(5):
            print(f"    {n:>4}× {msg or '(no message)'}")


def _read_date(date: str) -> list:
    """Load all records for a YYYY-MM-DD UTC date."""
    return list(audit.iter_records(date=date))


def _read_range(start_date: datetime, days: int) -> list:
    out = []
    for i in range(days):
        d = (start_date - timedelta(days=i)).strftime("%Y-%m-%d")
        out.extend(_read_date(d))
    return out


def _print_tail(n: int):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    records = _read_date(today)
    for r in records[-n:]:
        print(json.dumps(r, ensure_ascii=False))


# ────────────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if args and args[0] == "--tail":
        n = int(args[1]) if len(args) > 1 else 20
        _print_tail(n)
        return

    if args and args[0] == "--week":
        records = _read_range(datetime.now(timezone.utc), days=7)
        _summarize(records, label="Last 7 days (UTC, aggregated)")
        return

    if args:
        date = args[0]
    else:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    records = _read_date(date)
    _summarize(records, label=f"Audit summary — {date} (UTC)")


if __name__ == "__main__":
    main()
