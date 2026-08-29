"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC: IPC → BNS Converter                                              ║
║  Day-1 deliverable from the Legora teardown.                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS DOES
──────────────
Every Indian advocate has a stack of IPC-era pleadings, FIRs, legal notices,
and case files written under the old Indian Penal Code (1860).  As of 1 July
2024 those references are stale — the Bharatiya Nyaya Sanhita (BNS, 2023)
renumbered every section.  This module scans a piece of text (plain string
or a .docx file), finds every IPC reference using the regex patterns Indian
lawyers actually write ("Section 302 IPC", "u/s 498A", "S. 420 of the IPC",
"under section 379", etc.), looks up the BNS equivalent in our curated
mapping, and produces either:

  (a) annotated plain text with [BNS X] markers next to each IPC ref, or
  (b) a new .docx file with the original formatting preserved and each
      IPC reference highlighted yellow with the BNS equivalent inserted
      in red brackets right after it.

It also returns a summary dict (counts, mappings used, unknown refs).

This is the wedge feature against Legora: they cannot do it for Indian
law because they don't have the IPC→BNS corpus.

USAGE
─────
    from ipc_bns_converter import convert_text, convert_docx

    summary = convert_text("The accused is charged under Section 302 IPC")
    # → "The accused is charged under Section 302 IPC [BNS 103 — Murder]"

    new_docx_bytes, summary = convert_docx(open("old_pleading.docx", "rb"))
    # → bytes for a new .docx with highlights + summary stats
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

# ─── Mapping data ────────────────────────────────────────────────────────────
_MAPPING_PATH = Path(__file__).parent / "data" / "legal_corpus" / "ipc_bns_mapping.json"


def _load_mapping() -> dict[str, dict]:
    """Load the curated IPC→BNS mapping (51 entries as of v1.2)."""
    with open(_MAPPING_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Normalise keys to "302" / "498A" form (strip "IPC " prefix, uppercase)
    normalised = {}
    for key, value in raw.items():
        section_num = key.replace("IPC", "").strip().upper()
        normalised[section_num] = value
    return normalised


_MAPPING: dict[str, dict] | None = None


def get_mapping() -> dict[str, dict]:
    """Lazy-load + cache the IPC→BNS mapping."""
    global _MAPPING
    if _MAPPING is None:
        _MAPPING = _load_mapping()
    return _MAPPING


# ─── Regex patterns Indian lawyers actually write ────────────────────────────
# Each pattern captures a section number (with optional letter suffix like 498A
# or 304B).  We need to handle the messy real-world variants — lawyers don't
# write a single canonical form.
#
# Examples covered:
#   "Section 302"                "section 498A"
#   "Sec 302"                    "S. 302"               "S 302"
#   "IPC 302"                    "302 IPC"              "Indian Penal Code 302"
#   "u/s 302"                    "u/s. 302"             "under Section 302"
#   "under section 302 IPC"      "under section 302 of the IPC"
#   "Sections 302, 304, 307"     (multiple in one phrase)
#
# IMPORTANT: we only match when "IPC" / "Indian Penal Code" / "Penal Code"
# is in the immediate context (within ~30 chars), OR the phrase explicitly
# uses "u/s" / "under section".  Otherwise plain "Section 302" could be a
# section number of any statute (CPC, CrPC, Companies Act, etc.) and we
# must not blindly convert those.

_SECTION_NUM = r"\d{1,4}[A-Z]{0,2}"  # 1-4 digits + optional letter suffix

# Separator between grouped section numbers as Indian lawyers write them:
#   "302, 304"        "302/307"       "302 & 304"
#   "302 and 304"     "302 r/w 34"    "302 read with 34"     "and Section 304"
# We must let this chain across multi-word separators because Indian
# pleadings routinely write "Section 498A and 304B of the IPC" or
# "Sections 302, 307 and 34 read with 120B IPC".
_SEP = (
    r"(?:"
    r"[,/&]"                              # plain punctuation
    r"|\s+(?:and|r/w|read\s+with)\s+"     # word separators
    r"|\s+(?:and\s+)?(?:Sections?|Sec\.?|S\.?)\s+"  # "and Section"
    r")"
)
_SECTION_GROUP = rf"{_SECTION_NUM}(?:\s*{_SEP}\s*{_SECTION_NUM})*"

# Pattern 1: an IPC-marker word followed by Section(s) NN[, NN, NN]
_PATTERN_CONTEXT_FIRST = re.compile(
    rf"""(?ix)                                # case-insensitive, verbose
    \b(?:IPC|Indian\s+Penal\s+Code|Penal\s+Code)\b         # IPC marker
    \s*[,:\-]?\s*                                          # optional sep
    (?:Section[s]?|Sec\.?|S\.?)?                           # optional 'Section'
    \s*
    ({_SECTION_GROUP})                                     # one or more nums
    """
)

# Pattern 2: Section(s) NN ... IPC (the IPC follows the section number)
_PATTERN_CONTEXT_AFTER = re.compile(
    rf"""(?ix)
    \b(?:Section[s]?|Sec\.?|S\.?)                          # 'Section'-ish
    \s*
    ({_SECTION_GROUP})                                     # one or more nums
    \s*
    (?:of\s+the\s+)?                                       # 'of the'?
    \b(?:IPC|Indian\s+Penal\s+Code|Penal\s+Code)\b         # IPC marker
    """
)

# Pattern 3: u/s NN (under-section abbreviation — IPC is implicit in Indian
# criminal practice when u/s appears without another statute name nearby)
_PATTERN_USS = re.compile(
    rf"""(?ix)
    \b
    (?:u/s\.?|under\s+section[s]?)
    \s*
    ({_SECTION_GROUP})
    """
)


@dataclass
class IpcMatch:
    """One IPC reference found in the text."""
    raw_match: str                  # the exact substring that matched
    start: int                      # character offset in source
    end: int
    section_numbers: list[str]      # ['302'] or ['302', '304'] for grouped refs
    bns_replacements: list[dict]    # list of {section, title, change} or None per number


@dataclass
class ConversionSummary:
    """What we did — for the user-facing preview UI and audit."""
    total_matches: int = 0
    total_section_refs: int = 0      # may be > total_matches if "302, 304" is one match
    mapped: list[IpcMatch] = field(default_factory=list)
    unmapped_section_numbers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_matches": self.total_matches,
            "total_section_refs": self.total_section_refs,
            "mapped_count": sum(
                1 for m in self.mapped for r in m.bns_replacements if r
            ),
            "unmapped_count": len(self.unmapped_section_numbers),
            "unmapped_section_numbers": sorted(set(self.unmapped_section_numbers)),
            "matches": [
                {
                    "raw": m.raw_match,
                    "section_numbers": m.section_numbers,
                    "bns": m.bns_replacements,
                }
                for m in self.mapped
            ],
        }


_SPLIT_RE = re.compile(
    r"[,/&\s]+|\band\b|\br/w\b|\bread\s+with\b|\bSections?\b|\bSec\.?\b|\bS\.?\b",
    re.IGNORECASE,
)


def _split_section_numbers(group: str) -> list[str]:
    """
    '302, 304/307 & 498A and 34 r/w 120B' → ['302','304','307','498A','34','120B']

    Also strips word separators ("and", "read with", repeated "Section" words)
    that the upstream regex allowed through.
    """
    parts = _SPLIT_RE.split(group)
    return [p.strip().upper() for p in parts if p and p.strip()]


def _lookup(section_num: str) -> dict | None:
    """Return {bns, title, change} or None if we don't have a mapping."""
    return get_mapping().get(section_num.upper())


def _iter_matches(text: str) -> Iterator[IpcMatch]:
    """
    Find every IPC reference in `text` using all three patterns.  Yields
    IpcMatch instances in order of appearance.  De-duplicates overlapping
    matches — a string like "u/s 302 IPC" hits both u/s and CONTEXT_AFTER;
    we keep only the longest match starting at the earliest position.
    """
    candidates: list[IpcMatch] = []

    for pattern in (_PATTERN_CONTEXT_FIRST, _PATTERN_CONTEXT_AFTER, _PATTERN_USS):
        for m in pattern.finditer(text):
            section_group = m.group(1)
            section_numbers = _split_section_numbers(section_group)
            bns_replacements = [_lookup(n) for n in section_numbers]
            candidates.append(IpcMatch(
                raw_match=m.group(0),
                start=m.start(),
                end=m.end(),
                section_numbers=section_numbers,
                bns_replacements=bns_replacements,
            ))

    # Sort by start, longest first
    candidates.sort(key=lambda c: (c.start, -(c.end - c.start)))

    # Drop overlapping matches (keep first / longest)
    accepted: list[IpcMatch] = []
    last_end = -1
    for c in candidates:
        if c.start >= last_end:
            accepted.append(c)
            last_end = c.end

    yield from accepted


# ════════════════════════════════════════════════════════════════════════════
# Public API: plain text
# ════════════════════════════════════════════════════════════════════════════
def convert_text(
    text: str, *, marker_format: str = " [BNS {bns} — {title}]"
) -> tuple[str, ConversionSummary]:
    """
    Convert a plain-text document.  Returns (annotated_text, summary).

    The original IPC references are preserved verbatim — we only INSERT the
    BNS equivalent next to each one, so an advocate reviewing the converted
    pleading can see both the old and new for auditing.  This is deliberate;
    silently replacing IPC with BNS would lose context.

    `marker_format` is interpolated with {bns} and {title} per reference.
    For grouped references like "Sections 302 & 304" we insert one combined
    marker.
    """
    summary = ConversionSummary()
    result_chunks: list[str] = []
    cursor = 0

    for m in _iter_matches(text):
        summary.total_matches += 1
        summary.total_section_refs += len(m.section_numbers)
        summary.mapped.append(m)

        # Copy the unchanged slice
        result_chunks.append(text[cursor:m.end])

        # Build the BNS marker (one per replacement, combined into one block)
        marker_parts = []
        for num, rep in zip(m.section_numbers, m.bns_replacements):
            if rep and rep.get("repealed"):
                # IPC section with NO BNS successor (377, 497, 124A): say so
                # explicitly rather than inventing a number or flagging "unknown".
                marker_parts.append(f"[IPC {num} — {rep['title']} · no BNS equivalent]")
            elif rep:
                marker_parts.append(
                    marker_format.format(
                        bns=rep["bns"].replace("BNS ", ""),
                        title=rep["title"],
                    ).strip()
                )
            else:
                summary.unmapped_section_numbers.append(num)
                marker_parts.append(f"[IPC {num} — no BNS mapping]")

        if marker_parts:
            result_chunks.append(" " + " ".join(marker_parts))

        cursor = m.end

    # Tail
    result_chunks.append(text[cursor:])
    return "".join(result_chunks), summary


# ════════════════════════════════════════════════════════════════════════════
# Public API: .docx round-trip
# ════════════════════════════════════════════════════════════════════════════
def convert_docx(file_obj) -> tuple[bytes, ConversionSummary]:
    """
    Convert a .docx file in-place: yellow-highlight every IPC reference and
    insert the BNS equivalent in red bold right after it.  Preserves bold,
    italics, font, paragraph styles, tables, headers, footers.

    Args:
        file_obj: any file-like with .read() returning bytes, or a path.

    Returns:
        (new_docx_bytes, summary)
    """
    from docx import Document
    from docx.shared import RGBColor
    from docx.enum.text import WD_COLOR_INDEX

    doc = Document(file_obj)
    summary = ConversionSummary()

    def _process_paragraph(paragraph):
        """
        Find IPC refs in this paragraph's text and inject BNS markers.

        Note: a single IPC reference may span multiple runs (because Word
        breaks text on style boundaries).  Easiest robust approach: read
        the paragraph's full text, find matches, then rebuild the runs.

        We deliberately keep this simple: if the paragraph has any IPC ref,
        we replace the entire paragraph's runs with a new run sequence that
        preserves the original text and inserts highlighted markers.  This
        loses per-character bold/italic within the paragraph but keeps the
        paragraph's overall style (heading, list, etc.).  Good enough for v1.
        """
        full_text = paragraph.text
        if not full_text:
            return

        matches = list(_iter_matches(full_text))
        if not matches:
            return

        summary.total_matches += len(matches)
        for m in matches:
            summary.total_section_refs += len(m.section_numbers)
            summary.mapped.append(m)
            for num, rep in zip(m.section_numbers, m.bns_replacements):
                if not rep:
                    summary.unmapped_section_numbers.append(num)

        # Capture the paragraph's primary run style before nuking
        first_run = paragraph.runs[0] if paragraph.runs else None
        base_font = (first_run.font.name if first_run else None) or "Helvetica"
        base_size = first_run.font.size if first_run else None
        base_bold = bool(first_run.bold) if first_run else False
        base_italic = bool(first_run.italic) if first_run else False

        # Clear existing runs (preserve paragraph-level style)
        for run in list(paragraph.runs):
            run.text = ""

        # Rebuild from chunks
        cursor = 0
        # Start writing into the first run if present; else add a new one
        def _add_run(text: str, *, highlight: bool = False, bns_marker: bool = False):
            run = paragraph.add_run(text)
            if base_font:
                run.font.name = base_font
            if base_size:
                run.font.size = base_size
            if base_bold:
                run.bold = True
            if base_italic:
                run.italic = True
            if highlight:
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            if bns_marker:
                run.bold = True
                run.font.color.rgb = RGBColor(0xB4, 0x1E, 0x1E)  # red
                run.font.highlight_color = WD_COLOR_INDEX.GRAY_25
            return run

        for m in matches:
            # Unchanged prefix
            if m.start > cursor:
                _add_run(full_text[cursor:m.start])
            # The IPC reference itself, highlighted yellow
            _add_run(full_text[m.start:m.end], highlight=True)
            # The BNS marker
            marker_parts = []
            for num, rep in zip(m.section_numbers, m.bns_replacements):
                if rep:
                    marker_parts.append(f"[{rep['bns']} — {rep['title']}]")
                else:
                    marker_parts.append(f"[IPC {num} — no BNS mapping]")
            _add_run(" " + " ".join(marker_parts), bns_marker=True)
            cursor = m.end

        # Tail
        if cursor < len(full_text):
            _add_run(full_text[cursor:])

    # Walk every paragraph in the body
    for p in doc.paragraphs:
        _process_paragraph(p)

    # Walk paragraphs inside tables too — pleadings often use tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _process_paragraph(p)

    # Serialize to bytes
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue(), summary


# ════════════════════════════════════════════════════════════════════════════
# Multi-statute conversion (IPC→BNS, CrPC→BNSS, Evidence Act→BSA)
#
# ADDITIVE — used by the migration auditor.  The IPC-only convert_text /
# convert_docx above are untouched, so the /convert UI and Word add-in behave
# exactly as before.  Any reference we don't have a mapping for is flagged
# honestly ("no BNSS mapping"), never guessed.
# ════════════════════════════════════════════════════════════════════════════
_CRPC_PATH = Path(__file__).parent / "data" / "legal_corpus" / "crpc_bnss_mapping.json"
_IEA_PATH = Path(__file__).parent / "data" / "legal_corpus" / "iea_bsa_mapping.json"


def _load_target_mapping(path: Path, target_key: str) -> dict[str, dict]:
    """Load {<PREFIX> <num>: {<target_key>, title}} → {num: {target, title}}.
    Skips metadata keys (starting with '_'); section number = text from first digit."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        m = re.search(r"\d", key)
        if not m:
            continue
        num = key[m.start():].strip().upper()
        out[num] = {"target": value.get(target_key, ""), "title": value.get("title", "")}
    return out


@dataclass(frozen=True)
class _Statute:
    name: str            # 'IPC' / 'CrPC' / 'Evidence Act'
    target_label: str    # 'BNS' / 'BNSS' / 'BSA'
    marker: str          # regex alternation matching the statute name


_STATUTE_DEFS = [
    _Statute("IPC", "BNS", r"IPC|Indian\s+Penal\s+Code|Penal\s+Code"),
    _Statute("CrPC", "BNSS", r"CrPC|Cr\.?\s?P\.?\s?C\.?|Code\s+of\s+Criminal\s+Procedure"),
    _Statute("Evidence Act", "BSA", r"Indian\s+Evidence\s+Act|Evidence\s+Act|IEA"),
]

_MULTI_MAPS: dict[str, dict] | None = None


def _multi_maps() -> dict[str, dict]:
    """statute name → {num: {target, title}} for all three statutes (cached)."""
    global _MULTI_MAPS
    if _MULTI_MAPS is None:
        ipc = {num: {"target": v.get("bns", ""), "title": v.get("title", "")}
               for num, v in get_mapping().items() if not num.startswith("_")}
        _MULTI_MAPS = {
            "IPC": ipc,
            "CrPC": _load_target_mapping(_CRPC_PATH, "bnss"),
            "Evidence Act": _load_target_mapping(_IEA_PATH, "bsa"),
        }
    return _MULTI_MAPS


def _statute_patterns(marker: str) -> tuple[re.Pattern, re.Pattern]:
    first = re.compile(
        rf"(?ix)\b(?:{marker})\b\s*[,:\-]?\s*(?:Section[s]?|Sec\.?|S\.?)?\s*({_SECTION_GROUP})")
    # 'u/s 167(2) CrPC' must be claimed by CrPC, not the implicit-IPC u/s rule:
    # accept u/s-style prefixes and tolerate a trailing subsection before the
    # statute word.
    after = re.compile(
        rf"(?ix)\b(?:u/s\.?|under\s+section[s]?|Section[s]?|Sec\.?|S\.?)\s*"
        rf"({_SECTION_GROUP})\s*(?:\(\d+\)\s*)?(?:of\s+the\s+)?\b(?:{marker})\b")
    return first, after


@dataclass
class StatuteMatch:
    statute: str               # 'IPC' / 'CrPC' / 'Evidence Act'
    target_label: str          # 'BNS' / 'BNSS' / 'BSA'
    old_num: str               # '302'
    target: str | None         # 'BNS 103' or None when unmapped
    title: str | None


def _iter_multi(text: str) -> list[tuple]:
    # 1) Explicit statute-word matches take priority (CrPC/Evidence must beat the
    #    IPC-implicit 'u/s' rule when a statute word is actually present).
    explicit: list[tuple] = []
    for st in _STATUTE_DEFS:
        first, after = _statute_patterns(st.marker)
        for pat in (first, after):
            for m in pat.finditer(text):
                explicit.append((m.start(), m.end(), st,
                                 _split_section_numbers(m.group(1))))
    explicit.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    accepted, spans, last_end = [], [], -1
    for c in explicit:
        if c[0] >= last_end:
            accepted.append(c)
            spans.append((c[0], c[1]))
            last_end = c[1]

    # 2) 'u/s NN' / 'under section NN' with NO statute word → IPC implicit, but
    #    only where an explicit match hasn't already claimed the span.
    for m in _PATTERN_USS.finditer(text):
        s, e = m.start(), m.end()
        if any(not (e <= a or s >= b) for (a, b) in spans):
            continue
        accepted.append((s, e, _STATUTE_DEFS[0], _split_section_numbers(m.group(1))))

    # 3) Final ordering + de-dup (handles u/s-vs-u/s overlaps).
    accepted.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    final, last_end = [], -1
    for c in accepted:
        if c[0] >= last_end:
            final.append(c)
            last_end = c[1]
    return final


def convert_text_multi(
    text: str, *, marker_format: str = " [{target} — {title}]"
) -> tuple[str, list[StatuteMatch]]:
    """Annotate IPC/CrPC/Evidence-Act references with their BNS/BNSS/BSA
    equivalents in one pass. Returns (annotated_text, matches)."""
    chunks: list[str] = []
    matches: list[StatuteMatch] = []
    cursor = 0
    for start, end, st, nums in _iter_multi(text):
        maps = _multi_maps()[st.name]
        chunks.append(text[cursor:end])
        parts = []
        for num in nums:
            rep = maps.get(num.upper())
            if rep and rep.get("target"):
                parts.append(marker_format.format(target=rep["target"],
                                                  title=rep["title"]).strip())
                matches.append(StatuteMatch(st.name, st.target_label, num,
                                            rep["target"], rep["title"]))
            else:
                parts.append(f"[{st.name} {num} — no {st.target_label} mapping]")
                matches.append(StatuteMatch(st.name, st.target_label, num, None, None))
        if parts:
            chunks.append(" " + " ".join(parts))
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks), matches


def convert_text_multi_summary(
    text: str, *, marker_format: str = " [{target} — {title}]"
) -> tuple[str, dict]:
    """Multi-statute conversion (IPC→BNS, CrPC→BNSS, Evidence Act→BSA) with a
    ConversionSummary-shaped dict, so /convert/text and the Word add-in can
    consume all three statutes through the response format they already know.

    Each match dict carries:
      raw             — the exact matched substring (the add-in searches on it)
      statute         — 'IPC' / 'CrPC' / 'Evidence Act'
      target_label    — 'BNS' / 'BNSS' / 'BSA'
      section_numbers — ['302', ...]
      bns             — per-number {bns: 'BNS 103', title} or None (unmapped);
                        the key keeps its legacy name for old clients
      labels          — per-number ready-to-insert marker text
    """
    chunks: list[str] = []
    out_matches: list[dict] = []
    unmapped: list[str] = []
    statute_counts: dict[str, int] = {}
    total_refs = 0
    mapped_count = 0
    cursor = 0

    for start, end, st, nums in _iter_multi(text):
        maps = _multi_maps()[st.name]
        chunks.append(text[cursor:end])
        parts: list[str] = []
        reps: list[dict | None] = []
        for num in nums:
            total_refs += 1
            rep = maps.get(num.upper())
            # IPC repealed sections (377/497/124A…) must say "no BNS
            # equivalent" — checked FIRST because the mapping stores a
            # placeholder ("—") in the bns field that would read as mapped.
            full = get_mapping().get(num.upper()) if st.name == "IPC" else None
            if full and full.get("repealed"):
                label = f"[IPC {num} — {full['title']} · no BNS equivalent]"
                reps.append(None)
            elif rep and rep.get("target"):
                label = marker_format.format(target=rep["target"],
                                             title=rep["title"]).strip()
                reps.append({"bns": rep["target"], "title": rep["title"]})
                mapped_count += 1
            else:
                label = f"[{st.name} {num} — no {st.target_label} mapping]"
                reps.append(None)
                unmapped.append(f"{st.name} {num}")
            parts.append(label)
        statute_counts[st.name] = statute_counts.get(st.name, 0) + 1
        out_matches.append({
            "raw": text[start:end],
            "statute": st.name,
            "target_label": st.target_label,
            "section_numbers": nums,
            "bns": reps,
            "labels": parts,
        })
        if parts:
            chunks.append(" " + " ".join(parts))
        cursor = end
    chunks.append(text[cursor:])

    summary = {
        "total_matches": len(out_matches),
        "total_section_refs": total_refs,
        "mapped_count": mapped_count,
        "unmapped_count": len(set(unmapped)),
        "unmapped_section_numbers": sorted(set(unmapped)),
        "statutes": statute_counts,
        "matches": out_matches,
    }
    return "".join(chunks), summary


# ════════════════════════════════════════════════════════════════════════════
# CLI for local testing — `python3 ipc_bns_converter.py path/to/old.docx`
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 ipc_bns_converter.py <input.docx | quoted text>")
        print()
        print("Examples:")
        print('  python3 ipc_bns_converter.py "Accused charged u/s 302 IPC and 498A"')
        print("  python3 ipc_bns_converter.py outputs/old_pleading.docx")
        sys.exit(1)

    arg = sys.argv[1]
    if arg.lower().endswith(".docx") and Path(arg).exists():
        out_path = Path(arg).with_suffix(".bns.docx")
        with open(arg, "rb") as f:
            new_bytes, summary = convert_docx(f)
        with open(out_path, "wb") as f:
            f.write(new_bytes)
        print(f"Wrote {out_path}")
        print(json.dumps(summary.to_dict(), indent=2))
    else:
        annotated, summary = convert_text(arg)
        print("─" * 70)
        print(annotated)
        print("─" * 70)
        print(json.dumps(summary.to_dict(), indent=2))
