#!/usr/bin/env python3
"""
Stress-test /analyze on data/eval/stress_67.json (67 scenarios, easy → hard).

Grades every answer against the official statute text
(data/legal_corpus/statutes/*_section_titles.json, from the Gazette):

  required     every `require` / `require_bnss` / `require_ipc` group is cited
  mentions     every `mention` group appears (special laws, key doctrine)
  hard errors  (counted automatically — each one is a hallucination)
               · a BNS/BNSS section number that does not exist
               · a section number labelled with an offence its official title doesn't cover
               · BNS 106(2) relied on (never brought into force)
               · an IPC↔BNS pairing that contradicts the concordance
               · case law that is unverified, overruled, or wrongly reported
  review flags (listed for a human to confirm — never auto-scored)
               · "BNS 302 (murder)": a real number tied to the wrong offence
               · a `forbid` section cited without being ruled out in context
               · BNS sections the knowledge base does not cover

USAGE
  python3 tools/eval_stress.py --base-url http://localhost:8081 --out-dir <dir>
  python3 tools/eval_stress.py --regrade --out-dir <dir>   # re-score saved answers, no model calls
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

from verifier import (_CASE_RE, _CITE_RES, _ipc_cited, cited_sections,  # noqa: E402
                      known_bns_sections, label_mismatches, mapping_mismatches,
                      nonexistent_sections, not_in_force, precedent_check,
                      sc_record_check)

SCENARIOS = ROOT / "data" / "eval" / "stress_67.json"
STATUTES = ROOT / "data" / "legal_corpus" / "statutes"
SECTION_KEYS = [f"section_{i}" for i in range(1, 7)]

# Offence words a model writes next to a citation, and the words that must
# appear in that section's official title for the label to be right.
_LABEL_WORDS = {
    "murder": ["murder"], "culpable homicide": ["culpable homicide"],
    "negligen": ["negligen"], "grievous": ["grievous"], "theft": ["theft"],
    "robbery": ["robbery"], "dacoity": ["dacoity"], "snatching": ["snatching"],
    "extortion": ["extortion"], "cheating": ["cheat"], "personation": ["personation"],
    "breach of trust": ["breach of trust"], "misappropriation": ["misappropriation"],
    "forg": ["forg"], "trespass": ["trespass"], "mischief": ["mischief"],
    "house-breaking": ["house-breaking", "house- breaking", "house breaking"],
    "intimidation": ["intimidation"], "defamation": ["defamation"], "stalking": ["stalking"],
    "voyeurism": ["voyeurism"], "rape": ["rape"], "sexual harassment": ["sexual harassment"],
    "modesty": ["modesty"], "cruelty": ["cruelty"], "dowry": ["dowry"], "suicide": ["suicide"],
    "kidnap": ["kidnap"], "ransom": ["ransom"], "confinement": ["confinement"],
    "conspiracy": ["conspiracy"], "rioting": ["rioting"], "unlawful assembly": ["unlawful assembly"],
    "enmity": ["enmity"], "organised crime": ["organised crime"], "acid": ["acid"],
    "stolen property": ["stolen property"], "bigamy": ["marrying again"],
    "deceitful": ["deceitful"], "rash driving": ["rash driving"],
}
# Labels whose words are not in the official title but are still right.
_LABEL_OK = {("BNS", "3"): {"common intention"}, ("BNS", "86"): {"cruelty"}}
_BNSS_LABELS = {
    "anticipatory bail": {"482"}, "first information": {"173"}, "fir": {"173"},
    "zero fir": {"173"}, "chargesheet": {"193"}, "charge sheet": {"193"},
    "inherent power": {"528"}, "quash": {"528"}, "remand": {"187"},
    "notice of appearance": {"35"},
}
_NEGATION = re.compile(
    r"\b(not|no|nor|rather than|instead|inapplicable|does not|doesn't|cannot|"
    r"would not|wouldn't|excluded|ruled out|unlike|distinguish|isn't|is not|"
    r"neither|only if|unless|would apply if|if .{0,40} had)\b", re.I)


def load_titles() -> dict[str, dict[str, str | None]]:
    out = {}
    for code in ("bns", "bnss", "bsa"):
        raw = json.loads((STATUTES / f"{code}_section_titles.json").read_text(encoding="utf-8"))
        out[code.upper()] = raw["sections"]
    return out


def _base(s: str) -> str:
    return re.sub(r"\(.*$", "", s.upper().replace(" ", ""))


def _descriptor(text: str, end: int) -> str:
    """The words right after a citation: 'BNS 302 (murder)' → '(murder)'."""
    tail = text[end:end + 70]
    stop = re.search(r"\b(?:BNS|BNSS|BSA|IPC|CrPC|Section)\b|[\n;]", tail)
    return (tail[:stop.start()] if stop else tail).lower()


def mislabels(text: str, titles: dict) -> list[str]:
    """Real section numbers tied to an offence their official title doesn't cover."""
    hits: list[str] = []
    for code in ("BNS", "BNSS"):
        for m in _CITE_RES[code].finditer(text):
            nums = re.findall(r"\d{1,3}", m.group(1))
            if len(nums) != 1:          # a list — the label can't be pinned to one number
                continue
            num = nums[0]
            title = (titles[code].get(num) or "").lower()
            desc = _descriptor(text, m.end())
            if code == "BNS":
                if not title:
                    continue
                said = [k for k in _LABEL_WORDS if k in desc]
                ok = _LABEL_OK.get((code, num), set())
                if said and not any(any(w in title for w in _LABEL_WORDS[k]) or k in ok for k in said):
                    hits.append(f"BNS {num} labelled '{desc.strip()[:50]}' — official: {titles[code][num]}")
            else:
                said = [k for k in _BNSS_LABELS if re.search(rf"\b{re.escape(k)}\b", desc)]
                if said and not any(num in _BNSS_LABELS[k] for k in said):
                    hits.append(f"BNSS {num} labelled '{desc.strip()[:50]}' — official: {titles[code].get(num)}")
    return sorted(set(hits))


def nonexistent(text: str) -> list[str]:
    return nonexistent_sections(text)


def forbidden_hits(text: str, forbid: list[str]) -> list[str]:
    """Forbidden sections cited without a ruling-out word nearby."""
    hits = []
    for f in forbid:
        pat = re.compile(rf"(?:BNS|Bharatiya Nyaya Sanhita)[^\n]{{0,25}}?\b{f}\b(?!\d)", re.I)
        for m in pat.finditer(text):
            ctx = text[max(0, m.start() - 120):m.end() + 120]
            # Negation must sit in the citation's own sentence to rule it out.
            near = re.split(r"(?<=[.!?\n])\s+", text[max(0, m.start() - 80):m.end() + 60])
            own = next((s for s in near if f.lower() in s.lower()), ctx)
            if not _NEGATION.search(own):
                hits.append(f"BNS {f}: …{ctx.strip()[:200]}…")
                break
    return hits


def case_names(text: str) -> list[str]:
    return sorted({m.group(0).strip()[:90] for m in _CASE_RE.finditer(text)})


def grade(sections: dict, sc: dict, titles: dict, known: set[str]) -> dict:
    # Answers arrive as display HTML (<strong>, <br>); grade the words, not the markup.
    text = re.sub(r"<[^>]+>", "", "\n".join(sections.get(k) or "" for k in SECTION_KEYS))
    low = text.lower()
    bns = {_base(c) for c in cited_sections(text, "BNS")}
    bnss = {_base(c) for c in cited_sections(text, "BNSS")}
    ipc = {_base(c) for c in _ipc_cited(text)}
    missing = [f"BNS {'/'.join(g)}" for g in sc.get("require", []) if not bns & set(g)]
    missing += [f"BNSS {'/'.join(g)}" for g in sc.get("require_bnss", []) if not bnss & set(g)]
    missing += [f"IPC {s}" for s in sc.get("require_ipc", []) if s not in ipc]
    missing_mentions = ["/".join(g) for g in sc.get("mention", [])
                        if not any(w.lower() in low for w in g)]
    prec = precedent_check(text)
    hard = (nonexistent(text)
            + [f"{m['cited']} is '{m['official_title']}', not {m['label']}" for m in label_mismatches(text)]
            + [f"{p} relied on but not in force" for p in not_in_force(text)]
            + [f"SC record: {r['cited']} {r['problem']}" for r in sc_record_check(text)]
            + [f"IPC {m['ipc']} → BNS {m['cited_bns']} (wrong pair)" for m in mapping_mismatches(text)]
            + [f"unverified case: {c}" for c in prec["unverified"]]
            + [f"bad law: {b['case']} ({b.get('status')})" for b in prec["bad_law"]]
            + [f"wrong report: {w['case']}" for w in prec["wrong_citation"]])
    present = sum(1 for k in SECTION_KEYS if len((sections.get(k) or "").strip()) >= 40)
    return {
        "id": sc["id"], "tier": sc["tier"],
        "sections_present": present,
        "cited_bns": sorted(bns, key=lambda s: int(s) if s.isdigit() else 0),
        "cited_bnss": sorted(bnss, key=lambda s: int(s) if s.isdigit() else 0),
        "missing": missing, "missing_mentions": missing_mentions,
        "hard_errors": hard,
        "review_mislabels": mislabels(text, titles),
        "review_forbidden": forbidden_hits(text, sc.get("forbid", [])),
        "outside_kb": sorted(b for b in bns if b not in known),
        "case_names": case_names(text),
        "pass": present == 6 and not missing and not missing_mentions and not hard,
    }


def fetch(base_url: str, story: str, timeout: int = 300) -> dict:
    body = json.dumps({"client_story": story, "language": "en"}).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + "/analyze", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read().decode("utf-8"))
    import html
    payload["sections"] = {k: html.unescape(v) if isinstance(v, str) else v
                           for k, v in (payload.get("sections") or {}).items()}
    return payload


def write_report(out_dir: Path, results: list[dict]) -> None:
    (out_dir / "stress_report.json").write_text(
        json.dumps({"results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# /analyze stress test — 67 scenarios", "",
             "| Case | Tier | Pass | Missing | Missing concept | Hard errors | Review flags |",
             "|------|------|:----:|---------|-----------------|-------------|--------------|"]
    for g in results:
        flags = len(g["review_mislabels"]) + len(g["review_forbidden"])
        lines.append(f"| `{g['id']}` | {g['tier']} | {'✅' if g['pass'] else '❌'} "
                     f"| {', '.join(g['missing']) or '—'} | {', '.join(g['missing_mentions']) or '—'} "
                     f"| {'; '.join(g['hard_errors']) or '—'} | {flags or '—'} |")
    if results:
        by_tier = {}
        for g in results:
            t = by_tier.setdefault(g["tier"], [0, 0])
            t[0] += g["pass"]; t[1] += 1
        n_pass = sum(g["pass"] for g in results)
        n_hard = sum(bool(g["hard_errors"]) for g in results)
        lines += ["", f"**Passed {n_pass}/{len(results)} ({100 * n_pass / len(results):.1f}%)** — "
                  + ", ".join(f"{t} {p}/{n}" for t, (p, n) in by_tier.items())
                  + f". Answers with a hard error (hallucination): {n_hard}."]
    (out_dir / "stress_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--base-url", default="http://localhost:8081")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--only", default="", help="Comma list of scenario ids.")
    ap.add_argument("--regrade", action="store_true", help="Re-score saved answers only.")
    ap.add_argument("--busy-wait", type=int, default=75, help="Seconds to wait after a 503/429.")
    ap.add_argument("--busy-retries", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=300,
                    help="Seconds to wait for one analysis (local models need ~900).")
    args = ap.parse_args()

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    answers_path = out_dir / "stress_answers.jsonl"
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
    if args.only:
        keep = set(args.only.split(","))
        scenarios = [s for s in scenarios if s["id"] in keep]
    titles, known = load_titles(), known_bns_sections()

    answers: dict[str, dict] = {}
    if answers_path.exists():
        for line in answers_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line); answers[row["id"]] = row

    if not args.regrade:
        todo = [s for s in scenarios if s["id"] not in answers]
        print(f"{len(answers)} answered already; running {len(todo)} against {args.base_url}\n")
        gave_up = 0
        for sc in todo:
            payload = None
            for attempt in range(args.busy_retries):
                try:
                    t0 = time.monotonic()
                    payload = fetch(args.base_url, sc["story"], args.timeout)
                    payload["seconds"] = round(time.monotonic() - t0, 1)
                    break
                except urllib.error.HTTPError as e:
                    msg = e.read().decode("utf-8", "replace")[:300]
                    print(f"  ! {sc['id']}: HTTP {e.code} {msg}")
                    if e.code not in (429, 503):
                        break
                    time.sleep(args.busy_wait)
                except Exception as e:  # noqa: BLE001
                    print(f"  ! {sc['id']}: {e}")
                    if "timed out" in str(e):
                        break          # re-sending re-runs the whole analysis; move on
                    time.sleep(args.busy_wait)
            if payload is None:
                gave_up += 1
                if gave_up >= 3:
                    print("\nThree scenarios in a row could not run — provider quota is "
                          "probably exhausted for today. Re-run later; answered cases are kept.")
                    break
                continue
            gave_up = 0
            row = {"id": sc["id"], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **payload}
            with open(answers_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            answers[sc["id"]] = row
            g = grade(row["sections"], sc, titles, known)
            print(f"  {sc['id']:32s} {'PASS' if g['pass'] else 'FAIL'}  {row['seconds']:>5}s  "
                  f"missing={g['missing'] or '-'} concepts={g['missing_mentions'] or '-'} "
                  f"hard={len(g['hard_errors'])} review={len(g['review_mislabels']) + len(g['review_forbidden'])}")

    results = [grade(answers[s["id"]]["sections"], s, titles, known)
               for s in scenarios if s["id"] in answers]
    write_report(out_dir, results)
    n = len(results)
    if n:
        print(f"\nGraded {n}: passed {sum(g['pass'] for g in results)}, "
              f"hard errors in {sum(bool(g['hard_errors']) for g in results)} → {out_dir/'stress_report.md'}")


if __name__ == "__main__":
    main()
