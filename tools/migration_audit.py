#!/usr/bin/env python3
"""
Statute migration audit over a folder of legal documents — reports every outdated
IPC/CrPC/Evidence-Act reference and its BNS/BNSS/BSA equivalent.

  python3 tools/migration_audit.py path/to/firm_templates/
  python3 tools/migration_audit.py file1.docx file2.pdf --out audit.md
  python3 tools/migration_audit.py path/ --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import migration_audit as ma


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan documents for outdated statute references.")
    ap.add_argument("paths", nargs="+", help="Files or folders (.txt/.docx/.pdf)")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    ap.add_argument("--out", default=None, help="Also write the markdown report here")
    args = ap.parse_args()

    report = ma.audit_paths(args.paths)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(ma.render_markdown(report))
    if args.out:
        Path(args.out).write_text(ma.render_markdown(report), encoding="utf-8")
        print(f"\n✓ wrote {args.out}")


if __name__ == "__main__":
    main()
