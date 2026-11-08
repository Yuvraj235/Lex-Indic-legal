"""
Official text of the three criminal-law Acts as retrieval documents.

Source files (data/legal_corpus/statutes/) are extracted from the Gazette of
India, 25 Dec 2023: every section of the BNS (358), BNSS (531) and BSA (170)
with its official marginal title, plus the BNSS First Schedule classification
(punishment, cognizable, bailable, triable by) for BNS offences.

One document per section: official title + text, the old IPC/CrPC/IEA section
it replaced, the official classification, and — where the hand-curated
knowledge base covers the section — its plain-language keywords, which help
the search match how clients describe facts ("chain snatched", "in-laws").

Pure module: no network, no Flask.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_STATUTES = Path(__file__).resolve().parent / "data" / "legal_corpus" / "statutes"
_MAPPINGS = {"BNS": ("ipc_bns_mapping.json", "bns", "IPC"),
             "BNSS": ("crpc_bnss_mapping.json", "bnss", "CrPC"),
             "BSA": ("iea_bsa_mapping.json", "bsa", "IEA")}
MAX_TEXT = 1400          # characters of section text per document (prompt budget)


def _load(name: str) -> dict:
    return json.loads((_STATUTES / name).read_text(encoding="utf-8"))


def _base(section: str) -> str:
    return re.sub(r"\(.*$", "", section.strip().split()[-1])


def old_sections(code: str) -> dict[str, list[str]]:
    """New section number → the old-code sections it replaced (verified tables)."""
    fname, key, old = _MAPPINGS[code]
    raw = json.loads((_STATUTES.parent / fname).read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        targets = [v.get(key) or ""] + list(v.get(f"also_{key}", []))
        for t in targets:
            if t.startswith(code + " "):
                out.setdefault(_base(t), []).append(k)
    return out


def classification() -> dict[str, list[dict]]:
    """BNS base section → First Schedule rows (one per sub-section/variant)."""
    out: dict[str, list[dict]] = {}
    for row in _load("bns_classification.json")["rows"]:
        out.setdefault(_base(row["section"]), []).append(row)
    return out


def _classification_line(rows: list[dict]) -> str:
    parts = []
    for r in rows[:4]:
        bits = [b for b in (r["punishment"], r["cognizable"].rstrip("."), r["bailable"],
                            r["court"].rstrip(".")) if b]
        parts.append(f"{r['section']}: " + "; ".join(bits))
    return " | ".join(parts)


def _curated_extras(curated_docs: list[str]) -> dict[str, dict[str, str]]:
    """'BNS 85' → {'KEYWORDS': …, 'TRANSITION NOTE': …} from the curated
    knowledge-base document (plain-language search terms and practice notes)."""
    out: dict[str, dict[str, str]] = {}
    for doc in curated_docs:
        head = re.match(r"(BNS|BNSS|BSA) Section (\d+)", doc)
        if not head:
            continue
        extras = {}
        for field in ("KEYWORDS", "TRANSITION NOTE"):
            m = re.search(rf"^{field}:\s*(.+)$", doc, re.M)
            if m:
                extras[field] = m.group(1).strip()
        extras["_card"] = doc            # plain-language card: best search key
        out[f"{head.group(1)} {head.group(2)}"] = extras
    return out


def official_documents(curated_docs: list[str] | None = None
                       ) -> tuple[list[str], list[dict], list[str]]:
    """(documents, metadatas, ids) for every section of the three Acts."""
    extras = _curated_extras(curated_docs or [])
    schedule = classification()
    docs, metas, ids = [], [], []
    for code in ("BNS", "BNSS", "BSA"):
        titles = _load(f"{code.lower()}_section_titles.json")["sections"]
        texts = _load(f"{code.lower()}_text.json")["sections"]
        olds = old_sections(code)
        for n, body in texts.items():
            title = (titles.get(n) or "").rstrip(".")
            text = re.sub(r"\s+", " ", body)
            if len(text) > MAX_TEXT:
                text = text[:MAX_TEXT].rsplit(" ", 1)[0] + " …"
            lines = [f"{code} Section {n} — {title}" if title else f"{code} Section {n}"]
            if olds.get(n):
                lines.append("Previously: " + ", ".join(olds[n]))
            lines.append(f"OFFICIAL TEXT: {text}")
            if code == "BNS" and schedule.get(n):
                lines.append("CLASSIFICATION (BNSS First Schedule): " + _classification_line(schedule[n]))
            curated = extras.get(f"{code} {n}", {})
            for field in ("KEYWORDS", "TRANSITION NOTE"):
                if curated.get(field):
                    lines.append(f"{field}: {curated[field]}")
            docs.append("\n".join(lines))
            # What the search matches on: a client's plain words find a section
            # by a plain-language card far better than by its legal text
            # (measured on the stress set: curated cards 80% vs official text 68%).
            key = curated.get("_card") or " ".join(
                filter(None, [f"{code} {n}: {title}.", text[:300]]))
            metas.append({"type": f"{code.lower()}_section", "section": f"{code} Section {n}",
                          "title": title, "source": "official", "search_key": key,
                          "curated": bool(curated.get("_card"))})
            ids.append(f"{code.lower()}_{n}")
    for path in sorted((_STATUTES / "special").glob("*.json")):
        d, m, i = special_act_documents(json.loads(path.read_text(encoding="utf-8")))
        docs += d
        metas += m
        ids += i
    return docs, metas, ids


def special_act_documents(act: dict) -> tuple[list[str], list[dict], list[str]]:
    """Special laws (POCSO, NDPS, IT Act …) saved as
    data/legal_corpus/statutes/special/<code>.json: {code, act, sections: {n: {title, text}}}."""
    code, name = act["code"], act["act"]
    docs, metas, ids = [], [], []
    for n, sec in act["sections"].items():
        text = re.sub(r"\s+", " ", sec["text"])
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT].rsplit(" ", 1)[0] + " …"
        docs.append(f"{code} Section {n} — {sec['title']} ({name})\nOFFICIAL TEXT: {text}")
        metas.append({"type": "special_section", "section": f"{code} Section {n}", "title": sec["title"],
                      "act": name, "source": "official", "curated": False,
                      "search_key": f"{name} section {n}: {sec['title']}. {text[:300]}"})
        ids.append(f"{code.lower()}_{n}")
    return docs, metas, ids
