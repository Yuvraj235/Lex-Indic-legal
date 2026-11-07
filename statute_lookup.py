"""
Deterministic answers for questions with exactly one right answer in our own
tables — no model involved, so nothing to hallucinate:

  "What is the BNS equivalent of IPC 323?"  → the government IPC→BNS concordance
  "Is BNS 115 bailable?" / "punishment under BNS 85?" → the verified BNS knowledge base

Anything else returns None and the caller falls back to RAG + LLM. Section
numbers are never recalled by a model when a table can answer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import data.bns_knowledge_base as _bns_kb

_MAPPING = Path(__file__).resolve().parent / "data" / "legal_corpus" / "ipc_bns_mapping.json"
_IPC_Q = re.compile(r"\bIPC\s*(?:section|sec\.?|s\.|§)?\s*(\d{1,3}[A-Z]{0,2})\b", re.I)
_SECTION_FIRST_IPC = re.compile(r"\bsection\s+(\d{1,3}[A-Z]{0,2})\s+(?:of\s+(?:the\s+)?)?(?:IPC|Indian\s+Penal\s+Code)\b", re.I)
_BNS_Q = re.compile(r"\bBNS\s*(?:section|sec\.?|s\.|§)?\s*(\d{1,3})\b", re.I)
_MAPPING_INTENT = re.compile(r"\b(equivalent|replace[ds]?|correspond\w*|new section|now under|"
                             r"under bns|in bns|bns section|which bns|what bns|became|converted?|map)\b", re.I)
_FACT_INTENT = {
    "bailable": re.compile(r"\bbail(?:able)?\b", re.I),
    "cognizable": re.compile(r"\bcogni[sz]able\b", re.I),
    "punishment": re.compile(r"\b(punish\w*|sentence|jail|imprison\w*|penalty|fine)\b", re.I),
}
_mapping_cache: dict | None = None
_kb_cache: dict | None = None


def _mapping() -> dict:
    global _mapping_cache
    if _mapping_cache is None:
        raw = json.loads(_MAPPING.read_text(encoding="utf-8"))
        _mapping_cache = {k.upper().replace(" ", ""): v for k, v in raw.items()
                          if not k.startswith("_") and isinstance(v, dict)}
    return _mapping_cache


def _kb() -> dict:
    global _kb_cache
    if _kb_cache is None:
        _kb_cache = {}
        for e in _bns_kb.BNS_SECTIONS:
            m = re.search(r"(\d+)", e.get("section", ""))
            if m:
                _kb_cache.setdefault(m.group(1), e)
    return _kb_cache


def ipc_to_bns_answer(question: str) -> dict | None:
    """{'answer': ..., 'source': ...} for 'BNS equivalent of IPC N' questions."""
    m = _IPC_Q.search(question) or _SECTION_FIRST_IPC.search(question)
    if not m or not _MAPPING_INTENT.search(question):
        return None
    ipc = m.group(1).upper()
    entry = _mapping().get(f"IPC{ipc}")
    if not entry:
        return None
    if entry.get("repealed"):
        text = f"IPC {ipc} ({entry['title']}) has no direct BNS equivalent. {entry.get('change', '')}"
    else:
        text = (f"IPC {ipc} ({entry['title']}) is now {entry['bns']} of the Bharatiya Nyaya "
                f"Sanhita, 2023. {entry.get('change', '')}".strip())
    return {"answer": text.strip(), "source": "Government IPC→BNS concordance",
            "bns": entry.get("bns"), "ipc": f"IPC {ipc}"}


def bns_fact_answer(question: str) -> dict | None:
    """{'answer': ..., 'source': ...} for bailable / cognizable / punishment of BNS N."""
    m = _BNS_Q.search(question)
    if not m:
        return None
    asked = [k for k, pat in _FACT_INTENT.items() if pat.search(question)]
    entry = _kb().get(m.group(1))
    if not asked or not entry:
        return None
    labels = {"bailable": "Bail status", "cognizable": "Cognizable", "punishment": "Punishment"}
    parts = [f"{entry['section']} — {entry['title']} (old {entry.get('old_ipc', 'n/a')})."]
    for k in asked:
        if entry.get(k):
            parts.append(f"{labels[k]}: {entry[k]}.")
    return {"answer": " ".join(parts), "source": "Lex-Indic verified BNS knowledge base",
            "bns": entry["section"]}


def answer(question: str) -> dict | None:
    """A deterministic answer if the question has one, else None."""
    return ipc_to_bns_answer(question) or bns_fact_answer(question)
