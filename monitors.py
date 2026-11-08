"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Supreme Court Precedent Monitor (Day 3 of Legora teardown)     ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS DOES
──────────────
Legora ships "Monitors" — real-time alerts when EU/UK regulation changes.
This is the Indian equivalent: a lawyer registers the matter types they care
about ("dowry death", "cheating cases", "snatching", "BNS 304"), and every
day the monitor scans the latest Supreme Court rulings against those interest
areas using the same Gemini embeddings + ChromaDB retrieval the rest of
Lex-Indic uses.  New matching rulings show up as a daily digest in the UI.

WHY THIS IS THE WEDGE
─────────────────────
Legora's Monitors cover GDPR, UK Companies Act, EU directives.  They have
nothing for Indian criminal law.  Every Indian advocate needs to track
Supreme Court rulings that affect their active matters — this is something
they currently do by hand, by reading SCC Online or LiveLaw newsletters.
A focused daily digest scoped to YOUR matter areas saves them ~1 hour/day.

DATA SOURCE
───────────
The seeded ruling corpus in this file is hand-curated from publicly reported
landmark and recent SC rulings.  In a real production deployment this would
be replaced with a scheduled scraper of Indian Kanoon's RSS feed, the
National Judicial Data Grid (NJDG), or a paid subscription to SCC Online's
API.  For v1.3 we keep the seed corpus small but real, so the monitor's
matching, digest UI, and email scaffolding can be developed against it.

ARCHITECTURE
────────────
    matters.json  ──┐
                    ├──>  monitor.run_digest()  ──>  digests/YYYY-MM-DD.json
    rulings (seed) ─┘                                      │
                                                           ▼
                                                  /monitors/digest UI
                                                  /monitors/digest.txt (cron)
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import db   # Day-21 dual-backend

# ─── Storage paths ──────────────────────────────────────────────────────────
_DATA_DIR    = Path(__file__).parent / "data" / "monitor_corpus"
_RULINGS_FILE = _DATA_DIR / "sc_rulings.json"
_MATTERS_FILE = Path("outputs") / "monitors" / "matters.json"
_DIGEST_DIR  = Path("outputs") / "monitors" / "digests"


# ════════════════════════════════════════════════════════════════════════════
# Seed ruling corpus — intentionally empty.
# ─────────────────────────────────────────────────────────────────────────────
# The 15 "hand-curated" rulings that used to live here were checked on
# 2026-11-08 against the official Supreme Court record (tools/
# build_sc_citation_index.py): 10 neutral citations belong to unrelated cases
# and 5 do not exist. They were fabricated, so they are gone. Rulings now come
# only from sc_scraper (live feeds, each with a source link).
# ════════════════════════════════════════════════════════════════════════════
SEED_RULINGS: list[dict] = []

def _ensure_seed_corpus():
    """Write the seed corpus to disk on first run."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _RULINGS_FILE.exists():
        _RULINGS_FILE.write_text(
            json.dumps(SEED_RULINGS, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def load_rulings() -> list[dict]:
    """Load all known SC rulings (seed + any added later by a scraper)."""
    _ensure_seed_corpus()
    return json.loads(_RULINGS_FILE.read_text(encoding="utf-8"))


# ════════════════════════════════════════════════════════════════════════════
# Matter registration — what each lawyer wants to be notified about
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class Matter:
    """A topic the lawyer wants to be alerted on."""
    id: str
    label: str                # human-readable name shown in UI
    keywords: list[str]       # plain-text keywords / phrases
    sections: list[str]       # BNS / BNSS / BSA / POCSO section codes
    created_at: str = ""      # ISO timestamp
    owner: str = ""           # firm_id (or user id if no firm); "" = legacy, cron-only


def _load_matters() -> list[Matter]:
    if not _MATTERS_FILE.exists():
        return []
    raw = json.loads(_MATTERS_FILE.read_text(encoding="utf-8"))
    return [Matter(**m) for m in raw]


def _save_matters(matters: list[Matter]):
    _MATTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MATTERS_FILE.write_text(
        json.dumps([asdict(m) for m in matters], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _row_to_matter(row) -> Matter:
    return Matter(
        id=row.id, label=row.label,
        keywords=list(row.keywords or []),
        sections=list(row.sections or []),
        created_at=row.created_at.isoformat(timespec="seconds") if row.created_at else "",
        owner=getattr(row, "owner", "") or "",
    )


def backend() -> str:
    if not db.is_enabled():
        return "json"
    scheme = db.database_url().split(":")[0].lower()
    return "postgres" if "postgres" in scheme else ("sqlite" if "sqlite" in scheme else scheme)


def list_matters(owner: str | None = None) -> list[dict]:
    """Watched matters — only `owner`'s when given (None: all, for cron)."""
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.MonitorMatter).order_by(
                db.MonitorMatter.created_at.asc()
            ).all()
            matters = [_row_to_matter(r) for r in rows]
    else:
        matters = _load_matters()
    return [asdict(m) for m in matters if owner is None or m.owner == owner]


def add_matter(label: str, keywords: list[str], sections: list[str], *,
               owner: str) -> dict:
    """Register a new matter to watch for `owner`. Returns the saved matter."""
    # Random suffix: two adds in the same second must not share an id.
    new_id = f"m_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(3)}"
    now = datetime.now(timezone.utc)
    clean_kw = [k.strip().lower() for k in keywords if k.strip()][:20]
    clean_sec = [s.strip().upper() for s in sections if s.strip()][:20]

    if db.is_enabled():
        with db.session() as s:
            s.add(db.MonitorMatter(
                id=new_id,
                label=label.strip()[:100],
                keywords=clean_kw,
                sections=clean_sec,
                created_at=now,
                owner=owner,
            ))
        return {
            "id": new_id, "label": label.strip()[:100],
            "keywords": clean_kw, "sections": clean_sec,
            "created_at": now.isoformat(timespec="seconds"), "owner": owner,
        }

    matters = _load_matters()
    new = Matter(
        id=new_id,
        label=label.strip()[:100],
        keywords=clean_kw,
        sections=clean_sec,
        created_at=now.isoformat(timespec="seconds"),
        owner=owner,
    )
    matters.append(new)
    _save_matters(matters)
    return asdict(new)


def remove_matter(matter_id: str, owner: str | None = None) -> bool:
    """Delete a watched matter `owner` holds (None: any, operator)."""
    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.MonitorMatter).filter(
                db.MonitorMatter.id == matter_id
            ).first()
            if not row or (owner is not None and (getattr(row, "owner", "") or "") != owner):
                return False
            s.delete(row)
        return True

    matters = _load_matters()
    target = next((m for m in matters if m.id == matter_id), None)
    if not target or (owner is not None and target.owner != owner):
        return False
    _save_matters([m for m in matters if m.id != matter_id])
    return True


# ════════════════════════════════════════════════════════════════════════════
# Matching engine — cheap-and-correct scoring
# ════════════════════════════════════════════════════════════════════════════
def _normalize_section(s: str) -> str:
    """'BNS 304', 'bns 304', 'Section 304' → '304'."""
    s = s.upper().replace("BNS", "").replace("SECTION", "").replace("SEC.", "").replace("S.", "")
    return s.strip()


def _score_ruling(ruling: dict, matter: Matter) -> tuple[float, list[str]]:
    """
    Return (relevance_score 0..1, list_of_reasons).  Two ingredients:
      - section overlap: any of matter.sections in ruling.sections → +0.6
      - keyword overlap: each matter.keyword appearing in title/tags/ratio → +0.1

    Reasons are short strings shown in the UI ("matches BNS 304", "mentions
    'chain snatching'") so the lawyer immediately sees WHY a ruling surfaced.
    """
    reasons: list[str] = []
    score = 0.0

    ruling_sections_norm = {_normalize_section(s) for s in ruling["sections"]}
    for s in matter.sections:
        if _normalize_section(s) in ruling_sections_norm:
            score += 0.6 / max(len(matter.sections), 1)
            reasons.append(f"section match · {s}")

    haystack = " ".join([
        ruling.get("title", ""),
        " ".join(ruling.get("tags", [])),
        ruling.get("ratio", ""),
        ruling.get("practice_impact", ""),
    ]).lower()

    for kw in matter.keywords:
        if not kw:
            continue
        if kw in haystack:
            score += 0.1
            reasons.append(f"keyword · {kw}")

    return min(score, 1.0), reasons


def run_digest(*, since: str | None = None, owner: str | None = None) -> dict:
    """
    Compute the digest for all registered matters.

    Args:
        since: ISO date string. If provided, only rulings dated on or after
               this date are considered. If None, all rulings included.

    Returns:
        {
            'date': '2026-05-16',
            'matters': [
                {'matter': {...}, 'hits': [{'ruling': {...}, 'score': 0.7,
                                            'reasons': ['section match · BNS 304']}, ...]},
                ...
            ],
            'totals': {'matters_with_hits': N, 'total_hits': N},
        }
    """
    matters_raw = list_matters(owner)  # dual-backend aware; owner=None → all
    matters = [Matter(**m) for m in matters_raw]
    rulings = load_rulings()

    if since:
        rulings = [r for r in rulings if r.get("date", "") >= since]

    matter_blocks = []
    total_hits = 0
    matters_with_hits = 0

    for m in matters:
        scored = []
        for r in rulings:
            score, reasons = _score_ruling(r, m)
            if score >= 0.1:  # ignore near-zero matches
                scored.append({"ruling": r, "score": round(score, 3), "reasons": reasons})
        scored.sort(key=lambda x: x["score"], reverse=True)
        if scored:
            matters_with_hits += 1
            total_hits += len(scored)
        matter_blocks.append({"matter": asdict(m), "hits": scored})

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "matters": matter_blocks,
        "totals": {
            "matters_count": len(matters),
            "matters_with_hits": matters_with_hits,
            "total_hits": total_hits,
            "rulings_scanned": len(rulings),
        },
    }


def save_digest(digest: dict) -> Path:
    """Persist a digest to outputs/monitors/digests/YYYY-MM-DD.json."""
    _DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    path = _DIGEST_DIR / f"{digest['date']}.json"
    path.write_text(json.dumps(digest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def format_digest_text(digest: dict) -> str:
    """Plain-text rendering for the cron job to pipe into `mail` or `sendmail`."""
    lines = []
    lines.append("=" * 72)
    lines.append(f"  LEX-INDIC — DAILY SC PRECEDENT DIGEST · {digest['date']}")
    lines.append("=" * 72)
    t = digest["totals"]
    lines.append(
        f"  {t['rulings_scanned']} rulings scanned · "
        f"{t['matters_with_hits']}/{t['matters_count']} matters touched · "
        f"{t['total_hits']} hits total"
    )
    lines.append("")

    for block in digest["matters"]:
        m = block["matter"]
        lines.append("─" * 72)
        lines.append(f"MATTER: {m['label']}")
        if m["sections"]:
            lines.append(f"  Sections: {', '.join(m['sections'])}")
        if m["keywords"]:
            lines.append(f"  Keywords: {', '.join(m['keywords'])}")
        if not block["hits"]:
            lines.append("  → No new rulings today.")
            continue
        for hit in block["hits"]:
            r = hit["ruling"]
            lines.append("")
            lines.append(f"  [{hit['score']:.2f}] {r['title']}  ({r['neutral_citation']})")
            lines.append(f"        {r['court']} · {r['date']}")
            lines.append(f"        Sections: {', '.join(r['sections'])}")
            lines.append(f"        Why: {' · '.join(hit['reasons'])}")
            wrap = lambda text, w=66: [
                text[i:i+w] for i in range(0, len(text), w)
            ]
            lines.append("        Ratio:")
            for ln in wrap(r["ratio"]):
                lines.append(f"          {ln}")
        lines.append("")

    lines.append("=" * 72)
    lines.append("  Reply STOP <matter-id> to unsubscribe from a single matter.")
    lines.append("=" * 72)
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# CLI — meant to be called by cron, e.g.
#   0 7 * * *  cd /opt/lex-indic && python3 -m monitors --save --print
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the SC precedent digest.")
    parser.add_argument("--since", help="Only include rulings dated on/after this YYYY-MM-DD.")
    parser.add_argument("--save", action="store_true", help="Persist the digest to outputs/monitors/digests/.")
    parser.add_argument("--print", action="store_true", help="Print the formatted text digest to stdout.")
    parser.add_argument("--json", action="store_true", help="Print the raw JSON digest to stdout.")
    args = parser.parse_args()

    d = run_digest(since=args.since)
    if args.save:
        path = save_digest(d)
        print(f"Wrote {path}")
    if args.print or (not args.json and not args.save):
        print(format_digest_text(d))
    if args.json:
        print(json.dumps(d, indent=2, ensure_ascii=False))
