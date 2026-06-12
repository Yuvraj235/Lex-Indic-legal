#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Model evaluation harness (Day 26)                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS DOES
──────────────
Scores any model on the HELD-OUT gold set produced by
tools/generate_instruction_data.py (data/finetune/eval.jsonl) and prints the
the headline section-mapping accuracy number:

    "Our fine-tuned 7B gets BNS section-mapping right 96% of the time, vs 71%
     for a generic 70B model."

Because the eval questions were deliberately excluded from training, the number
is honest.

WHAT IT CAN SCORE
─────────────────
  groq            the generic big-model baseline (Llama-3.3-70B via Groq)
  ollama:<name>   any local Ollama model — a vanilla base (ollama:qwen2.5:7b)
                  or your fine-tune (ollama:lexindic-qwen).

So the SAME harness runs today against Groq (giving the baseline immediately),
and later against the fine-tuned GGUFs once they are pulled into Ollama.

USAGE
  python3 tools/eval_model.py --models groq
  python3 tools/eval_model.py --models groq,ollama:lexindic-qwen,ollama:qwen2.5:7b

OUTPUTS (data/finetune/)
  eval_report.json   machine-readable scores
  eval_report.md     a comparison table for the /trust page
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()                # so the groq baseline sees GROQ_API_KEY
except ImportError:
    pass

EVAL_FILE = ROOT / "data" / "finetune" / "eval.jsonl"
OUT_DIR = ROOT / "data" / "finetune"

# Minimal, identical-across-models system prompt so we measure KNOWLEDGE, not
# prompt engineering. (A heavier prompt would flatter every model equally and
# hide the gap the fine-tune is supposed to close.)
EVAL_SYSTEM = (
    "You are an expert on Indian criminal law under the Bharatiya Nyaya Sanhita "
    "(BNS) 2023. Answer concisely and factually."
)

GROQ_MODEL = "llama-3.3-70b-versatile"

# 'BNS 103', 'BNS Section 103', 'BNS 103(2)', 'B.N.S. 103' → 103 / 103(2)
_BNS_RE = re.compile(r"B\.?N\.?S\.?\s*(?:Section|Sec\.?|S\.?)?\s*(\d{1,4}[A-Z]?(?:\(\d+\))?)",
                     re.IGNORECASE)
_NUM_RE = re.compile(r"\b(\d{1,4}[A-Z]?(?:\(\d+\))?)\b")


# ──────────────────────────────────────────────────────────────────────────────
# Pure scoring helpers — unit-tested in tests/test_pure.py
# ──────────────────────────────────────────────────────────────────────────────
def extract_bns_section(text: str) -> str | None:
    """Pull the BNS section the model named. Prefer an explicit 'BNS NNN'
    mention; fall back to the first bare number only if no 'BNS' anchor exists."""
    if not text:
        return None
    m = _BNS_RE.search(text)
    if m:
        return _norm(m.group(1))
    m = _NUM_RE.search(text)
    return _norm(m.group(1)) if m else None


def _norm(s: str) -> str:
    return s.upper().replace(" ", "")


def score_one(gold: dict, response: str) -> bool:
    """True if `response` answers `gold` correctly."""
    kind = gold.get("kind")
    if kind == "mapping":
        return extract_bns_section(response) == _norm(gold["expected_bns"])
    if kind == "fact":
        # 'non-bailable' must not be satisfied by a bare 'bailable' substring,
        # so check the negative form first.
        text = (response or "").lower()
        want = gold["expected_substring"].lower()
        if want == "bailable":
            return "bailable" in text and "non-bailable" not in text \
                and "non bailable" not in text
        return want in text or want.replace("-", " ") in text
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Model adapters (network)
# ──────────────────────────────────────────────────────────────────────────────
def _query_groq(question: str, temperature: float) -> str:
    from main import configure_groq
    client = configure_groq()
    comp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": EVAL_SYSTEM},
                  {"role": "user", "content": question}],
        temperature=temperature,
        max_tokens=300,
    )
    return comp.choices[0].message.content or ""


def _query_ollama(model: str, question: str, temperature: float) -> str:
    import json as _json
    import urllib.request
    import llm_provider
    body = _json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": EVAL_SYSTEM},
                     {"role": "user", "content": question}],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": 300},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{llm_provider.ollama_host()}/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = _json.loads(resp.read().decode("utf-8"))
    return (payload.get("message") or {}).get("content") or ""


def query(model_spec: str, question: str, temperature: float) -> str:
    if model_spec == "groq":
        return _query_groq(question, temperature)
    if model_spec.startswith("ollama:"):
        return _query_ollama(model_spec.split(":", 1)[1], question, temperature)
    raise ValueError(f"Unknown model spec '{model_spec}'. "
                     f"Use 'groq' or 'ollama:<name>'.")


# ──────────────────────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class ModelScore:
    model: str
    correct: int = 0
    total: int = 0
    by_kind: dict = field(default_factory=dict)   # kind -> [correct, total]
    wrong: list[str] = field(default_factory=list)
    errors: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def load_gold(path: Path, limit: int | None) -> list[dict]:
    if not path.exists():
        raise ValueError(f"No eval set at {path}. Run "
                         f"tools/generate_instruction_data.py first.")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return rows[:limit] if limit else rows


def evaluate(model_spec: str, gold: list[dict], temperature: float) -> ModelScore:
    s = ModelScore(model=model_spec)
    for g in gold:
        s.total += 1
        k = g.get("kind", "?")
        s.by_kind.setdefault(k, [0, 0])
        s.by_kind[k][1] += 1
        try:
            resp = query(model_spec, g["question"], temperature)
        except Exception as e:  # noqa: BLE001 — one bad call shouldn't void the run
            s.errors += 1
            s.wrong.append(g.get("id", "?"))
            print(f"    ! {model_spec} error on {g.get('id')}: {e}")
            continue
        if score_one(g, resp):
            s.correct += 1
            s.by_kind[k][0] += 1
        else:
            s.wrong.append(g.get("id", "?"))
    return s


def write_reports(scores: list[ModelScore], gold: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_questions": len(gold),
        "results": {
            s.model: {
                "accuracy": round(s.accuracy, 4),
                "correct": s.correct, "total": s.total, "errors": s.errors,
                "by_kind": {k: {"correct": v[0], "total": v[1]}
                            for k, v in s.by_kind.items()},
                "wrong": s.wrong,
            } for s in scores
        },
    }
    (OUT_DIR / "eval_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Lex-Indic — BNS knowledge eval",
        "",
        f"_Generated {payload['generated_at']} · {len(gold)} held-out questions "
        f"(never seen in training)._",
        "",
        "| Model | Accuracy | Correct | Mapping | Fact | Errors |",
        "|-------|---------:|--------:|--------:|-----:|-------:|",
    ]
    for s in sorted(scores, key=lambda x: x.accuracy, reverse=True):
        mp = s.by_kind.get("mapping", [0, 0])
        ft = s.by_kind.get("fact", [0, 0])
        lines.append(
            f"| `{s.model}` | **{s.accuracy*100:.0f}%** | {s.correct}/{s.total} "
            f"| {mp[0]}/{mp[1]} | {ft[0]}/{ft[1]} | {s.errors} |")
    lines += [
        "",
        "Mapping = 'what is the BNS equivalent of IPC NNN'. Fact = bailable / "
        "non-bailable status. Both have a single verifiable right answer drawn "
        "from `data/legal_corpus/ipc_bns_mapping.json` and the knowledge base.",
        "",
    ]
    (OUT_DIR / "eval_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate models on held-out BNS gold.")
    ap.add_argument("--models", default="groq",
                    help="Comma list: groq, ollama:<name>, …")
    ap.add_argument("--eval-file", default=str(EVAL_FILE))
    ap.add_argument("--limit", type=int, default=None,
                    help="Score only the first N questions (quick smoke test).")
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    gold = load_gold(Path(args.eval_file), args.limit)
    specs = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"Scoring {len(specs)} model(s) on {len(gold)} held-out questions …\n")

    scores: list[ModelScore] = []
    for spec in specs:
        t0 = time.monotonic()
        print(f"  → {spec}")
        s = evaluate(spec, gold, args.temperature)
        dt = time.monotonic() - t0
        print(f"    {s.accuracy*100:.0f}%  ({s.correct}/{s.total}, "
              f"{s.errors} errors, {dt:.0f}s)\n")
        scores.append(s)

    write_reports(scores, gold)
    print(f"✓ wrote {OUT_DIR/'eval_report.md'} and eval_report.json")
    if len(scores) > 1:
        best = max(scores, key=lambda x: x.accuracy)
        print(f"\nBest: {best.model} at {best.accuracy*100:.0f}%. "
              f"Ship it via OLLAMA_MODEL and drop the number on /trust.")


if __name__ == "__main__":
    main()
