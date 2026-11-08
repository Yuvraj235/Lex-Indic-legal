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
# membership is checked on the base number.  Two shapes per statute:
#   "BNS 103", "BNS §103", "BNS Section 103", "Bharatiya Nyaya Sanhita, 2023, s. 318(4)"
#                                                          (statute first)
#   "Section 103 of the Bharatiya Nyaya Sanhita", "Sections 85 and 86 BNS"
#                                                          (number first)
_NUM = r"\d{1,4}[A-Z]?(?:\(\d+\))?"
# "103, 105 and 109(1)": a comma-continued number counts only when another
# list item or the end of the list follows — so "BNS 318(4), 20 witnesses"
# doesn't turn 20 into a section.
_LIST = (rf"{_NUM}(?:\s*,\s*{_NUM}(?=\s*(?:,|and\b|&|/|\)|\.|;|$)))*"
         rf"(?:\s*(?:and|&|/)\s*{_NUM})?")
_STATUTE_NAMES = {
    "BNS":  r"BNS(?!S)|Bharatiya\s+Nyaya\s+Sanhita",
    "BNSS": r"BNSS|Bharatiya\s+Nagarik\s+Suraksha\s+Sanhita",
    "BSA":  r"BSA|Bharatiya\s+Sakshya\s+Adhiniyam",
}
_CITE_RES = {
    st: re.compile(rf"\b(?:{names}),?\s*(?:\d{{4}},?\s*)?(?:Sections?|Secs?\.|S\.|§§?)?\s*({_LIST})", re.I)
    for st, names in _STATUTE_NAMES.items()
}
_CITE_LIST_RES = {
    st: re.compile(rf"(?:\b(?:Sections?|Secs?\.|S\.)|§§?)\s*((?:{_NUM})(?:\s*(?:,|and|&|/)\s*{_NUM})*)"
                   rf"\s*,?\s*(?:of\s+(?:the\s+)?)?(?:{names})\b", re.I)
    for st, names in _STATUTE_NAMES.items()
}
_IPC_CITE_RES = (
    re.compile(r"\bIPC\s*(?:Section\s*|Sec\.\s*|§§?\s*)?(\d{1,4}[A-Z]?)", re.I),
    re.compile(r"(?:\bSection[s]?|§§?)\s*(\d{1,4}[A-Z]?)\s*(?:of\s+the\s+)?(?:IPC|Indian\s+Penal\s+Code)", re.I),
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


_IPC_MAP: dict[str, set[str]] | None = None


def ipc_to_bns() -> dict[str, set[str]]:
    """IPC section → the BNS base numbers it became, from the government
    concordance table. Repealed sections (no BNS equivalent) are omitted."""
    global _IPC_MAP
    if _IPC_MAP is None:
        _IPC_MAP = {}
        try:
            raw = json.loads((_CORPUS / "ipc_bns_mapping.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        for key, value in raw.items():
            if key.startswith("_") or not isinstance(value, dict):
                continue
            # "also_bns": further sections the IPC section split into (IPC 498A's
            # Explanation became BNS 86) — valid pairings, not the converter's target.
            sources = [value.get("bns", "") or ""] + list(value.get("also_bns", []))
            targets = {_base_num(n) for src in sources for n in re.findall(_NUM, src)}
            ipc = re.sub(r"^IPC\s*", "", key, flags=re.I)
            if targets:
                _IPC_MAP[_norm(ipc)] = targets
    return _IPC_MAP


def _spans(text: str, regexes) -> list[tuple[int, str]]:
    """(position, normalised section) for every match of the given regexes."""
    out = []
    for pat in regexes:
        for m in pat.finditer(text):
            for n in re.findall(_NUM, m.group(1)):
                if not _is_year_not_section(n):
                    out.append((m.start(), _norm(n)))
    return out


# Sentence ends: ". Next" after a lowercase letter, digit or ")" — so the
# abbreviations inside citations ("S. 309", "Sec. 302", "No. 5") don't split.
_SENTENCE_END = re.compile(r"(?<=[a-z0-9)][.!?])\s+(?=[A-Z])")


def _clauses(text: str) -> list[str]:
    return [c for line in text.splitlines() for c in _SENTENCE_END.split(line)]


def mapping_mismatches(text: str, window: int = 80) -> list[dict]:
    """IPC↔BNS pairings that contradict the concordance. For each IPC citation,
    look at the BNS citations in the same sentence within `window` characters: if
    none of them is a section that IPC section actually became, the text is
    pairing it with the wrong one. "BNS 302 (old IPC 302)" is caught even
    though BNS 302 exists (IPC 302 became BNS 103); a line listing several
    correct pairs side by side is not flagged."""
    table = ipc_to_bns()
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for line in _clauses(text or ""):
        ipcs = _spans(line, _IPC_CITE_RES)
        if not ipcs:
            continue
        bns = _spans(line, (_CITE_RES["BNS"], _CITE_LIST_RES["BNS"]))
        for pos, ipc in ipcs:
            expected = table.get(_norm(ipc))
            near = sorted((abs(bpos - pos), b) for bpos, b in bns if abs(bpos - pos) <= window)
            if not expected or not near:
                continue
            if any(_base_num(b) in expected for _, b in near):
                continue
            cited = near[0][1]
            if (ipc, cited) not in seen:
                seen.add((ipc, cited))
                found.append({"ipc": ipc, "cited_bns": cited,
                              "expected_bns": sorted(expected)})
    return found


def known_sections() -> dict[str, set[str]]:
    """statute → set of verified section numbers.  Sources: the official
    Gazette text (every section of each Act, also in the retrieval index), the
    curated knowledge bases and the govt-concordance mapping tables.  Cached."""
    global _KNOWN
    if _KNOWN is None:
        official = {code: set(t) for code, t in official_titles().items()}
        _KNOWN = {
            "BNS":  official["BNS"] | _nums_from_kb(_bns_kb.BNS_SECTIONS)
                    | _nums_from_mapping(_CORPUS / "ipc_bns_mapping.json", "bns"),
            "BNSS": official["BNSS"] | _nums_from_kb(_bnss_bsa_kb.BNSS_SECTIONS)
                    | _nums_from_mapping(_CORPUS / "crpc_bnss_mapping.json", "bnss"),
            "BSA":  official["BSA"] | _nums_from_kb(_bnss_bsa_kb.BSA_SECTIONS)
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
    """All section numbers cited for one statute in `text` (normalised),
    whether written statute-first ("BNS 103") or number-first ("Section 103
    of the Bharatiya Nyaya Sanhita"). Year references like 'BNS 2023' are
    excluded."""
    text = text or ""
    nums: list[str] = []
    for pat in (_CITE_RES[statute], _CITE_LIST_RES[statute]):
        for group in pat.findall(text):
            nums.extend(re.findall(_NUM, group))
    return {_norm(n) for n in nums if not _is_year_not_section(n)}


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


# ─── Official statute text (Gazette of India, 25 Dec 2023) ───────────────────
# All 358 BNS / 531 BNSS / 170 BSA sections with their official marginal
# titles. The knowledge base covers only part of each Act, so "not in the KB"
# can't tell an invented section from a real one we don't cover; this can.
_OFFICIAL: dict[str, dict[str, str | None]] | None = None


def official_titles() -> dict[str, dict[str, str | None]]:
    global _OFFICIAL
    if _OFFICIAL is None:
        _OFFICIAL = {}
        for code in ("BNS", "BNSS", "BSA"):
            path = _CORPUS / "statutes" / f"{code.lower()}_section_titles.json"
            _OFFICIAL[code] = json.loads(path.read_text(encoding="utf-8"))["sections"]
    return _OFFICIAL


def nonexistent_sections(text: str) -> list[str]:
    """Citations of sections the Act does not have ('BNS 420', 'BNS 498A')."""
    titles = official_titles()
    return [f"{code} {c}" for code in ("BNS", "BNSS", "BSA")
            for c in sorted(cited_sections(text, code))
            if _base_num(c) not in titles[code]]


# Offence words a draft writes next to a citation → words the official title
# must contain for that label to be right. "BNS 302 (murder)" is wrong: 302 is
# about wounding religious feelings; murder is 101/103.
_LABEL_WORDS = {
    "murder": ["murder"], "culpable homicide": ["culpable homicide"],
    "negligen": ["negligen"], "grievous": ["grievous"], "theft": ["theft"],
    "robbery": ["robbery"], "dacoity": ["dacoity"], "snatching": ["snatching"],
    "extortion": ["extortion"], "cheating": ["cheat"], "personation": ["personation"],
    "breach of trust": ["breach of trust"], "misappropriation": ["misappropriation"],
    "forg": ["forg"], "trespass": ["trespass"], "mischief": ["mischief"],
    "house-breaking": ["house-breaking", "house- breaking", "house breaking"],
    "intimidation": ["intimidation"], "defamation": ["defamation"], "stalking": ["stalking"],
    "voyeurism": ["voyeurism"], "rape": ["rape"], "sexual harassment": ["sexual harassment"],
    "modesty": ["modesty"], "cruelty": ["cruelty"], "dowry": ["dowry"], "suicide": ["suicide"],
    "kidnap": ["kidnap"], "ransom": ["ransom"], "confinement": ["confinement"],
    "conspiracy": ["conspiracy"], "rioting": ["rioting"], "unlawful assembly": ["unlawful assembly"],
    "enmity": ["enmity"], "organised crime": ["organised crime"], "acid": ["acid"],
    "stolen property": ["stolen property"], "bigamy": ["marrying again"],
    "deceitful": ["deceitful"], "rash driving": ["rash driving"],
}
# Right labels whose words aren't in the title: 3(5) is common intention; 125
# is the rash-or-negligent act section, (b) where grievous hurt is caused.
_LABEL_OK = {("BNS", "3"): {"common intention"},
             ("BNS", "125"): {"negligen", "grievous", "rash driving"}}
_BNSS_LABELS = {
    "anticipatory bail": {"482"}, "first information": {"173"}, "fir": {"173"},
    "zero fir": {"173"}, "chargesheet": {"193"}, "charge sheet": {"193"},
    "inherent power": {"528"}, "quash": {"528"}, "remand": {"187"},
    "notice of appearance": {"35"},
}
# A label sits right after the number: "BNS 302 (murder)", "BNS 302 – murder",
# "BNS 302: murder", "BNS 302 for murder". Prose ("BNS 114. The injury is not
# grievous") is not a label.
_LABEL_START = re.compile(r"^\s*(?:\*\*|</?strong>)?\s*(?:[(\[:–—-]|,\s*which|\s+for\b)", re.I)


# "BNS 115 – ruled out because the injury is grievous" explains why a section
# does NOT apply; the words after it are not a label for it.
_RULED_OUT = re.compile(r"\b(?:ruled out|not|no|rather than|instead|inapplicable|"
                        r"does not|doesn't|excluded|unlike|because|since|as the)\b", re.I)


def _label_after(text: str, end: int) -> str:
    if not _LABEL_START.match(text[end:end + 12]):
        return ""
    tail = text[end:end + 80]
    stop = re.search(r"[)\].;\n]|\b(?:BNS|BNSS|BSA|IPC|CrPC)\b", tail[1:])
    label = (tail[:stop.start() + 1] if stop else tail).lower()
    return "" if _RULED_OUT.search(label) else label


def _sections_titled(word: str) -> list[str]:
    titles = official_titles()["BNS"]
    return [n for n, t in titles.items() if t and word in t.lower()][:4]


def label_mismatches(text: str) -> list[dict]:
    """Real section numbers tied to an offence their official title doesn't
    cover — the usual shape of a recalled-from-memory citation."""
    titles = official_titles()
    out: list[dict] = []
    seen: set[str] = set()
    for code in ("BNS", "BNSS"):
        for m in _CITE_RES[code].finditer(text or ""):
            nums = re.findall(r"\d{1,3}", m.group(1))
            if len(nums) != 1 or nums[0] not in titles[code]:
                continue          # lists can't be pinned to one label; fakes are reported elsewhere
            num, label = nums[0], _label_after(text, m.end())
            if not label:
                continue
            if code == "BNS":
                title = (titles["BNS"][num] or "").lower()
                said = [k for k in _LABEL_WORDS if k in label]
                ok = _LABEL_OK.get(("BNS", num), set())
                if not said or any(k in ok or any(w in title for w in _LABEL_WORDS[k]) for k in said):
                    continue
                hint = ", ".join(f"BNS {n}" for n in _sections_titled(_LABEL_WORDS[said[0]][0]))
            else:
                said = [k for k in _BNSS_LABELS if re.search(rf"\b{re.escape(k)}\b", label)]
                if not said or any(num in _BNSS_LABELS[k] for k in said):
                    continue
                hint = ", ".join(f"BNSS {n}" for n in sorted(_BNSS_LABELS[said[0]]))
            key = f"{code} {num}:{said[0]}"
            if key in seen:
                continue
            seen.add(key)
            out.append({"cited": f"{code} {num}", "label": said[0],
                        "official_title": titles[code][num], "suggest": hint})
    return out


# Provisions enacted but never brought into force. S.O. 850(E) (23 Feb 2024)
# commenced the BNS on 1 July 2024 "except the provision of sub-section (2) of
# section 106" (hit-and-run without reporting).
_NOT_IN_FORCE = {"BNS 106(2)": "the hit-and-run clause has not been brought into force — "
                               "charge under BNS 106(1)"}
_IN_FORCE_CAVEAT = re.compile(r"not\s+(?:yet\s+)?(?:been\s+)?(?:brought\s+into\s+force|in\s+force|"
                              r"notified|operational|enforced)|abeyance|on\s+hold|kept\s+out", re.I)


def not_in_force(text: str) -> list[str]:
    """Provisions relied on as live law although they aren't in force."""
    out = []
    for label in _NOT_IN_FORCE:
        code, num = label.split(" ", 1)
        if num not in {c for c in cited_sections(text, code)}:
            continue
        for sent in re.split(r"(?<=[.!?\n])\s+", text):
            if re.search(rf"\b{re.escape(num)}", sent) and code in sent.upper() \
                    and not _IN_FORCE_CAVEAT.search(sent):
                out.append(label)
                break
    return out


def verify_analysis(sections: dict) -> dict:
    """Verify one /analyze output (dict with section_1..section_6).

    Returns a JSON-safe verdict block:
      citations        — every statute citation with its verdict + where found
      ungrounded       — labels like 'BNS 999' not backed by any KB/mapping
      foreign_citations— US/UK reporter hits (jurisdiction guard)
      mapping_mismatches— "IPC 302 → BNS 302"-style pairings that contradict
                         the government IPC→BNS concordance
      precedents       — case law: cited / unverified (not in the curated
                         judgments) / bad_law (overruled, superseded) /
                         wrong_citation (right case, wrong report)
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
    mismatches = mapping_mismatches(combined)
    precedents = precedent_check(combined)
    fake = nonexistent_sections(combined)
    labels = label_mismatches(combined)
    inactive = not_in_force(combined)
    sc_record = sc_record_check(combined)
    bns_cited_anywhere = any(c["statute"] == "BNS" for c in citations)
    ipc_without_bns = bool(_ipc_cited(combined)) and not bns_cited_anywhere

    verified_count = sum(1 for c in citations if c["status"] == "verified")
    return {
        "citations": citations,
        "verified_count": verified_count,
        "ungrounded_count": len(ungrounded),
        "ungrounded": ungrounded,
        "foreign_citations": foreign,
        "mapping_mismatches": mismatches,
        "precedents": precedents,
        "nonexistent": fake,
        "label_mismatches": labels,
        "not_in_force": inactive,
        "sc_record": sc_record,
        "ipc_without_bns": ipc_without_bns,
        "all_verified": (not ungrounded and not foreign and not mismatches
                         and not precedents["unverified"] and not precedents["bad_law"]
                         and not precedents["wrong_citation"]
                         and not fake and not labels and not inactive and not sc_record),
    }


def verification_stamp(v: dict) -> str:
    """One-line human-readable verdict for the PDF / saved text output."""
    if v["all_verified"] and not v["ipc_without_bns"]:
        return (f"CITATION CHECK: PASSED — {v['verified_count']}/"
                f"{v['verified_count']} statute citations verified against the "
                "Lex-Indic knowledge base.")
    problems = []
    if v.get("nonexistent"):
        problems.append("sections that DO NOT EXIST in the Act: " + ", ".join(v["nonexistent"]))
    if v.get("label_mismatches"):
        problems.append("section number does not match the offence named: " + "; ".join(
            f"{m['cited']} is '{m['official_title']}', not {m['label']}"
            for m in v["label_mismatches"]))
    if v.get("not_in_force"):
        problems.append("relied on a provision not in force: " + ", ".join(v["not_in_force"]))
    if v.get("sc_record"):
        problems.append("Supreme Court citation not matching the official record: " + "; ".join(
            f"{r['cited']} ({r['case'] or 'case not named'}) — {r['problem']}" for r in v["sc_record"]))
    if v["ungrounded"]:
        problems.append("UNVERIFIED citations: " + ", ".join(v["ungrounded"]))
    if v["foreign_citations"]:
        problems.append("foreign-law references: "
                        + ", ".join(h["match"] for h in v["foreign_citations"]))
    prec = v.get("precedents") or {}
    if prec.get("unverified"):
        problems.append("UNVERIFIED case law: " + "; ".join(prec["unverified"]))
    if prec.get("bad_law"):
        problems.append("no longer good law: " + "; ".join(
            f"{b['case']} ({b['status'].replace('_', ' ')})" for b in prec["bad_law"]))
    if prec.get("wrong_citation"):
        problems.append("wrong report citation: " + "; ".join(
            f"{w['case']} is {w['correct']}, not {w['cited']}" for w in prec["wrong_citation"]))
    if v.get("mapping_mismatches"):
        problems.append("wrong IPC→BNS pairing: " + ", ".join(
            f"IPC {m['ipc']} is BNS {'/'.join(m['expected_bns'])}, not BNS {m['cited_bns']}"
            for m in v["mapping_mismatches"]))
    if v["ipc_without_bns"]:
        problems.append("IPC cited with no BNS equivalent — confirm the "
                        "incident predates 01 Jul 2024")
    return ("CITATION CHECK: ATTENTION REQUIRED — " + "; ".join(problems)
            + ". Do not file without advocate review.")


# ─── Self-correction ─────────────────────────────────────────────────────────
_PLACEHOLDER = re.compile(r"^\[SECTION \d - not found in report\]$")


def missing_sections(sections: dict, min_len: int = 40) -> list[str]:
    """Section keys that are absent, placeholder-only or too short to be real."""
    out = []
    for key in SECTION_KEYS:
        text = (sections.get(key) or "").strip()
        if len(text) < min_len or _PLACEHOLDER.match(text):
            out.append(key)
    return out


def repair_feedback(sections: dict, verification: dict) -> list[str]:
    """Concrete, checkable corrections for one draft — empty when it passes.
    Each line names the exact problem so a correction pass can't guess."""
    issues = []
    missing = missing_sections(sections)
    if missing:
        issues.append("These sections are missing or empty — write each under its "
                      "exact heading: " + ", ".join(k.replace("section_", "SECTION ")
                                                    for k in missing) + ".")
    for label in verification.get("nonexistent", []):
        issues.append(f"{label} does not exist in the Act — remove it; cite only sections "
                      "from the law provided.")
    for m in verification.get("label_mismatches", []):
        hint = (f" Sections whose official title covers {m['label']}: {m['suggest']}."
                if m["suggest"] else "")
        issues.append(f"{m['cited']} is '{m['official_title']}' — it is not {m['label']}.{hint} "
                      "Correct every occurrence.")
    for label in verification.get("not_in_force", []):
        issues.append(f"{label}: {_NOT_IN_FORCE[label]}, and state that it is not in force.")
    for r in verification.get("sc_record", []):
        issues.append(f"The citation {r['cited']} given for '{r['case'] or 'a case'}' is {r['problem']} — "
                      "remove the case or cite it exactly as given in the LANDMARK CASE entries.")
    for m in verification.get("mapping_mismatches", []):
        issues.append(f"IPC {m['ipc']} corresponds to BNS {' / '.join(m['expected_bns'])}, "
                      f"not BNS {m['cited_bns']} — correct every occurrence.")
    for label in verification.get("ungrounded", []):
        if label in verification.get("nonexistent", []):
            continue
        issues.append(f"{label} is not in the law provided to you — remove it or "
                      "replace it with one of the provided sections.")
    for f in verification.get("foreign_citations", []):
        issues.append(f"Remove the foreign-law reference '{f['match']}' — cite Indian law only.")
    prec = verification.get("precedents") or {}
    for case in prec.get("unverified", []):
        issues.append(f"Remove '{case}' — it is not one of the verified judgments provided; "
                      "cite case law only from the LANDMARK CASE entries.")
    for b in prec.get("bad_law", []):
        issues.append(f"{b['case']} is {b['status'].replace('_', ' ')} ({b['note']}) — do not "
                      "rely on it as current law.")
    for w in prec.get("wrong_citation", []):
        issues.append(f"{w['case']} is reported at {w['correct']}, not {w['cited']}.")
    return issues


def issue_score(sections: dict, verification: dict) -> int:
    """Weighted problem count used to pick the better of two drafts (lower wins).
    A wrong mapping or a missing section costs more than an unverifiable cite."""
    return (3 * len(missing_sections(sections))
            + 3 * len(verification.get("nonexistent", []))
            + 3 * len(verification.get("label_mismatches", []))
            + 3 * len(verification.get("not_in_force", []))
            + 3 * len(verification.get("sc_record", []))
            + 3 * len(verification.get("mapping_mismatches", []))
            + 2 * len(verification.get("ungrounded", []))
            + 2 * len(verification.get("foreign_citations", []))
            + 3 * len((verification.get("precedents") or {}).get("unverified", []))
            + 3 * len((verification.get("precedents") or {}).get("bad_law", []))
            + 2 * len((verification.get("precedents") or {}).get("wrong_citation", [])))



# ─── Case-law (precedent) verification ───────────────────────────────────────
# The Supreme Court treats unverified AI-generated precedents with zero
# tolerance (Pooja Ramesh Singh v. J&K Bank, 2026 INSC 668). A precedent is any
# "X v. Y" carrying a year or law-report citation; it must be one of the curated
# judgments, cited with the right report, and still good law.
_REPORTER = (r"\(\s*\d{4}\s*\)\s*(?:Supp\s*\(\d\)\s*)?\d+\s*SCC\s*\d+|\d{4}\s+Supp\s*\(\d\)\s*SCC\s*\d+"
             r"|AIR\s+\d{4}\s+[A-Z]{2,5}\s+\d+|\d{4}\s+INSC\s+\d+|\d{4}\s+SCC\s+OnLine\s+\w+\s+\d+"
             r"|\(\d{4}\)\s*\d+\s*SCR\s*\d+|\d{4}\s+Cri\s*LJ\s+\d+")
_PARTY = r"[A-Z][\w.&'’\-]*(?:\s+(?:of|the|and|for|[A-Z(][\w.&'’\-()]*)){0,7}"
_CASE_RE = re.compile(
    rf"(?P<case>{_PARTY}\s+(?:v\.|vs\.?|versus)\s+{_PARTY})"
    rf"\s*[,(]?\s*(?P<cite>{_REPORTER}|\(\s*\d{{4}}\s*\))", re.S)
_GENERIC_PARTY = re.compile(
    r"^(?:the\s+)?(?:state|union|govt\.?|government|emperor|cbi|ncb|ed|"
    r"state\s+of\s+[\w.() ]+|union\s+of\s+india|state\s*\(nct\s+of\s+delhi\))\b", re.I)
_JUDGMENTS: list[dict] | None = None


def _judgments() -> list[dict]:
    global _JUDGMENTS
    if _JUDGMENTS is None:
        try:
            raw = json.loads((_CORPUS / "landmark_judgments.json").read_text(encoding="utf-8"))
            _JUDGMENTS = raw.get("judgments", [])
        except (OSError, json.JSONDecodeError):
            _JUDGMENTS = []
    return _JUDGMENTS


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _party_keys(case: str) -> list[str]:
    """Distinctive party names ("arneshkumar", "bhajanlal"), skipping generic
    ones like "State of Bihar" / "Union of India" that many cases share."""
    parties = re.split(r"\s+(?:v\.|vs\.?|versus)\s+", re.sub(r"\(.*?\)", "", case), maxsplit=1)
    keys = [_squash(p) for p in parties if p.strip() and not _GENERIC_PARTY.match(p.strip())]
    return [k for k in keys if len(k) >= 5]


def _find_judgment(case_text: str) -> dict | None:
    keys = _party_keys(case_text)
    for j in _judgments():
        jkeys = _party_keys(j["case"])
        if any(k == jk or (min(len(k), len(jk)) >= 8 and (k in jk or jk in k))
               for k in keys for jk in jkeys):
            return j
    return None


_LEAD_IN = re.compile(r"^(?:(?:see|also|cf\.?|per|in|rely\s+on|following|refer|and)\s+)+", re.I)


def precedent_check(text: str) -> dict:
    """{'cited': [...], 'unverified': [...], 'bad_law': [...], 'wrong_citation': [...]}

    An unknown case is flagged when it carries a law-report citation, or a bare
    year with the State/Union as a party (the shape of a reported judgment) —
    not "Ramesh v. Suresh (2023)", which is more likely the client's own dispute."""
    out = {"cited": [], "unverified": [], "bad_law": [], "wrong_citation": []}
    seen_case: set[str] = set()
    seen_pair: set[tuple[str, str]] = set()
    for m in _CASE_RE.finditer(text or ""):
        case = _LEAD_IN.sub("", " ".join(m.group("case").split()))
        cite = " ".join(m.group("cite").split())
        if (case, cite) in seen_pair:
            continue
        seen_pair.add((case, cite))
        reported = bool(re.search(r"SCC|AIR|INSC|SCR|Cri", cite))
        j = _find_judgment(case)
        if not j:
            if _in_sc_record(case, cite):
                # Not a curated case, but a real Supreme Court judgment cited
                # with its own neutral citation — verified by the official record.
                if case not in seen_case:
                    seen_case.add(case)
                    out["cited"].append({"case": case, "citation": cite, "status": "official_record"})
                continue
            parties = re.split(r"\s+(?:v\.|vs\.?|versus)\s+", case, maxsplit=1)
            if reported or any(_GENERIC_PARTY.match(p.strip()) for p in parties):
                out["unverified"].append(f"{case} {cite}")
            continue
        known = _squash(j.get("citation", ""))
        if reported and known and _squash(cite) != known:
            out["wrong_citation"].append({"case": j["case"], "cited": cite,
                                          "correct": j.get("citation", "")})
        if j["case"] in seen_case:
            continue
        seen_case.add(j["case"])
        out["cited"].append({"case": j["case"], "citation": j.get("citation", ""),
                             "status": j.get("status", "good_law")})
        if j.get("status", "good_law") != "good_law":
            out["bad_law"].append({"case": j["case"], "status": j["status"],
                                   "note": j.get("status_note", "")})
    return out


# ─── Supreme Court record check ──────────────────────────────────────────────
# Every Supreme Court judgment 1950–2026 with its neutral citation, official
# S.C.R. report and party names (tools/build_sc_citation_index.py, from the
# CC-BY open dataset). Any cited "2024 INSC 891" or "[2014] 8 S.C.R. 128" must
# exist there and belong to the case named next to it — the check that caught
# all 15 fabricated rulings once shipped in monitors.SEED_RULINGS.
_SC_INDEX: dict | None = None
_INSC_RE = re.compile(r"\b((?:19|20)\d{2})\s*INSC\s*(\d{1,4})\b")
_SCR_RE = re.compile(r"\[\s*((?:19|20)\d{2})\s*\]\s*(SUPP\.?\s*)?(\d{1,2})\s*S\.?\s*C\.?\s*R\.?\s*(\d{1,4})", re.I)


def _sc_index() -> dict:
    global _SC_INDEX
    if _SC_INDEX is None:
        import gzip
        path = _CORPUS / "sc_citations.json.gz"
        try:
            _SC_INDEX = json.loads(gzip.decompress(path.read_bytes()))
        except (OSError, ValueError):
            _SC_INDEX = {"insc": {}, "scr": {}, "years": [0, 0]}
    return _SC_INDEX


def _case_before(text: str, start: int) -> str:
    """The 'X v. Y' named just before a citation, if any."""
    window = text[max(0, start - 160):start]
    m = None
    for m in re.finditer(rf"{_PARTY}\s+(?:v\.|vs\.?|versus)\s+{_PARTY}", window):
        pass
    return _LEAD_IN.sub("", m.group(0).strip()) if m else ""


def sc_record_check(text: str) -> list[dict]:
    """Supreme Court citations that are not in the official record, or that
    belong to a different case than the one named with them."""
    idx = _sc_index()
    if not idx["insc"]:
        return []
    first, last = idx["years"]
    out: list[dict] = []
    seen: set[str] = set()
    hits = [(m.start(), f"{m.group(1)} INSC {int(m.group(2))}", "insc", int(m.group(1)))
            for m in _INSC_RE.finditer(text or "")]
    hits += [(m.start(), f"[{m.group(1)}] {'SUPP ' if m.group(2) else ''}{m.group(3)} S.C.R. {m.group(4)}",
              "scr", int(m.group(1))) for m in _SCR_RE.finditer(text or "")]
    for start, cite, kind, year in sorted(hits):
        if cite in seen or not (first <= year <= last):
            continue
        seen.add(cite)
        insc = cite if kind == "insc" else idx["scr"].get(cite.upper())
        record = idx["insc"].get(insc) if insc else None
        case = _case_before(text, start)
        if record is None:
            out.append({"cited": cite, "case": case, "problem": "not in the Supreme Court record"})
            continue
        keys = _party_keys(case) if case else []
        rkeys = _party_keys(record[0].replace(" versus ", " v. "))
        if keys and rkeys and not any(
                k == r or (min(len(k), len(r)) >= 6 and (k in r or r in k)) for k in keys for r in rkeys):
            out.append({"cited": cite, "case": case,
                        "problem": f"belongs to {record[0].title()} ({record[1]})"})
    return out


def _in_sc_record(case: str, cite: str) -> bool:
    """True when `cite` is a neutral / S.C.R. citation in the official record
    and belongs to the case named."""
    m = _INSC_RE.search(cite or "")
    if not m:
        return False
    record = _sc_index()["insc"].get(f"{m.group(1)} INSC {int(m.group(2))}")
    if not record:
        return False
    keys, rkeys = _party_keys(case), _party_keys(record[0].replace(" versus ", " v. "))
    return any(k == r or (min(len(k), len(r)) >= 6 and (k in r or r in k)) for k in keys for r in rkeys)
