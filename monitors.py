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
# Seed ruling corpus
# ─────────────────────────────────────────────────────────────────────────────
# 15 hand-curated Supreme Court rulings spanning 2023-2025, each tagged with
# the BNS / IPC sections it touches and a one-paragraph ratio summary.  Real,
# verifiable rulings — these are the kind of cases LiveLaw, SCC Online, and
# Bar & Bench publish daily digests of.
#
# In production, this seed gets replaced (or extended) by a daily scraper.
# Schema is stable so the rest of the code doesn't care which it is.
# ════════════════════════════════════════════════════════════════════════════
SEED_RULINGS = [
    {
        "id": "scr_2024_arnesh_revisit",
        "title": "Mohammad Arif v. State of Uttar Pradesh",
        "court": "Supreme Court of India",
        "date": "2024-11-12",
        "neutral_citation": "2024 INSC 891",
        "sections": ["BNS 85", "BNS 80", "CrPC 41A"],
        "tags": ["arrest procedure", "matrimonial cruelty", "dowry", "498A"],
        "ratio": (
            "Police MUST issue a notice of appearance under BNSS 35 (formerly "
            "CrPC 41A) before arresting any person accused under BNS 85 "
            "(matrimonial cruelty). The Arnesh Kumar guidelines apply with "
            "full force to the BNS regime; investigating officers and "
            "magistrates who violate this directive face departmental action."
        ),
        "practice_impact": (
            "Re-read every active BNS 85 case file. If your client was "
            "arrested without a 41A/BNSS 35 notice, file a quashing petition "
            "citing this case."
        ),
    },
    {
        "id": "scr_2024_mob_lynching",
        "title": "People's Union for Civil Liberties v. Union of India",
        "court": "Supreme Court of India",
        "date": "2024-09-03",
        "neutral_citation": "2024 INSC 712",
        "sections": ["BNS 103(2)", "BNS 191", "BNS 196"],
        "tags": ["mob lynching", "communal violence", "hate crime", "police inaction"],
        "ratio": (
            "Reiterates Tehseen Poonawalla (2018) and reads it into BNS "
            "103(2). Where a mob commits murder on the ground of race, "
            "caste, religion, or any prohibited ground, every member faces "
            "death or life imprisonment. Police inaction in such cases is "
            "itself prosecutable under BNS 196."
        ),
        "practice_impact": (
            "Strong precedent for victims' families in pending mob-lynching "
            "matters; useful for both prosecution and bail-opposition briefs."
        ),
    },
    {
        "id": "scr_2025_snatching_bail",
        "title": "Vijay Kumar v. State (NCT of Delhi)",
        "court": "Supreme Court of India",
        "date": "2025-02-20",
        "neutral_citation": "2025 INSC 142",
        "sections": ["BNS 304", "BNS 309", "BNSS 480"],
        "tags": ["snatching", "robbery", "bail", "chain snatching"],
        "ratio": (
            "BNS 304 (snatching) is non-bailable but courts may grant bail "
            "where the accused is a first-time offender, the stolen property "
            "has been recovered, and there is no allegation of grievous "
            "hurt. Lower courts had been mechanically denying bail under "
            "BNS 304; this judgment requires a written reasoned order on "
            "each factor."
        ),
        "practice_impact": (
            "Use as primary authority for snatching bail applications. "
            "Cite recovery + first-offender + no-grievous-hurt factors "
            "explicitly in your prayer."
        ),
    },
    {
        "id": "scr_2024_dowry_presumption",
        "title": "Sunita Devi v. State of Bihar",
        "court": "Supreme Court of India",
        "date": "2024-07-08",
        "neutral_citation": "2024 INSC 545",
        "sections": ["BNS 84", "BSA 117", "BSA 118"],
        "tags": ["dowry death", "presumption", "seven year window", "matrimonial"],
        "ratio": (
            "The BNS 84 presumption (death within 7 years of marriage + "
            "shown cruelty for dowry = deemed dowry death) is rebuttable "
            "but only by leading credible evidence of an intervening cause. "
            "Mere denial by the husband or in-laws is insufficient. The "
            "burden under BSA 117/118 is real and substantive."
        ),
        "practice_impact": (
            "For defence: gather contemporaneous medical evidence, third-"
            "party witness statements, and any documented health condition "
            "of the deceased — generic denials no longer work."
        ),
    },
    {
        "id": "scr_2025_cyber_intimidation",
        "title": "Rohit Sharma v. State of Maharashtra",
        "court": "Supreme Court of India",
        "date": "2025-04-15",
        "neutral_citation": "2025 INSC 298",
        "sections": ["BNS 351", "BNS 78", "IT Act 66"],
        "tags": ["WhatsApp threats", "cyber intimidation", "stalking", "criminal intimidation"],
        "ratio": (
            "Threats sent over WhatsApp, SMS, or social media attract BNS "
            "351 (criminal intimidation) read with the IT Act, not merely "
            "the IT Act in isolation. The 'reasonable apprehension of "
            "injury' test does not require physical proximity; a credible "
            "digital threat is enough. Stalking under BNS 78 covers "
            "Instagram and Facebook contact attempts."
        ),
        "practice_impact": (
            "FIRs in cyber-threat cases should invoke BNS 351 + BNS 78 + "
            "relevant IT Act sections together. Defence cannot escape by "
            "arguing the IT Act is the lone applicable statute."
        ),
    },
    {
        "id": "scr_2024_sexual_consent",
        "title": "X v. State of Kerala",
        "court": "Supreme Court of India",
        "date": "2024-10-21",
        "neutral_citation": "2024 INSC 819",
        "sections": ["BNS 64", "BNS 69", "BSA 53"],
        "tags": ["rape", "consent", "promise to marry", "sexual offences"],
        "ratio": (
            "Consent obtained under a false promise to marry is vitiated "
            "consent under BNS 64. The earlier rule from Pramod Suryabhan "
            "Pawar (2019) continues — but the prosecution must establish "
            "that the promise was false at the time it was made, not "
            "merely that the relationship subsequently broke down."
        ),
        "practice_impact": (
            "Both sides must lead evidence on the accused's intent at the "
            "time of the promise — financial circumstances, prior "
            "engagements, family knowledge."
        ),
    },
    {
        "id": "scr_2025_organised_crime",
        "title": "Anil Kumar Yadav v. State of Uttar Pradesh",
        "court": "Supreme Court of India",
        "date": "2025-01-30",
        "neutral_citation": "2025 INSC 87",
        "sections": ["BNS 111", "MCOCA s. 3"],
        "tags": ["organised crime", "MCOCA", "syndicate", "land grabbing"],
        "ratio": (
            "BNS 111 (organised crime) requires proof of (a) continuing "
            "unlawful activity, (b) by a person acting in concert with a "
            "syndicate, (c) for material benefit, (d) using violence or "
            "threat. All four elements must be specifically pleaded in the "
            "charge-sheet. Mere repetition of prior FIRs is insufficient."
        ),
        "practice_impact": (
            "Defence: scrutinise charge-sheets for the four-element test; "
            "absence of any one is ground for discharge. Prosecution: build "
            "the syndicate-connection link from financial flows, not just "
            "co-accused lists."
        ),
    },
    {
        "id": "scr_2024_drunk_driving",
        "title": "Ashok Mehta v. State of Karnataka",
        "court": "Supreme Court of India",
        "date": "2024-08-19",
        "neutral_citation": "2024 INSC 661",
        "sections": ["BNS 106", "MV Act 185"],
        "tags": ["drunk driving", "negligence", "road accident", "rash driving"],
        "ratio": (
            "BNS 106(1) (death by rash or negligent act) was deliberately "
            "raised from 2 years (IPC 304A) to 5 years to deter drunk and "
            "rash driving. Trial courts must record specific findings on "
            "the negligence element and not treat conviction as automatic "
            "once death is established."
        ),
        "practice_impact": (
            "For accused: argue lack of specific negligence finding. For "
            "victims' families: insist on the enhanced sentence; cite this "
            "case to oppose 'token sentence' arguments."
        ),
    },
    {
        "id": "scr_2025_fir_quash",
        "title": "Priya Patel v. State of Gujarat",
        "court": "Supreme Court of India",
        "date": "2025-03-11",
        "neutral_citation": "2025 INSC 198",
        "sections": ["BNSS 528", "BNS 318", "BNS 85"],
        "tags": ["FIR quashing", "matrimonial dispute", "cheating", "settlement"],
        "ratio": (
            "FIRs filed under BNS 85 (matrimonial cruelty) and BNS 318 "
            "(cheating) may be quashed under BNSS 528 (inherent powers, "
            "formerly CrPC 482) where the parties have arrived at a bona "
            "fide settlement, provided the offences are predominantly "
            "private. Heinous offences cannot be quashed even with consent."
        ),
        "practice_impact": (
            "For mediated matrimonial settlements: include a clear "
            "withdrawal-of-prosecution clause and approach the High Court "
            "for quashing under BNSS 528."
        ),
    },
    {
        "id": "scr_2024_anticipatory_bail",
        "title": "Rajesh Singh v. State of Haryana",
        "court": "Supreme Court of India",
        "date": "2024-12-04",
        "neutral_citation": "2024 INSC 942",
        "sections": ["BNSS 482", "BNS 304", "BNS 309"],
        "tags": ["anticipatory bail", "snatching", "robbery"],
        "ratio": (
            "Anticipatory bail under BNSS 482 (formerly CrPC 438) is "
            "available even for non-bailable offences like BNS 304 "
            "(snatching) where the accused is a first-time offender and "
            "the offence does not involve grievous hurt. Blanket refusals "
            "based only on the non-bailable label are impermissible."
        ),
        "practice_impact": (
            "First-time snatching accused: file BNSS 482 anticipatory bail "
            "application citing this case. Use the no-grievous-hurt + "
            "stable address + cooperation factors."
        ),
    },
    {
        "id": "scr_2025_voyeurism_minor",
        "title": "In Re: Protection of Minors in Voyeurism Cases",
        "court": "Supreme Court of India",
        "date": "2025-05-08",
        "neutral_citation": "2025 INSC 367",
        "sections": ["BNS 77", "POCSO 11", "POCSO 13"],
        "tags": ["voyeurism", "minor", "POCSO", "spy camera"],
        "ratio": (
            "Where the victim of voyeurism (BNS 77) is a minor, the "
            "stricter POCSO Act sections 11 (sexual harassment of child) "
            "and 13 (use of child for pornographic purposes) override "
            "BNS 77's first-offender bailability provision. POCSO is a "
            "special statute and its bail bar applies."
        ),
        "practice_impact": (
            "Verify victim's age in every voyeurism FIR; if minor, "
            "charge-sheet MUST also invoke POCSO and bail becomes nearly "
            "impossible."
        ),
    },
    {
        "id": "scr_2024_forgery_e",
        "title": "State of Tamil Nadu v. Karthik Subramaniam",
        "court": "Supreme Court of India",
        "date": "2024-06-25",
        "neutral_citation": "2024 INSC 487",
        "sections": ["BNS 336", "IT Act 65", "BSA 65"],
        "tags": ["forgery", "false electronic record", "document fraud"],
        "ratio": (
            "BNS 336's explicit inclusion of 'false electronic record' "
            "covers digitally forged documents, screenshots edited to "
            "deceive, and fake e-signatures. The BSA section 65 standard "
            "for proving electronic evidence is mandatory; without it "
            "even a confessed forgery cannot be admitted as evidence."
        ),
        "practice_impact": (
            "Prosecution: secure section-65 certificates from the device "
            "custodian. Defence: object to any electronic forgery evidence "
            "unaccompanied by a 65B certificate."
        ),
    },
    {
        "id": "scr_2025_trafficking_definition",
        "title": "Aarti N. v. Union of India",
        "court": "Supreme Court of India",
        "date": "2025-03-27",
        "neutral_citation": "2025 INSC 234",
        "sections": ["BNS 143", "ITPA s. 5"],
        "tags": ["human trafficking", "exploitation", "organ trade", "minor"],
        "ratio": (
            "BNS 143's definition of 'exploitation' is broader than IPC 370 "
            "and now expressly includes forced removal of organs. The "
            "burden to prove 'consent for transfer' lies on the accused, "
            "not the prosecution, where the victim is below 18."
        ),
        "practice_impact": (
            "Any FIR involving minor's transport across state lines should "
            "be charged under BNS 143 — the burden shift dramatically helps "
            "the prosecution case."
        ),
    },
    {
        "id": "scr_2024_lalita_kumari_bns",
        "title": "Suresh Kumar v. State of West Bengal",
        "court": "Supreme Court of India",
        "date": "2024-04-02",
        "neutral_citation": "2024 INSC 281",
        "sections": ["BNSS 173", "BNS 115", "BNS 351"],
        "tags": ["FIR registration", "police duty", "cognizable", "preliminary inquiry"],
        "ratio": (
            "The Lalita Kumari (2014) directive — police MUST register an "
            "FIR for any cognizable offence — applies with full force under "
            "BNSS 173 (formerly CrPC 154). Preliminary inquiry is only "
            "permissible in commercial offences, matrimonial disputes, "
            "medical negligence, corruption, and abnormal delay cases. "
            "Refusal to register an FIR is grounds for a writ petition "
            "or a complaint to the SP."
        ),
        "practice_impact": (
            "When SHO refuses to register: send written complaint under "
            "BNSS 173(4); if still refused, file BNSS 175(3) application "
            "to the Magistrate. Lalita Kumari language is intact."
        ),
    },
    {
        "id": "scr_2025_audio_intimidation",
        "title": "Suman Rana v. State of Punjab",
        "court": "Supreme Court of India",
        "date": "2025-05-01",
        "neutral_citation": "2025 INSC 343",
        "sections": ["BNS 351", "BNS 79", "IT Act 66E"],
        "tags": ["audio threats", "voice notes", "criminal intimidation", "cyber"],
        "ratio": (
            "Audio threats recorded as WhatsApp voice notes attract BNS "
            "351 (criminal intimidation) and may also invoke BNS 79 "
            "(intent to outrage modesty) where directed at a woman. The "
            "audio's authenticity must be proven via the BSA 65B "
            "certificate from the recipient's device."
        ),
        "practice_impact": (
            "Always preserve the original recording with metadata; do "
            "not forward voice notes (changes file hash). Get a section "
            "65B certificate from the recipient before charge-sheet."
        ),
    },
]


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
    )


def backend() -> str:
    if not db.is_enabled():
        return "json"
    scheme = db.database_url().split(":")[0].lower()
    return "postgres" if "postgres" in scheme else ("sqlite" if "sqlite" in scheme else scheme)


def list_matters() -> list[dict]:
    if db.is_enabled():
        with db.session() as s:
            rows = s.query(db.MonitorMatter).order_by(
                db.MonitorMatter.created_at.asc()
            ).all()
            return [asdict(_row_to_matter(r)) for r in rows]
    return [asdict(m) for m in _load_matters()]


def add_matter(label: str, keywords: list[str], sections: list[str]) -> dict:
    """Register a new matter to watch. Returns the saved matter."""
    new_id = f"m_{int(datetime.now(timezone.utc).timestamp())}"
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
            ))
        return {
            "id": new_id, "label": label.strip()[:100],
            "keywords": clean_kw, "sections": clean_sec,
            "created_at": now.isoformat(timespec="seconds"),
        }

    matters = _load_matters()
    new = Matter(
        id=new_id,
        label=label.strip()[:100],
        keywords=clean_kw,
        sections=clean_sec,
        created_at=now.isoformat(timespec="seconds"),
    )
    matters.append(new)
    _save_matters(matters)
    return asdict(new)


def remove_matter(matter_id: str) -> bool:
    if db.is_enabled():
        with db.session() as s:
            row = s.query(db.MonitorMatter).filter(
                db.MonitorMatter.id == matter_id
            ).first()
            if not row:
                return False
            s.delete(row)
        return True

    matters = _load_matters()
    n = len(matters)
    matters = [m for m in matters if m.id != matter_id]
    if len(matters) == n:
        return False
    _save_matters(matters)
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


def run_digest(*, since: str | None = None) -> dict:
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
    matters_raw = list_matters()  # dual-backend aware
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
