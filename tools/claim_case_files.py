#!/usr/bin/env python3
"""
Assign case files generated before ownership tracking existed to a user, so
they show up in that user's /history again. Files that already have an owner
are never touched.

  python3 tools/claim_case_files.py --email advocate@firm.in            # dry run
  python3 tools/claim_case_files.py --email advocate@firm.in --apply
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)   # outputs/ paths are relative to the repo root

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import auth
import case_access

_TS = re.compile(r"_(\d{8}_\d{6})\.")


def _pair_pdf(txt_name: str, pdfs: dict[str, str]) -> str | None:
    """The PDF for a txt file: same stem for current names, else the PDF
    written within two minutes after it (names from before the stems matched)."""
    same_stem = "CaseBrief_" + txt_name[len("case_analysis_"):-len(".txt")] + ".pdf"
    if (Path("outputs") / same_stem).exists():
        return same_stem
    m = _TS.search(txt_name)
    if not m:
        return None
    t0 = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    for pdf_ts in sorted(pdfs):
        gap = (datetime.strptime(pdf_ts, "%Y%m%d_%H%M%S") - t0).total_seconds()
        if 0 <= gap <= 120:
            return pdfs[pdf_ts]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--email", required=True, help="user who should own the files")
    ap.add_argument("--apply", action="store_true", help="write the ownership records")
    args = ap.parse_args()

    user = auth.get_user_by_email(args.email.strip().lower())
    if not user:
        print(f"No user with email {args.email}. Sign in once at /login first.")
        return 1

    out = Path("outputs")
    txts = sorted(p.name for p in out.glob("case_analysis_*.txt"))
    pdfs = {}
    for p in out.glob("CaseBrief_*.pdf"):
        m = _TS.search(p.name)
        if m:
            pdfs[m.group(1)] = p.name

    todo = case_access.unclaimed(txts)
    print(f"{len(todo)} unclaimed case file(s) → {user['email']} "
          f"(firm: {user.get('firm_id') or 'none'})")
    for txt in todo:
        pdf = _pair_pdf(txt, pdfs)
        print(f"  {txt}  ↔  {pdf or '(no PDF)'}")
        if args.apply:
            case_access.record(txt, pdf, user_id=user["id"],
                               firm_id=user.get("firm_id") or None)
    if not args.apply and todo:
        print("\nDry run. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
