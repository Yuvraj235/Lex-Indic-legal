"""
Section selection over the official BNS title list.

Similarity search ranks sibling sections almost equally — the local embedder
scored "Theft" below "Deserter concealed on board merchant vessel" for a
pickpocketing story. The BNS is a closed list of 358 official titles, small
enough to show a model whole, so the model reads the facts and picks the
sections; retrieval then fetches those sections' official text by number and
similarity search only fills the remaining slots.

Only numbers that exist in the official text are ever returned.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import llm_provider

_TITLES = Path(__file__).resolve().parent / "data" / "legal_corpus" / "statutes" / "bns_section_titles.json"
_LIST: str | None = None
_VALID: set[str] | None = None

SYSTEM = (
    "You select provisions of the Bharatiya Nyaya Sanhita, 2023 (BNS) for an Indian "
    "criminal lawyer. You are given the complete official list of BNS sections and a "
    "client's facts. Choose the sections whose offence the facts may attract, including "
    "the close alternatives a careful lawyer must rule in or out (theft / snatching / "
    "robbery; hurt / grievous hurt / attempt to murder; cheating / breach of trust). "
    "Prefer the section that punishes an offence over the one that only defines it. "
    "Ignore procedure. Answer with JSON only: {\"sections\": [\"303\", \"305\"]}."
)


def title_list() -> str:
    global _LIST, _VALID
    if _LIST is None:
        titles = json.loads(_TITLES.read_text(encoding="utf-8"))["sections"]
        _VALID = set(titles)
        _LIST = "\n".join(f"{n}: {t}" for n, t in titles.items())
    return _LIST


def parse_selection(text: str, limit: int) -> list[str]:
    """Section numbers from the model's reply — JSON if it gave JSON, else any
    'BNS 303' / bare numbers in a sections list; only real sections, in order."""
    title_list()
    nums: list[str] = []
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            nums = [re.sub(r"\D.*$", "", str(x).replace("BNS", "").strip())
                    for x in json.loads(m.group(0)).get("sections", [])]
        except (ValueError, AttributeError):
            nums = []
    if not nums:
        nums = re.findall(r"\b(\d{1,3})\b", text or "")
    out: list[str] = []
    for n in nums:
        if n in _VALID and n not in out:
            out.append(n)
    return out[:limit]


def enabled() -> bool:
    """Opt-in (SECTION_SELECTOR=local). Measured 2026-11-08 on the 67 stress
    scenarios: qwen3:8b picked wrong sections (theft for an online advance-fee
    fraud, hurt for a dowry death) and cut retrieval recall from 68% to 41%;
    with thinking on it took 90–166 s and still missed. Needs a stronger
    local model before it is turned on by default."""
    return (os.getenv("SECTION_SELECTOR") or "").strip().lower() == "local"


def select_sections(story: str, limit: int = 6) -> list[str]:
    reply = llm_provider.complete_local(
        system_messages=[SYSTEM],
        user_message=f"OFFICIAL BNS SECTIONS:\n{title_list()}\n\nCLIENT'S FACTS:\n{story}\n\n"
                     f"Up to {limit} section numbers, most relevant first. JSON only.",
        temperature=0.0, max_tokens=200, timeout_s=180, think=False,
    )["text"]
    return parse_selection(reply, limit)
