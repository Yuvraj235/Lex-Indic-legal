#!/usr/bin/env python3
"""
Ingest Supreme Court criminal judgments into a local store for "similar real
cases" retrieval.

Source: Indian Supreme Court Judgments open dataset (AWS Open Data,
CC-BY-4.0 — "Vanga (2025). Indian Supreme Court Judgments"):
  metadata  s3://indian-supreme-court-judgments/metadata/parquet/year=YYYY/metadata.parquet
  PDFs      https://indian-supreme-court-judgments.s3.amazonaws.com/data/pdf/year=YYYY/english/<path>_EN.pdf

Candidates are judgments with the State / Union / an investigating agency as a
party; a candidate is kept only if its text cites IPC/BNS/CrPC/BNSS or a
criminal special law. Each PDF is deleted right after its text is extracted.

Output: data/judgments/judgments.db (SQLite, gitignored)
  judgments(insc PK, title, decided, scr, sections, excerpt, text_gz)

USAGE
  python3 tools/ingest_judgments.py --parquet-dir <dir> --years 2014-2025 --plan
  python3 tools/ingest_judgments.py --parquet-dir <dir> --years 2014-2025 --apply [--limit N]
"""

from __future__ import annotations

import argparse
import glob
import gzip
import re
import sqlite3
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DB = ROOT / "data" / "judgments" / "judgments.db"
PDF_URL = "https://indian-supreme-court-judgments.s3.amazonaws.com/data/pdf/year={year}/english/{path}_EN.pdf"

STATE_PARTY = re.compile(r"\b(?:STATE\b|UNION OF INDIA|C\.?\s?B\.?\s?I\b|CENTRAL BUREAU|DIRECTORATE OF ENFORCEMENT|"
                         r"NARCOTICS CONTROL|NATIONAL INVESTIGATION AGENCY|N\.?I\.?A\b|ENFORCEMENT DIRECTORATE)", re.I)
CRPC = re.compile(r"\b(?:Cr\.?\s?P\.?\s?C\.?|Code of Criminal Procedure)\b[^.\n]{0,40}?(\d{1,3}[A-Z]?)|"
                  r"Section\s+(\d{1,3}[A-Z]?)\s+(?:of\s+the\s+)?(?:Cr\.?\s?P\.?\s?C|Code of Criminal Procedure)", re.I)
SPECIAL = re.compile(r"\b(NDPS|POCSO|Prevention of Corruption|Arms Act|Dowry Prohibition|"
                     r"Negotiable Instruments|Information Technology Act|Atrocities|UAPA|"
                     r"Unlawful Activities)\b", re.I)


def schema(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS judgments (
        insc TEXT PRIMARY KEY, title TEXT, decided TEXT, scr TEXT,
        sections TEXT, excerpt TEXT, text_gz BLOB)""")
    con.execute("CREATE TABLE IF NOT EXISTS skipped (insc TEXT PRIMARY KEY, reason TEXT)")


def candidates(parquet_dir: str, first: int, last: int) -> list[dict]:
    import pyarrow.parquet as pq
    out = []
    for f in sorted(glob.glob(str(Path(parquet_dir) / "*.parquet"))):
        for r in pq.read_table(f, columns=["title", "citation", "case_id", "decision_date", "year",
                                           "path", "available_languages"]).to_pylist():
            year = int(r["year"] or 0)
            if not (first <= year <= last) or not re.match(r"\d{4} INSC \d+$", r["case_id"] or ""):
                continue
            if r["path"] and STATE_PARTY.search(r["title"] or ""):
                out.append(r)
    return out


def sections_cited(text: str) -> list[str]:
    from verifier import _ipc_cited, cited_sections
    out = [f"IPC {s}" for s in sorted(_ipc_cited(text))]
    out += [f"BNS {s}" for s in sorted(cited_sections(text, "BNS"))]
    out += [f"BNSS {s}" for s in sorted(cited_sections(text, "BNSS"))]
    out += sorted({f"CrPC {a or b}" for a, b in CRPC.findall(text)})
    out += sorted({m.group(1).upper() if m.group(1).isupper() else m.group(1) for m in SPECIAL.finditer(text)})
    return out[:40]


def excerpt(text: str, n: int = 1400) -> str:
    """The opening of the judgment proper (after the 'JUDGMENT' heading)."""
    m = re.search(r"J\s*U\s*D\s*G\s*M\s*E\s*N\s*T\b|\bORDER\b", text)
    body = text[m.end():] if m else text
    body = re.sub(r"\s+", " ", body).strip()
    return body[:n].rsplit(" ", 1)[0]


def fetch_text(row: dict, tmp: str) -> str:
    import pdfplumber
    url = PDF_URL.format(year=row["year"], path=row["path"])
    pdf = Path(tmp) / f"{row['path']}.pdf"
    req = urllib.request.Request(url, headers={"User-Agent": "lex-indic-ingest"})
    with urllib.request.urlopen(req, timeout=90) as r:
        pdf.write_bytes(r.read())
    try:
        with pdfplumber.open(pdf) as p:
            return "\n".join((pg.extract_text() or "") for pg in p.pages)
    finally:
        pdf.unlink(missing_ok=True)


def work(row: dict, tmp: str) -> tuple[dict, str, str | None]:
    try:
        return row, fetch_text(row, tmp), None
    except Exception as e:  # noqa: BLE001 — one bad PDF must not stop the run
        return row, "", f"{type(e).__name__}: {str(e)[:80]}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--parquet-dir", required=True)
    ap.add_argument("--years", default="2014-2025")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    first, last = (int(x) for x in args.years.split("-"))

    rows = candidates(args.parquet_dir, first, last)
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    schema(con)
    done = {r[0] for r in con.execute("SELECT insc FROM judgments UNION SELECT insc FROM skipped")}
    todo = [r for r in rows if r["case_id"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(rows)} candidate judgments {first}–{last} (State/agency party); "
          f"{len(done)} already processed; {len(todo)} to fetch (~{len(todo) * 0.2:.0f} MB transfer, "
          f"PDFs deleted after extraction)")
    if args.plan or not args.apply:
        return

    tmp = tempfile.mkdtemp(prefix="lexindic_sc_")
    t0, kept = time.monotonic(), 0

    # Processes, not threads: PDF text extraction is CPU-bound, and threads
    # ran it on one core (~1 judgment / 5 s).
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (row, text, err) in enumerate(pool.map(work, todo, [tmp] * len(todo), chunksize=4), 1):
            cid = row["case_id"]
            if err:
                print(f"  ! {cid}: {err}")
                continue
            secs = sections_cited(text)
            if not secs:
                con.execute("INSERT OR REPLACE INTO skipped VALUES (?, ?)", (cid, "no criminal provisions cited"))
            else:
                kept += 1
                con.execute("INSERT OR REPLACE INTO judgments VALUES (?,?,?,?,?,?,?)",
                            (cid, row["title"], row["decision_date"], row["citation"], ", ".join(secs),
                             excerpt(text), gzip.compress(text.encode("utf-8"))))
            if i % 25 == 0:
                con.commit()
                print(f"  {i}/{len(todo)} processed, {kept} criminal kept, {time.monotonic() - t0:.0f}s")
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM judgments").fetchone()[0]
    print(f"✓ {kept} criminal judgments added this run; {total} in {DB}")


if __name__ == "__main__":
    main()
