"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Supreme Court ruling scraper (Day 27)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Replaces the hand-curated SEED_RULINGS list in monitors.py with a live
daily scraper of Indian legal news sources. Each new ruling is parsed,
tagged with BNS/IPC sections it touches, and appended to the monitor corpus.

PROVIDER ABSTRACTION (same pattern as ecourts.py + llm_provider.py):
  - stub          (default) deterministic fake data, useful for tests + demos
  - livelaw       LiveLaw RSS feed (https://www.livelaw.in/rss.xml)
  - indiankanoon  IndianKanoon JSON endpoint (when API key is configured)

SCHEDULING: cron.py 'sc_scrape' job runs at 06:00 IST daily (before the
07:00 IST digest email). Appends to data/monitor_corpus/sc_rulings.json.

WHY NOT SCRAPE IN /analyze: scraping is slow + flaky. We pre-populate
once a day and serve from the local JSON corpus to keep /analyze fast.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

_RULINGS_FILE = Path(__file__).parent / "data" / "monitor_corpus" / "sc_rulings.json"

# Regex to find BNS / IPC / BNSS / BSA section references in ruling text/title
_SECTION_PATTERNS = [
    (re.compile(r"\bBNS\s+(?:Section\s+)?(\d+[A-Z]?)\b", re.IGNORECASE), "BNS"),
    (re.compile(r"\bBNSS\s+(?:Section\s+)?(\d+[A-Z]?)\b", re.IGNORECASE), "BNSS"),
    (re.compile(r"\bBSA\s+(?:Section\s+)?(\d+[A-Z]?)\b", re.IGNORECASE), "BSA"),
    (re.compile(r"\bIPC\s+(?:Section\s+)?(\d+[A-Z]?)\b", re.IGNORECASE), "IPC"),
    (re.compile(r"\bSection\s+(\d+[A-Z]?)\s+IPC\b", re.IGNORECASE), "IPC"),
    (re.compile(r"\bSection\s+(\d+[A-Z]?)\s+BNS\b", re.IGNORECASE), "BNS"),
    (re.compile(r"\b(POCSO|NDPS|UAPA)\s+(?:Section\s+)?(\d+[A-Z]?)\b", re.IGNORECASE),
     lambda m: m.group(1).upper()),
]


@dataclass
class ScrapedRuling:
    id: str
    title: str
    court: str = "Supreme Court of India"
    date: str = ""
    neutral_citation: str = ""
    sections: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_url: str = ""
    ratio: str = ""
    practice_impact: str = ""


# ─── Provider selection ───────────────────────────────────────────────────────
def get_provider() -> str:
    return (os.getenv("SC_SCRAPER_PROVIDER") or "stub").lower()


def extract_sections(text: str) -> list[str]:
    """Find every section reference in text. Returns ['BNS 85', 'IPC 498A', ...]."""
    found = set()
    for pattern, statute in _SECTION_PATTERNS:
        for m in pattern.finditer(text or ""):
            if callable(statute):
                found.add(f"{statute(m)} {m.group(2)}")
            else:
                num = m.group(1).upper()
                found.add(f"{statute} {num}")
    return sorted(found)


def extract_tags(text: str) -> list[str]:
    """Crude tag extraction from title/summary. Returns lowercase keywords."""
    keywords = [
        "arrest", "bail", "dowry", "rape", "murder", "assault", "kidnap",
        "theft", "fraud", "cheating", "matrimonial", "POCSO", "NDPS",
        "terrorism", "sedition", "cybercrime", "trafficking", "lynching",
        "mob", "communal", "498a", "harassment", "domestic violence",
        "constitutional", "writ", "habeas", "fundamental rights",
    ]
    text_lo = (text or "").lower()
    return sorted([k.lower() for k in keywords if k.lower() in text_lo])


# ─── stub provider (default — deterministic, for tests + demos) ──────────────
def _scrape_stub() -> list[ScrapedRuling]:
    """Returns 2 fake-but-realistic rulings dated today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        ScrapedRuling(
            id=f"scr_stub_{today}_001",
            title="State of Karnataka v. M.R. Singh (Stub Daily Ruling 1)",
            date=today,
            neutral_citation="2026 INSC STUB-001",
            sections=["BNS 85", "BNS 80", "BNSS 35"],
            tags=["dowry", "498a", "matrimonial"],
            source_url="https://example.invalid/stub-1",
            ratio=(
                "Stub ruling for testing. Court reaffirms that BNS 85 (matrimonial "
                "cruelty) requires notice under BNSS 35 before arrest, extending the "
                "Arnesh Kumar (2014) protections."
            ),
            practice_impact=(
                "Re-confirm every BNS 85 case has a documented 35 notice before "
                "filing the chargesheet."
            ),
        ),
        ScrapedRuling(
            id=f"scr_stub_{today}_002",
            title="Union of India v. ABC Industries (Stub Daily Ruling 2)",
            date=today,
            neutral_citation="2026 INSC STUB-002",
            sections=["BNS 111", "BNS 113"],
            tags=["organised crime", "cybercrime"],
            source_url="https://example.invalid/stub-2",
            ratio=(
                "Stub ruling. Court clarifies scope of BNS 111 (organised crime) "
                "vis-à-vis pre-existing MCOCA provisions in Maharashtra."
            ),
            practice_impact="MCOCA cases pending post-July 2024 should be re-examined.",
        ),
    ]


# ─── livelaw RSS provider ─────────────────────────────────────────────────────
def _scrape_livelaw(max_items: int = 25) -> list[ScrapedRuling]:
    """Parse LiveLaw RSS feed for Supreme Court rulings."""
    feed_url = os.getenv("LIVELAW_RSS_URL", "https://www.livelaw.in/rss.xml")
    try:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "Lex-Indic SC-scraper/1.0 (+legal research)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"LiveLaw RSS fetch failed: {e}") from e

    rulings: list[ScrapedRuling] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise RuntimeError(f"LiveLaw RSS XML parse failed: {e}") from e

    # RSS 2.0 structure: <rss><channel><item><title/link/description/pubDate>
    for item in root.findall(".//item")[:max_items]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        # Filter — only Supreme Court rulings
        title_lo = (title + " " + desc).lower()
        if not ("supreme court" in title_lo or "scc" in title_lo or "insc" in title_lo):
            continue

        # Extract sections + tags from title + desc
        full_text = f"{title} {desc}"
        sections = extract_sections(full_text)
        tags = extract_tags(full_text)
        # If no legal sections found, skip — probably not a ruling we care about
        if not sections and not tags:
            continue

        # Try to extract neutral citation like "2024 INSC 891"
        cit_match = re.search(r"\b(\d{4}\s+INSC\s+\d+)\b", full_text)
        citation = cit_match.group(1) if cit_match else ""

        # Parse pub_date into ISO YYYY-MM-DD if possible
        iso_date = ""
        try:
            from email.utils import parsedate_to_datetime
            iso_date = parsedate_to_datetime(pub_date).date().isoformat()
        except Exception:
            iso_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        rulings.append(ScrapedRuling(
            id=f"scr_livelaw_{uuid.uuid4().hex[:10]}",
            title=title[:200],
            date=iso_date,
            neutral_citation=citation,
            sections=sections,
            tags=tags,
            source_url=link,
            ratio=desc[:500],
            practice_impact="(extracted automatically — review for accuracy)",
        ))
    return rulings


# ─── indiankanoon provider (paid API; stubbed unless key set) ────────────────
def _scrape_indiankanoon(max_items: int = 25) -> list[ScrapedRuling]:
    api_key = os.getenv("INDIANKANOON_API_KEY", "")
    if not api_key:
        # Soft fallback to stub instead of crashing
        return _scrape_stub()
    # Real IndianKanoon JSON endpoint — placeholder until paid account
    endpoint = "https://api.indiankanoon.org/search/"
    try:
        req = urllib.request.Request(
            f"{endpoint}?formInput=fromdate:1-1-2024 doctypes:supremecourt",
            headers={
                "Authorization": f"Token {api_key}",
                "User-Agent": "Lex-Indic SC-scraper/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return _scrape_stub()

    rulings = []
    for doc in data.get("docs", [])[:max_items]:
        title = doc.get("title", "")
        text = doc.get("snippet", "")
        rulings.append(ScrapedRuling(
            id=f"scr_kanoon_{doc.get('tid', uuid.uuid4().hex[:10])}",
            title=title[:200],
            date=doc.get("publishdate", "")[:10],
            sections=extract_sections(f"{title} {text}"),
            tags=extract_tags(f"{title} {text}"),
            source_url=f"https://indiankanoon.org/doc/{doc.get('tid')}/",
            ratio=text[:500],
        ))
    return rulings


# ─── Public dispatch ──────────────────────────────────────────────────────────
def scrape(provider: str | None = None) -> list[ScrapedRuling]:
    """Scrape latest SC rulings using the configured provider."""
    p = (provider or get_provider()).lower()
    if p == "livelaw":
        return _scrape_livelaw()
    if p == "indiankanoon":
        return _scrape_indiankanoon()
    return _scrape_stub()


# ─── Merge into the monitor corpus ────────────────────────────────────────────
def merge_into_corpus(new_rulings: list[ScrapedRuling]) -> dict:
    """
    Append new rulings to data/monitor_corpus/sc_rulings.json without
    creating duplicates (matched by id).
    """
    _RULINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _RULINGS_FILE.exists():
        existing = json.loads(_RULINGS_FILE.read_text(encoding="utf-8"))
    else:
        existing = []

    existing_ids = {r.get("id") for r in existing}
    added = 0
    for r in new_rulings:
        if r.id in existing_ids:
            continue
        existing.append(asdict(r))
        added += 1

    if added:
        _RULINGS_FILE.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return {"added": added, "total": len(existing), "provider": get_provider()}


def run_daily_scrape(provider: str | None = None) -> dict:
    """One-shot: scrape + merge. Called by cron."""
    try:
        new_rulings = scrape(provider)
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200], "added": 0}
    result = merge_into_corpus(new_rulings)
    result["status"] = "ok"
    result["scraped"] = len(new_rulings)
    return result
