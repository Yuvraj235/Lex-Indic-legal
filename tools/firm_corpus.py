#!/usr/bin/env python3
"""
Build a firm's per-deployment training pairs (redacted of party names) from its
matters + uploaded precedents.

  python3 tools/firm_corpus.py --firm FIRM_ID --out data/finetune/firm_pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import firm_corpus


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a firm's redacted training pairs.")
    ap.add_argument("--firm", required=True, help="firm_id")
    ap.add_argument("--out", default="data/finetune/firm_pairs.jsonl")
    args = ap.parse_args()

    pairs = firm_corpus.build_firm_pairs(args.firm)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"✓ wrote {len(pairs)} redacted pairs → {out}")
    print(f"  next: python3 tools/generate_instruction_data.py --firm-data {out}")


if __name__ == "__main__":
    main()
