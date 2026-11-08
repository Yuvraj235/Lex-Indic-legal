#!/usr/bin/env python3
"""
Build the Supreme Court citation index used by verifier.sc_record_check.

Source: the Indian Supreme Court Judgments open dataset (AWS Open Data,
CC-BY-4.0 — "Vanga (2025). Indian Supreme Court Judgments"), per-year
metadata parquet files: s3://indian-supreme-court-judgments/metadata/parquet/
year=YYYY/metadata.parquet (public; fetch with plain HTTPS, ~46 MB for all years).

Output: data/legal_corpus/sc_citations.json.gz
  {"insc": {"2014 INSC 463": ["ARNESH KUMAR versus STATE OF BIHAR & ANR.", "02-07-2014", "[2014] 8 S.C.R. 128"]},
   "scr":  {"[2014] 8 S.C.R. 128": "2014 INSC 463"}, "years": [1950, 2025]}

USAGE
  python3 tools/build_sc_citation_index.py --parquet-dir <dir with meta<YEAR>.parquet>
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "legal_corpus" / "sc_citations.json.gz"


def norm_scr(c: str) -> str:
    return re.sub(r"\s+", " ", (c or "").upper().replace("SUPP.", "SUPP").strip())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--parquet-dir", required=True)
    args = ap.parse_args()
    import pyarrow.parquet as pq

    insc, scr, years = {}, {}, set()
    for f in sorted(glob.glob(str(Path(args.parquet_dir) / "*.parquet"))):
        for r in pq.read_table(f, columns=["title", "citation", "case_id", "decision_date", "year"]).to_pylist():
            cid = (r["case_id"] or "").strip()
            if not re.match(r"\d{4} INSC \d+$", cid):
                continue
            insc[cid] = [(r["title"] or "").strip(), r["decision_date"] or "", (r["citation"] or "").strip()]
            if r["citation"]:
                scr[norm_scr(r["citation"])] = cid
            if r["year"]:
                years.add(int(r["year"]))
    OUT.write_bytes(gzip.compress(json.dumps(
        {"_source": "Indian Supreme Court Judgments open dataset (AWS Open Data, CC-BY-4.0), metadata parquet",
         "years": [min(years), max(years)], "insc": insc, "scr": scr},
        ensure_ascii=False, separators=(",", ":")).encode("utf-8")))
    print(f"{len(insc)} neutral citations, {len(scr)} SCR citations, years {min(years)}–{max(years)} → {OUT} "
          f"({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
