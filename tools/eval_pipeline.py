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
import time
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

# Grounding/citation extraction lives in the runtime verifier (verifier.py) —
# the same functions run inside /analyze, so eval and serving can never drift.
from verifier import (cited_sections, known_bns_sections,  # noqa: F401 (re-exported)
                      mapping_mismatches, precedent_check)

OUT_DIR = ROOT / "data" / "finetune"

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
    # ── Hard cases (added after the 2026-07-20 stress test): facts written the
    # way a client talks, no legal keywords, traps between look-alike sections.
    {
        "id": "snatching_not_robbery",
        "story": ("My client, a college student, was riding pillion on her friend's "
                  "scooter in Pune. When they slowed at a speed-breaker, a man on a "
                  "motorcycle came from behind, grabbed the mobile phone she was "
                  "holding in her hand, and sped away instantly. Nobody was "
                  "threatened or hurt, no weapon was shown, and the whole thing was "
                  "over in two seconds. The phone cost Rs 80,000 and had her "
                  "research data. CCTV of the road shows the incident."),
        "must_cite": ["304"],              # snatching — NOT robbery (no force/threat)
        "must_mention": ["snatching"],
    },
    {
        "id": "hit_and_run_negligence",
        "story": ("Last Sunday around 11 pm my client's father, aged 61, was walking "
                  "back from the temple on the service road. A speeding truck hit him "
                  "and he died on the spot. The driver did not stop, did not call "
                  "anyone, and drove away in the dark. Police traced the truck two "
                  "days later from a toll camera. The driver says he did not realise "
                  "he had hit a person. There was no enmity between them."),
        "must_cite": ["106"],              # death by negligence — NOT murder
        "must_mention": ["negligence"],
    },
    {
        "id": "treasurer_breach_of_trust",
        "story": ("My client's housing society elected a treasurer three years ago. "
                  "Every month he collected Rs 2.5 lakh in maintenance money from 90 "
                  "flats into the society account, to which only he had access. An "
                  "audit last month found that over two years he quietly moved Rs 31 "
                  "lakh into fixed deposits in his own name and his wife's name. When "
                  "confronted he said it was a 'temporary arrangement'. He has now "
                  "stopped attending meetings."),
        "must_cite": ["316"],              # entrusted first → breach of trust, not cheating
        "must_mention": ["breach of trust"],
    },
    {
        "id": "mob_lynching_group_murder",
        "story": ("My client's brother, a migrant scrap dealer, was passing through a "
                  "village in the evening. A message had been circulating on WhatsApp "
                  "that child-lifters were roaming the area. A crowd of more than ten "
                  "villagers surrounded him, called him a child-lifter, tied him to a "
                  "pole and beat him with sticks for an hour. He died in hospital. "
                  "Videos from phones of bystanders identify at least seven "
                  "attackers. The family wants the strictest possible case."),
        "must_cite": ["103"],              # 103(2) murder by group / mob lynching
        "must_mention": ["lynching"],
    },
    {
        "id": "fake_army_qr_scam",
        "story": ("My client listed his almirah for sale on a marketplace app. A "
                  "buyer contacted him saying he was an army jawan being posted out, "
                  "sent a photo of an ID card, and insisted on paying in advance "
                  "through a QR code. He sent a QR and said 'scan this and you will "
                  "receive the money'. My client scanned it three times and Rs 47,000 "
                  "was debited from his account instead. The number is now switched "
                  "off. He has screenshots of the entire chat."),
        "must_cite": ["318"],              # cheating
        "must_mention": ["cheating"],
    },
    {
        "id": "acid_attack_mapping_layer",
        "story": ("A man my client had refused to marry stopped her outside her "
                  "coaching class and threw a corrosive liquid on her face from a "
                  "steel container. She has permanent burn scars on her face and neck "
                  "and partial loss of vision in one eye. Doctors say two more "
                  "surgeries are needed. The man had threatened her twice before on "
                  "the phone, saying he would 'ruin her face'. She wants him punished "
                  "as severely as the law allows."),
        "must_cite": ["124"],              # acid attack — reached via IPC 326A mapping
        "must_mention": ["acid"],
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Pure scoring (unit-tested) — no network
# ──────────────────────────────────────────────────────────────────────────────
def _save_output(scenario_id: str, base_url: str, sections: dict) -> None:
    """Raw answers go to outputs/eval/ (gitignored) so a run can be re-graded
    after the rubric changes without paying for the model again."""
    out = ROOT / "outputs" / "eval" / "pipeline_outputs.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps({"scenario": scenario_id, "base_url": base_url,
                            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "sections": sections}, ensure_ascii=False) + "\n")


def _base(section: str) -> str:
    return re.sub(r"\(.*\)$", "", section)


def _norm(s: str) -> str:
    return s.upper().replace(" ", "")


def count_sections_present(sections: dict, min_len: int = 40) -> int:
    return sum(1 for k in SECTION_KEYS if len((sections.get(k) or "").strip()) >= min_len)


def grade_analysis(sections: dict, scenario: dict, known: set[str] | None = None) -> dict:
    """Deterministic rubric over one /analyze output (a dict of six sections)."""
    known = known if known is not None else known_bns_sections()
    combined = "\n".join((sections.get(k) or "") for k in SECTION_KEYS)
    low = combined.lower()
    cites = cited_sections(combined)
    # Compare on base numbers, as the runtime verifier does: "BNS 103(2)"
    # (mob lynching) cites section 103 — it is neither missing nor invented.
    bases = {_base(c) for c in cites}
    must = [_norm(x) for x in scenario.get("must_cite", [])]
    mentions = scenario.get("must_mention", [])
    return {
        "scenario": scenario["id"],
        "sections_present": count_sections_present(sections),
        "citations": [sum(_base(c) in bases for c in must), len(must)],
        "mentions": [sum(w.lower() in low for w in mentions), len(mentions)],
        "ungrounded_citations": sorted(c for c in cites if _base(c) not in known),
        "missing_citations": [c for c in must if _base(c) not in bases],
        "missing_mentions": [w for w in mentions if w.lower() not in low],
        # Wrong IPC→BNS pairings and case law that isn't verified / good law —
        # the same checks the runtime verifier applies.
        "wrong_pairings": [f"IPC {m['ipc']}→BNS {m['cited_bns']}" for m in mapping_mismatches(combined)],
        "bad_precedents": _bad_precedents(combined),
    }


def _bad_precedents(text: str) -> list[str]:
    p = precedent_check(text)
    return (p["unverified"] + [b["case"] for b in p["bad_law"]]
            + [w["case"] + " (wrong report)" for w in p["wrong_citation"]])


def composite(g: dict) -> float:
    """0-1 score: mean of the present-ratios, penalised for ungrounded citations."""
    parts = [g["sections_present"] / 6]
    if g["citations"][1]:
        parts.append(g["citations"][0] / g["citations"][1])
    if g["mentions"][1]:
        parts.append(g["mentions"][0] / g["mentions"][1])
    base = sum(parts) / len(parts)
    errors = (len(g["ungrounded_citations"]) + len(g.get("wrong_pairings", []))
              + len(g.get("bad_precedents", [])))
    penalty = min(0.3, 0.1 * errors)
    return round(max(0.0, base - penalty), 3)


# ──────────────────────────────────────────────────────────────────────────────
# Network: fetch an analysis + optional LLM judge
# ──────────────────────────────────────────────────────────────────────────────
def fetch_analysis(base_url: str, story: str, language: str = "en") -> dict:
    """The six sections of one /analyze answer (HTML entities decoded)."""
    body = json.dumps({"client_story": story, "language": language}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/analyze", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        payload = json.loads(r.read().decode("utf-8"))
    import html
    return {k: html.unescape(v) if isinstance(v, str) else v
            for k, v in (payload.get("sections") or {}).items()}


def llm_judge(combined: str, scenario: dict) -> dict:
    from main import configure_groq
    client = configure_groq()
    rubric = ("You grade Indian criminal-law analyses. Rate 1-5 how well the "
              "analysis fits the client's situation: correct BNS sections, grounded "
              "(invents nothing), complete, professional. "
              "Return JSON {\"score\": <1-5>, \"reason\": \"...\"}.")
    msg = f"Client situation:\n{scenario['story']}\n\nAnalysis:\n{combined[:6000]}"
    import llm_provider
    text = llm_provider.groq_complete(
        client,
        [{"role": "system", "content": rubric},
         {"role": "user", "content": msg}],
        temperature=0.0, max_tokens=300, response_format={"type": "json_object"})
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return {"score": None, "reason": "judge parse error"}


# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Grade the six-section /analyze output.")
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--judge", action="store_true", help="Add a Groq holistic 1-5 score.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--resume", action="store_true",
                    help="Skip scenarios already in pipeline_eval_report.json "
                         "(lets a run finish across rate-limit interruptions / days).")
    ap.add_argument("--retries", type=int, default=1,
                    help="Retries per scenario on failure, with backoff (default 1).")
    ap.add_argument("--retry-wait", type=int, default=1500,
                    help="Seconds to wait between retries (default 1500 = 25 min, "
                         "sized for Groq's rolling free-tier window).")
    ap.add_argument("--out-dir", default=str(OUT_DIR),
                    help="Where to write pipeline_eval_report.{json,md} (default data/finetune).")
    args = ap.parse_args()

    scenarios = GOLD_SCENARIOS[:args.limit] if args.limit else GOLD_SCENARIOS
    known = known_bns_sections()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "pipeline_eval_report.json"

    # Resume: keep prior good results, only run the scenarios still missing.
    results = []
    done_ids: set[str] = set()
    if args.resume and report_path.exists():
        try:
            results = json.loads(report_path.read_text(encoding="utf-8")).get("results", [])
            done_ids = {g["scenario"] for g in results}
            print(f"Resuming — {len(done_ids)} scenario(s) already graded.\n")
        except (OSError, json.JSONDecodeError):
            results, done_ids = [], set()

    def _write_report():
        report_path.write_text(
            json.dumps({"results": results}, indent=2, ensure_ascii=False), encoding="utf-8")

    todo = [sc for sc in scenarios if sc["id"] not in done_ids]
    print(f"Grading {len(todo)} scenario(s) against {args.base_url} …\n")

    for sc in todo:
        sections = None
        for attempt in range(1, args.retries + 1):
            try:
                sections = fetch_analysis(args.base_url, sc["story"])
                break
            except Exception as e:  # noqa: BLE001
                print(f"  ! {sc['id']}: attempt {attempt}/{args.retries} failed: {e}")
                if attempt < args.retries:
                    time.sleep(args.retry_wait)
        if sections is None:
            print(f"  ! {sc['id']}: giving up (will retry on next --resume run)")
            continue
        g = grade_analysis(sections, sc, known)
        g["composite"] = composite(g)
        _save_output(sc["id"], args.base_url, sections)
        if args.judge:
            combined = "\n".join((sections.get(k) or "") for k in SECTION_KEYS)
            g["judge"] = llm_judge(combined, sc)
        results.append(g)
        _write_report()   # checkpoint after every scenario — never lose progress
        jw = f"  judge {g['judge'].get('score')}" if args.judge else ""
        print(f"  {sc['id']:32s} composite {g['composite']:.2f}  "
              f"sections {g['sections_present']}/6  "
              f"cite {g['citations'][0]}/{g['citations'][1]}  "
              f"ungrounded {len(g['ungrounded_citations'])}  "
              f"wrong-pair {len(g['wrong_pairings'])}  bad-case {len(g['bad_precedents'])}{jw}")

    _write_report()
    lines = ["# Lex-Indic — full-pipeline answer eval", "",
             "| Scenario | Composite | Sections | Citations | Mentions | Ungrounded | Wrong pair | Bad case |",
             "|----------|----------:|---------:|----------:|---------:|-----------:|-----------:|---------:|"]
    for g in results:
        lines.append(
            f"| `{g['scenario']}` | **{g['composite']:.2f}** | {g['sections_present']}/6 "
            f"| {g['citations'][0]}/{g['citations'][1]} | {g['mentions'][0]}/{g['mentions'][1]} "
            f"| {len(g['ungrounded_citations'])} | {len(g.get('wrong_pairings', []))} "
            f"| {len(g.get('bad_precedents', []))} |")
    if results:
        avg = sum(g["composite"] for g in results) / len(results)
        lines += ["", f"**Mean composite: {avg:.2f}** across {len(results)} scenarios. "
                  "Ungrounded = BNS sections cited that are not in the knowledge base "
                  "(hallucinated). Wrong pair = IPC→BNS pairing contradicting the govt "
                  "concordance. Bad case = case law not in the verified judgments, "
                  "overruled, or wrongly reported. Target for all three: 0."]
    (out_dir / "pipeline_eval_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✓ wrote {out_dir/'pipeline_eval_report.md'}")


if __name__ == "__main__":
    main()
