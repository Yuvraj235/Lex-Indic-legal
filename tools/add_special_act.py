#!/usr/bin/env python3
"""
Add a special criminal law (NDPS, IT Act, NI Act, SC/ST Act, JJ Act …) to the
retrieval index from an official PDF.

India Code (indiacode.nic.in) blocks automated downloads, so download the Act's
PDF in a browser, then:

  python3 tools/add_special_act.py --pdf ~/Downloads/it_act.pdf --code ITA
  python3 tools/add_special_act.py --pdf ~/Downloads/ndps.pdf --code NDPS

The Act is split into sections from its inline headings ("66D. Punishment for
cheating by personation by using computer resource.—"), checked for the
sections that matter (an outdated copy without them is refused), and saved to
data/legal_corpus/statutes/special/<code>.json, which statutes.py indexes.
Restart the app to re-index.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "legal_corpus" / "statutes" / "special"

# code → (name, last section to look for, sections that must be present)
ACTS = {
    "NDPS": ("Narcotic Drugs and Psychotropic Substances Act, 1985", 83, ["20", "21", "22", "37", "42", "50"]),
    "ITA": ("Information Technology Act, 2000", 90, ["43", "66", "66C", "66D", "66E", "67", "67A"]),
    "NIA": ("Negotiable Instruments Act, 1881", 147, ["138", "139", "141", "142"]),
    "SCST": ("Scheduled Castes and the Scheduled Tribes (Prevention of Atrocities) Act, 1989", 23, ["3", "14", "18"]),
    "JJA": ("Juvenile Justice (Care and Protection of Children) Act, 2015", 112, ["2", "4", "10", "12", "15", "18"]),
    "POCSO": ("Protection of Children from Sexual Offences Act, 2012", 46, ["3", "4", "6", "7", "8", "19", "21"]),
    "DPA": ("Dowry Prohibition Act, 1961", 10, ["2", "3", "4"]),
    "PWDVA": ("Protection of Women from Domestic Violence Act, 2005", 37, ["3", "12", "18", "19", "20"]),
}


def split_sections(text: str, last: int) -> dict[str, dict[str, str]]:
    """Sections from inline headings, tolerating amendment markers ('1[6.')
    and lettered sections ('66C.')."""
    text = re.sub(r"[ \t]+", " ", text)
    heads = list(re.finditer(
        r"(?:^|\n)\s*(?:\d+\[)?(\d{1,3}[A-Z]{0,2})\.\s*(?:\(1\)\s*)?([A-Z][^.\n—–]{2,160}?)\.?\s*(?:—|–|\.-|:-)", text))
    out: dict[str, dict[str, str]] = {}
    for i, m in enumerate(heads):
        num = m.group(1)
        if int(re.match(r"\d+", num).group()) > last or num in out:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = re.split(r"\n\s*(?:THE (?:FIRST )?SCHEDULE|_{5,})", text[m.start():end])[0].strip()
        out[num] = {"title": re.sub(r"\s+", " ", m.group(2)).strip(), "text": body}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--code", required=True, choices=sorted(ACTS))
    ap.add_argument("--source", default="", help="Where the PDF came from (URL), recorded with the text.")
    args = ap.parse_args()
    import pdfplumber

    name, last, required = ACTS[args.code]
    with pdfplumber.open(args.pdf) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    sections = split_sections(text, last)
    missing = [s for s in required if s not in sections]
    if missing:
        sys.exit(f"Refused: sections {', '.join(missing)} not found — the PDF may be an old or "
                 f"unamended copy, or a scan without text. Use the current text from India Code.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {"_source": f"{name} — {args.source or Path(args.pdf).name}", "code": args.code,
           "act": name, "sections": sections}
    path = OUT_DIR / f"{args.code.lower()}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"✓ {len(sections)} sections of the {name} → {path}. Restart the app to re-index.")


if __name__ == "__main__":
    main()
