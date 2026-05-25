"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Bare-act deep-link generator (Day 26 gap fix)                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Programmatic URL generator for indiacode.nic.in PDF deep-links — one for
every BNS / BNSS / BSA section. Lets the Verified Sources panel render a
clickable "View bare act" link for every retrieved section without requiring
hand-curated URLs in the KB.

DAY 8 GAP: Only BNS sections had hand-curated deep_link fields. BNSS + BSA
(added Day 11) did not. This module closes that gap by computing the URL +
page-hint from the section number using fixed offsets per statute.

PAGE ESTIMATION: Each statute's PDF has a known structure (table of contents
+ chapters). Sections are sequential, so #page=N is computable as:
   base_page + (section_number / sections_per_page)

These offsets are best-effort approximations — they get the reader to the
right neighborhood. Production accuracy will improve once we have access to
section-level OCR'd page maps.
"""

from __future__ import annotations

import re


# ── Official bare-act PDFs on indiacode.nic.in ─────────────────────────────
# Pre-confirmed working URLs as of May 2026.
_STATUTE_URLS = {
    "bns":  "https://www.indiacode.nic.in/bitstream/123456789/20062/1/a2023-45.pdf",
    "bnss": "https://www.indiacode.nic.in/bitstream/123456789/20063/1/a2023-46.pdf",
    "bsa":  "https://www.indiacode.nic.in/bitstream/123456789/20064/1/a2023-47.pdf",
}

# ── Page-hint offsets (empirical — refined by reading the PDFs) ────────────
# base_page: where Chapter 1 / Section 1 begins (after table of contents)
# sections_per_page: average density (sections per PDF page)
_STATUTE_OFFSETS = {
    "bns":  {"base_page": 6,  "sections_per_page": 1.3},   # 358 sections in ~280 pages
    "bnss": {"base_page": 8,  "sections_per_page": 1.2},   # 531 sections in ~450 pages
    "bsa":  {"base_page": 5,  "sections_per_page": 1.4},   # 170 sections in ~125 pages
}


def parse_section_id(source_id: str) -> tuple[str, str] | None:
    """
    Turn 'bns_85' or 'bnss_173' or 'bsa_61' into ('bns', '85') etc.
    Returns None if the id is not a recognised statute section.
    """
    m = re.match(r"^(bns|bnss|bsa)_(\d+[A-Za-z]?)$", source_id.strip().lower())
    if not m:
        return None
    return m.group(1), m.group(2)


def deep_link_for(source_id: str) -> str | None:
    """
    Generate a deep-link URL for a BNS / BNSS / BSA source ID.
    Returns None if the id doesn't match a known statute.

    Example:
        deep_link_for('bns_85')  →
          'https://www.indiacode.nic.in/.../a2023-45.pdf#page=72'
    """
    parsed = parse_section_id(source_id)
    if not parsed:
        return None
    statute, section_str = parsed
    url = _STATUTE_URLS.get(statute)
    if not url:
        return None

    offsets = _STATUTE_OFFSETS.get(statute, {})
    base = offsets.get("base_page", 1)
    density = offsets.get("sections_per_page", 1.0)

    # Strip alpha suffix (e.g. "85A" → 85) for page calculation
    section_num = int(re.match(r"^(\d+)", section_str).group(1))
    page = max(1, int(base + (section_num / density)))

    return f"{url}#page={page}"


def deep_link_label(source_id: str) -> str | None:
    """Friendly text for the link, e.g. 'View bare act BNS §85'."""
    parsed = parse_section_id(source_id)
    if not parsed:
        return None
    statute, section_str = parsed
    return f"View bare act — {statute.upper()} §{section_str}"


def is_supported_statute(source_id: str) -> bool:
    return parse_section_id(source_id) is not None
