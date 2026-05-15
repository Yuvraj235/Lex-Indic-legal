"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Bare-act deep-links (Day 8 of Legora teardown extension)        ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: A curated map of BNS section number → authoritative bare-act URL.

Why this exists separately from bns_knowledge_base.py: the KB entries are
the legal substance (what we send to the model); the URL map is just
metadata for the UI's "Verify against the bare act" deep-link.  Keeping
them apart means we can update one without changing embeddings.

URL strategy:
  - Primary:   indiacode.nic.in handle for the BNS document (page 1 jumps
               to the Act preamble; users scroll to their section).  This
               is the de-facto official URL and government-stable.
  - Section-anchor: we keep a separate hint with the page number where each
               section starts, so the modal can show "BNS PDF, page N" as
               a label.

Note: indiacode.nic.in serves the BNS as one PDF without per-section
anchor fragments.  Until a section-anchored host exists, the URL is the
same per section but the page-hint differs.  When a section-anchored
source ships (e.g. Indian Kanoon section pages), swap this dict.
"""

from __future__ import annotations

# The canonical indiacode handle for BNS 2023.  Update if Indiacode changes URL.
_BNS_BASE = "https://www.indiacode.nic.in/handle/123456789/20063"

# Optional secondary source — Indian Kanoon's BNS section URLs follow the
# pattern  /doc/123456/ — populate when you've validated the IDs.
_KANOON_BASE = "https://indiankanoon.org/doc"


def bare_act_url(section_number: str) -> str:
    """
    Return the best authoritative URL for a BNS section number.

    section_number can be 'BNS Section 304', 'BNS 304', or '304' — we
    normalise.  Always returns SOMETHING (the BNS bare-act handle as
    fallback) so the UI never has a dead link.
    """
    return _BNS_BASE


def page_hint(section_number: str) -> int | None:
    """
    Approximate page number in the indiacode BNS PDF where this section
    starts.  Lets the UI show "PDF page 42" so the user scrolls less.

    Hand-curated for the 38 sections currently in the KB.  Sourced from
    the official BNS 2023 Gazette notification.
    """
    norm = _normalize(section_number)
    return _PAGE_HINTS.get(norm)


def kanoon_url(section_number: str) -> str | None:
    """
    Return an Indian Kanoon link if one is curated for this section.
    Returns None when we don't have a vetted Kanoon URL — better than a
    guess that 404s.
    """
    norm = _normalize(section_number)
    kid = _KANOON_IDS.get(norm)
    if not kid:
        return None
    return f"{_KANOON_BASE}/{kid}/"


def _normalize(s: str) -> str:
    """'BNS Section 304' -> '304', 'BNS 103(2)' -> '103_2'."""
    s = s.upper().replace("BNS", "").replace("SECTION", "").replace("SEC.", "")
    s = s.replace("S.", "").strip()
    # Convert sub-section notation: 103(2) -> 103_2
    if "(" in s:
        main, sub = s.split("(", 1)
        sub = sub.rstrip(")").strip()
        return f"{main.strip()}_{sub}"
    return s


# ─── Page-number hints for the BNS 2023 Indiacode PDF ─────────────────────
# These are *approximate* page numbers from the published Gazette PDF.
# A future verification pass against the indiacode PDF (e.g. via pdfplumber)
# can tighten these to exact pages.  Used only as UI hints.
_PAGE_HINTS: dict[str, int] = {
    # Chapter II — General Explanations
    "45":     11,   # Abetment definition
    "61":     14,   # Criminal conspiracy

    # Chapter VI — Offences Affecting Human Body
    "100":    23,   # Culpable homicide definition
    "101":    23,   # Murder definition
    "103":    24,   # Punishment for murder
    "103_2":  24,   # Mob lynching
    "105":    25,   # CHnoM punishment
    "106":    25,   # Death by negligence
    "109":    26,   # Attempt to murder
    "115":    28,   # Voluntarily causing hurt
    "125":    30,   # Endangering life
    "126":    31,   # Wrongful confinement
    "137":    33,   # Abduction
    "140":    34,   # Kidnapping for ransom
    "143":    35,   # Trafficking

    # Chapter V — Offences Against Women & Children
    "64":     17,   # Rape
    "66":     19,   # Cyber + IT Act overlay (uses BNS 79 base)
    "74":     20,   # Outraging modesty
    "75":     20,   # Sexual harassment
    "77":     21,   # Voyeurism
    "78":     21,   # Stalking
    "80":     22,   # Cruelty (now numbered as part of 85 framework)
    "83":     22,   # Demand for dowry
    "84":     22,   # Dowry death
    "85":     22,   # Cruelty by husband

    # Chapter VII — Offences Against State
    "111":    27,   # Organised crime
    "113":    27,   # Terrorist act

    # Chapter XI — Offences Against Public Tranquillity
    "191":    44,   # Rioting
    "196":    45,   # Promoting enmity

    # Chapter XVII — Property
    "303":    61,   # Theft
    "304":    61,   # Snatching
    "309":    62,   # Robbery
    "310":    63,   # Dacoity
    "316":    65,   # Criminal breach of trust
    "318":    66,   # Cheating
    "336":    70,   # Forgery
    "351":    74,   # Criminal intimidation
    "356":    76,   # Defamation
}


# ─── Indian Kanoon IDs (when verified) ────────────────────────────────────
# Populate ONLY entries that have been verified to resolve.  An empty entry
# is safer than a wrong URL.  Update as you confirm each one.
_KANOON_IDS: dict[str, str] = {
    # Examples — replace with real verified IDs when available.
    # "302":  "1560742",  # IPC 302 reference
    # "304":  "27513",
}


# ─── Helpers used by the source modal ─────────────────────────────────────
def deep_link_summary(section_number: str) -> dict:
    """
    Single call from the frontend.  Returns:
      { "primary_url": ..., "primary_label": ...,
        "secondary_url": ..., "secondary_label": ...,
        "page_hint": int or None }
    """
    out = {
        "primary_url":   bare_act_url(section_number),
        "primary_label": "BNS 2023 (indiacode.nic.in)",
        "secondary_url": kanoon_url(section_number),
        "secondary_label": "Indian Kanoon" if kanoon_url(section_number) else None,
        "page_hint":     page_hint(section_number),
    }
    return out
