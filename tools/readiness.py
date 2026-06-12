#!/usr/bin/env python3
"""
Print the Lex-Indic go-live readiness checklist — which subsystems are still in
demo (stub) mode vs live, and what's left to flip before launch.

  python3 tools/readiness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import readiness


def main() -> None:
    r = readiness.gather_readiness()
    print("\nLex-Indic — go-live readiness\n" + "=" * 50)
    for it in r["items"]:
        mark = "✓ READY" if it["ready"] else ("● LIVE " if it["live"] else "○ demo ")
        print(f"  {mark}  {it['subsystem']:22s} [{it['mode']}]")
        if not it["ready"]:
            print(f"            ↳ {it['detail']}")
    s = r["summary"]
    print("=" * 50)
    print(f"  {s['ready']}/{s['total']} production-ready · {s['stubbed']} still in demo mode")
    print("  ✅ GO" if s["go_live"] else "  ⏳ NOT YET — flip the demo items above")
    print()


if __name__ == "__main__":
    main()
