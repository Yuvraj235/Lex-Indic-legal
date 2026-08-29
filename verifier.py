"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Runtime citation verifier                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Post-generation check that runs on every /analyze response BEFORE it reaches
the user.  Three checks, all deterministic and offline:

  1. GROUNDING   — every BNS/BNSS/BSA section the answer cites must exist in
                   our verified knowledge bases (or the govt-concordance
                   mapping tables).  A citation outside those sets is
                   UNGROUNDED — i.e. hallucinated relative to what the model
                   was actually given.
  2. JURISDICTION — flags foreign (US/UK) case-reporter citations, which have
                   no place in an Indian criminal-law analysis unless the
                   lawyer asked for comparative law.
  3. STALE IPC   — flags IPC sections cited with no BNS equivalent anywhere in
                   the analysis (IPC applies only to incidents before
                   01 Jul 2024; an IPC-only analysis needs a human check).

Pure module: no network, no Flask.  tools/eval_pipeline.py reuses these
functions so the offline eval and the live serving path can never drift.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import data.bns_knowledge_base as _bns_kb
import data.bnss_bsa_knowledge_base as _bnss_bsa_kb

_ROOT = Path(__file__).resolve().parent
_CORPUS = _ROOT / "data" / "legal_corpus"

_SEC_NUM_RE = re.compile(r"(\d{1,4}[A-Z]?(?:\(\d+\))?)")

# Statute citation extractors.  BNS uses (?!S) so "BNSS 173" is never read as
# a BNS citation.  Subsection suffixes like "103(2)" are captured but
# membership is checked on the base number.
_CITE_RES = {
    "BNS":  re.compile(r"\bBNS(?!S)\s*(?:Section\s*)?(\d{1,4}[A-Z]?(?:\(\d+\))?)", re.I),
    "BNSS": re.compile(r"\bBNSS\s*(?:Section\s*)?(\d{1,4}[A-Z]?(?:\(\d+\))?)", re.I),
    "BSA":  re.compile(r"\bBSA\s*(?:Section\s*)?(\d{1,4}[A-Z]?(?:\(\d+\))?)", re.I),
}

_IPC_CITE_RES = (
    re.compile(r"\bIPC\s*(?:Section\s*)?(\d{1,4}[A-Z]?)", re.I),
    re.compile(r"\bSection[s]?\s*(\d{1,4}[A-Z]?)\s*(?:of\s+the\s+)?(?:IPC|Indian\s+Penal\s+Code)", re.I),
)

# Foreign case-reporter patterns.  Deliberately conservative: Indian reporters
# (SCC, AIR, SCR, Cri LJ) must never trip these.
_FOREIGN_PATTERNS = [
    ("US reporter",  re.compile(r"\b\d+\s+U\.\s?S\.\s+\d+")),
    ("US reporter",  re.compile(r"\bF\.\s?(?:2d|3d|4th)\b")),
    ("US reporter",  re.compile(r"\bS\.\s?Ct\.\b")),
    ("US reporter",  re.compile(r"\bF\.\s?Supp\b")),
    ("US statute",   re.compile(r"\bU\.\s?S\.\s?C\.\b")),
    ("UK reporter",  re.compile(r"\b(?:EWCA|EWHC|UKSC|UKHL)\b")),
    ("UK reporter",  re.compile(r"\b(?:All\s+ER|WLR)\b")),
]

SECTION_KEYS = [f"section_{i}" for i in range(1, 7)]

_KNOWN: dict[str, set[str]] | None = None


def _norm(s: str) -> str:
    return s.upper().replace(" ", "")


def _base_num(s: str) -> str:
    """'103(2)' → '103' — membership is checked on the base section number."""
    return re.sub(r"\(.*\)$", "", _norm(s))


def _nums_from_kb(entries: list[dict]) -> set[str]:
    # Base numbers only: the KB may list "BSA Section 23(1)" but a citation of
    # plain "BSA 23" is the same section and must verify.
    out: set[str] = set()
    for e in entries:
        m = _SEC_NUM_RE.search(e.get("section", ""))
        if m:
            out.add(_base_num(m.group(1)))
    return out


def _nums_from_mapping(path: Path, target_key: str) -> set[str]:
    """Collect target section numbers ('bns'/'bnss'/'bsa' values) from a
    mapping JSON.  Repealed/no-equivalent entries contribute nothing."""
    out: set[str] = set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    for key, value in raw.items():
        if key.startswith("_") or not isinstance(value, dict):
            continue
        m = _SEC_NUM_RE.search(value.get(target_key, "") or "")
        if m:
            out.add(_base_num(m.group(1)))
    return out


def known_sections() -> dict[str, set[str]]:
    """statute → set of verified section numbers.  Sources: the curated
    knowledge bases + the govt-concordance mapping tables.  Cached."""
    global _KNOWN
    if _KNOWN is None:
        _KNOWN = {
            "BNS":  _nums_from_kb(_bns_kb.BNS_SECTIONS)
                    | _nums_from_mapping(_CORPUS / "ipc_bns_mapping.json", "bns"),
            "BNSS": _nums_from_kb(_bnss_bsa_kb.BNSS_SECTIONS)
                    | _nums_from_mapping(_CORPUS / "crpc_bnss_mapping.json", "bnss"),
            "BSA":  _nums_from_kb(_bnss_bsa_kb.BSA_SECTIONS)
                    | _nums_from_mapping(_CORPUS / "iea_bsa_mapping.json", "bsa"),
        }
    return _KNOWN


def known_bns_sections() -> set[str]:
    """Back-compat helper used by tools/eval_pipeline.py and tests."""
    return set(known_sections()["BNS"])


def _is_year_not_section(num: str) -> bool:
    """'BNS 2023' cites the Act's year, not a section — no Indian statute here
    has 1000+ sections, and 1860–2100 is unmistakably a year."""
    digits = re.sub(r"\D", "", num)
    return digits.isdigit() and 1860 <= int(digits) <= 2100 and len(digits) == 4


def cited_sections(text: str, statute: str = "BNS") -> set[str]:
    """All section numbers cited for one statute in `text` (normalised).
    Year references like 'BNS 2023' are excluded."""
    pat = _CITE_RES[statute]
    return {_norm(n) for n in pat.findall(text or "")
            if not _is_year_not_section(n)}


def foreign_citations(text: str) -> list[dict]:
    """Foreign-law reporter hits: [{'kind': 'US reporter', 'match': '410 U.S. 113'}]."""
    hits: list[dict] = []
    seen: set[str] = set()
    for kind, pat in _FOREIGN_PATTERNS:
        for m in pat.finditer(text or ""):
            key = m.group(0).strip()
            if key not in seen:
                seen.add(key)
                hits.append({"kind": kind, "match": key})
    return hits


def _ipc_cited(text: str) -> set[str]:
    out: set[str] = set()
    for pat in _IPC_CITE_RES:
        out.update(_norm(n) for n in pat.findall(text or ""))
    return out


def verify_analysis(sections: dict) -> dict:
    """Verify one /analyze output (dict with section_1..section_6).

    Returns a JSON-safe verdict block:
      citations        — every statute citation with its verdict + where found
      ungrounded       — labels like 'BNS 999' not backed by any KB/mapping
      foreign_citations— US/UK reporter hits (jurisdiction guard)
      ipc_without_bns  — True when IPC is cited but no BNS section is (stale-law
                         warning: valid only for pre-Jul-2024 incidents)
      all_verified     — True ⇔ no ungrounded citations and no foreign hits
    """
    known = known_sections()
    citations: list[dict] = []
    ungrounded: list[str] = []
    seen: set[tuple[str, str]] = set()

    combined_parts: list[str] = []
    for key in SECTION_KEYS:
        text = sections.get(key) or ""
        combined_parts.append(text)
        for statute in ("BNS", "BNSS", "BSA"):
            for num in sorted(cited_sections(text, statute)):
                if (statute, num) in seen:
                    continue
                seen.add((statute, num))
                ok = _base_num(num) in known[statute]
                label = f"{statute} {num}"
                citations.append({
                    "statute": statute,
                    "section": num,
                    "status": "verified" if ok else "ungrounded",
                    "found_in": key,
                })
                if not ok:
                    ungrounded.append(label)

    combined = "\n".join(combined_parts)
    foreign = foreign_citations(combined)
    bns_cited_anywhere = any(c["statute"] == "BNS" for c in citations)
    ipc_without_bns = bool(_ipc_cited(combined)) and not bns_cited_anywhere

    verified_count = sum(1 for c in citations if c["status"] == "verified")
    return {
        "citations": citations,
        "verified_count": verified_count,
        "ungrounded_count": len(ungrounded),
        "ungrounded": ungrounded,
        "foreign_citations": foreign,
        "ipc_without_bns": ipc_without_bns,
        "all_verified": not ungrounded and not foreign,
    }


def verification_stamp(v: dict) -> str:
    """One-line human-readable verdict for the PDF / saved text output."""
    if v["all_verified"] and not v["ipc_without_bns"]:
        return (f"CITATION CHECK: PASSED — {v['verified_count']}/"
                f"{v['verified_count']} statute citations verified against the "
                "Lex-Indic knowledge base.")
    problems = []
    if v["ungrounded"]:
        problems.append("UNVERIFIED citations: " + ", ".join(v["ungrounded"]))
    if v["foreign_citations"]:
        problems.append("foreign-law references: "
                        + ", ".join(h["match"] for h in v["foreign_citations"]))
    if v["ipc_without_bns"]:
        problems.append("IPC cited with no BNS equivalent — confirm the "
                        "incident predates 01 Jul 2024")
    return ("CITATION CHECK: ATTENTION REQUIRED — " + "; ".join(problems)
            + ". Do not file without advocate review.")
