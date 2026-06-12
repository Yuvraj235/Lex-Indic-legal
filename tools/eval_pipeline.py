#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Full-pipeline answer-quality eval (Day 27)                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS DOES
──────────────
tools/eval_model.py grades the CONVERTER (one IPC→BNS number, one right answer).
This grades the actual PRODUCT — the six-section /analyze output a lawyer reads —
against a fixed set of client scenarios.  It scores four things, deterministic
and reproducible:

  1. Completeness     — all six sections present and non-trivial.
  2. Citation cover   — the BNS sections a correct answer MUST cite are present.
  3. Concept mentions — required anchors (e.g. "Arnesh Kumar", "dowry") appear.
  4. GROUNDING        — every BNS section the answer cites exists in our KB.
                        A cited section that isn't in the KB is, by definition,
                        ungrounded (hallucinated) — this is the core product risk.

An optional --judge layer asks Groq for a holistic 1-5 grounding/quality score.

WHY THIS MATTERS
────────────────
Converter accuracy covers one IPC→BNS number. This covers the whole analysis a
lawyer reads — complete, correctly cited, and grounded (it never invents a
section across the fixed scenarios).

USAGE  (the app must be running — it keeps the KB warm)
  python3 app.py &                       # or your deployed URL
  python3 tools/eval_pipeline.py                       # grade vs localhost:8080
  python3 tools/eval_pipeline.py --judge               # + Groq holistic score
  python3 tools/eval_pipeline.py --base-url https://lex-indic.in

OUTPUT  data/finetune/pipeline_eval_report.{md,json}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import data.bns_knowledge_base as bns_kb

OUT_DIR = ROOT / "data" / "finetune"
MAPPING_PATH = ROOT / "data" / "legal_corpus" / "ipc_bns_mapping.json"

SECTION_KEYS = [f"section_{i}" for i in range(1, 7)]   # the six /analyze sections

# Fixed gold scenarios. must_cite = BNS section numbers a correct answer should
# cite (all present in the KB, so a grounded answer scores full marks).
GOLD_SCENARIOS = [
    {
        "id": "dowry_cruelty",
        "story": ("My client is a 27-year-old woman. Since her marriage two years "
                  "ago, her husband and mother-in-law have repeatedly demanded a "
                  "car and cash as dowry and beaten her when she refused. She wants "
                  "to file a case."),
        "must_cite": ["85"],                       # BNS 85 — cruelty (ex-IPC 498A)
        "must_mention": ["dowry", "cruelty"],
    },
    {
        "id": "chain_snatching_robbery",
        "story": ("My client was walking home when two men on a motorcycle snatched "
                  "her gold chain at knife-point and sped away."),
        "must_cite": ["304", "309"],               # snatching / robbery
        "must_mention": ["robbery"],
    },
    {
        "id": "cheating_advance",
        "story": ("My client paid Rs 5 lakh to a man who promised to deliver "
                  "construction material. He took the money, delivered nothing, and "
                  "stopped answering calls."),
        "must_cite": ["318"],                      # BNS 318 — cheating
        "must_mention": ["cheating"],
    },
    {
        "id": "arrest_safeguard_respondent",
        "story": ("Police are threatening to arrest my client over a matrimonial "
                  "cruelty complaint filed by his wife. He has received no notice. "
                  "What are his rights before arrest?"),
        "must_cite": ["85"],
        "must_mention": ["Arnesh Kumar", "notice"],  # arrest safeguards
    },
]

_BNS_CITE_RE = re.compile(r"BNS\s*(?:Section\s*)?(\d{1,4}[A-Z]?(?:\(\d+\))?)", re.I)
_SEC_NUM_RE = re.compile(r"(\d{1,4}[A-Z]?(?:\(\d+\))?)")


# ──────────────────────────────────────────────────────────────────────────────
# Pure scoring (unit-tested) — no network
# ──────────────────────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return s.upper().replace(" ", "")


def known_bns_sections() -> set[str]:
    """Every BNS section number our KB / mapping vouches for. A citation outside
    this set is ungrounded relative to what /analyze was actually given."""
    nums: set[str] = set()
    for s in bns_kb.BNS_SECTIONS:
        m = _SEC_NUM_RE.search(s.get("section", ""))
        if m:
            nums.add(_norm(m.group(1)))
    try:
        mp = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
        for v in mp.values():
            m = _SEC_NUM_RE.search(v.get("bns", ""))
            if m:
                nums.add(_norm(m.group(1)))
    except (OSError, json.JSONDecodeError):
        pass
    return nums


def cited_sections(text: str) -> set[str]:
    return {_norm(n) for n in _BNS_CITE_RE.findall(text or "")}


def count_sections_present(sections: dict, min_len: int = 40) -> int:
    return sum(1 for k in SECTION_KEYS if len((sections.get(k) or "").strip()) >= min_len)


def grade_analysis(sections: dict, scenario: dict, known: set[str] | None = None) -> dict:
    """Deterministic rubric over one /analyze output (a dict of six sections)."""
    known = known if known is not None else known_bns_sections()
    combined = "\n".join((sections.get(k) or "") for k in SECTION_KEYS)
    low = combined.lower()
    cites = cited_sections(combined)
    must = [_norm(x) for x in scenario.get("must_cite", [])]
    mentions = scenario.get("must_mention", [])
    return {
        "scenario": scenario["id"],
        "sections_present": count_sections_present(sections),
        "citations": [sum(c in cites for c in must), len(must)],
        "mentions": [sum(w.lower() in low for w in mentions), len(mentions)],
        "ungrounded_citations": sorted(c for c in cites if c not in known),
        "missing_citations": [c for c in must if c not in cites],
        "missing_mentions": [w for w in mentions if w.lower() not in low],
    }


def composite(g: dict) -> float:
    """0-1 score: mean of the present-ratios, penalised for ungrounded citations."""
    parts = [g["sections_present"] / 6]
    if g["citations"][1]:
        parts.append(g["citations"][0] / g["citations"][1])
    if g["mentions"][1]:
        parts.append(g["mentions"][0] / g["mentions"][1])
    base = sum(parts) / len(parts)
    penalty = min(0.3, 0.1 * len(g["ungrounded_citations"]))
    return round(max(0.0, base - penalty), 3)


# ──────────────────────────────────────────────────────────────────────────────
# Network: fetch an analysis + optional LLM judge
# ──────────────────────────────────────────────────────────────────────────────
def fetch_analysis(base_url: str, story: str, language: str = "en") -> dict:
    body = json.dumps({"client_story": story, "language": language}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/analyze", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        payload = json.loads(r.read().decode("utf-8"))
    return payload.get("sections") or {}


def llm_judge(combined: str, scenario: dict) -> dict:
    from main import configure_groq
    client = configure_groq()
    rubric = ("You grade Indian criminal-law analyses. Rate 1-5 how well the "
              "analysis fits the client's situation: correct BNS sections, grounded "
              "(invents nothing), complete, professional. "
              "Return JSON {\"score\": <1-5>, \"reason\": \"...\"}.")
    msg = f"Client situation:\n{scenario['story']}\n\nAnalysis:\n{combined[:6000]}"
    comp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": rubric},
                  {"role": "user", "content": msg}],
        temperature=0.0, max_tokens=300,
        response_format={"type": "json_object"})
    try:
        return json.loads(comp.choices[0].message.content)
    except Exception:  # noqa: BLE001
        return {"score": None, "reason": "judge parse error"}


# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Grade the six-section /analyze output.")
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--judge", action="store_true", help="Add a Groq holistic 1-5 score.")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    scenarios = GOLD_SCENARIOS[:args.limit] if args.limit else GOLD_SCENARIOS
    known = known_bns_sections()
    print(f"Grading {len(scenarios)} scenario(s) against {args.base_url} …\n")

    results = []
    for sc in scenarios:
        try:
            sections = fetch_analysis(args.base_url, sc["story"])
        except Exception as e:  # noqa: BLE001
            print(f"  ! {sc['id']}: /analyze failed: {e}")
            continue
        g = grade_analysis(sections, sc, known)
        g["composite"] = composite(g)
        if args.judge:
            combined = "\n".join((sections.get(k) or "") for k in SECTION_KEYS)
            g["judge"] = llm_judge(combined, sc)
        results.append(g)
        jw = f"  judge {g['judge'].get('score')}" if args.judge else ""
        print(f"  {sc['id']:32s} composite {g['composite']:.2f}  "
              f"sections {g['sections_present']}/6  "
              f"cite {g['citations'][0]}/{g['citations'][1]}  "
              f"ungrounded {len(g['ungrounded_citations'])}{jw}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pipeline_eval_report.json").write_text(
        json.dumps({"results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Lex-Indic — full-pipeline answer eval", "",
             "| Scenario | Composite | Sections | Citations | Mentions | Ungrounded |",
             "|----------|----------:|---------:|----------:|---------:|-----------:|"]
    for g in results:
        lines.append(
            f"| `{g['scenario']}` | **{g['composite']:.2f}** | {g['sections_present']}/6 "
            f"| {g['citations'][0]}/{g['citations'][1]} | {g['mentions'][0]}/{g['mentions'][1]} "
            f"| {len(g['ungrounded_citations'])} |")
    if results:
        avg = sum(g["composite"] for g in results) / len(results)
        lines += ["", f"**Mean composite: {avg:.2f}** across {len(results)} scenarios. "
                  "Ungrounded = BNS sections cited that are not in the knowledge base "
                  "(hallucinated). Target: 0."]
    (OUT_DIR / "pipeline_eval_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✓ wrote {OUT_DIR/'pipeline_eval_report.md'}")


if __name__ == "__main__":
    main()
