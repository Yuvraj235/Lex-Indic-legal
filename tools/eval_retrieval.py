#!/usr/bin/env python3
"""
Retrieval-only eval: does the search put the right law in front of the model?

For every scenario in data/eval/stress_67.json, retrieves the top-k documents
exactly as /analyze does and checks each `require` / `require_bnss` group:
a group is found when any of its sections is among the retrieved sections.
No LLM call — runs on the embedding provider only (EMBEDDINGS_PROVIDER).

USAGE
  EMBEDDINGS_PROVIDER=ollama OLLAMA_EMBED_MODEL=bge-m3 python3 tools/eval_retrieval.py
  python3 tools/eval_retrieval.py --k 8 --out <file.json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCENARIOS = ROOT / "data" / "eval" / "stress_67.json"


def retrieved_sections(context: str) -> dict[str, set[str]]:
    """Section numbers per Act that the retrieved documents are about (their
    first line), plus BNS targets named in IPC→BNS mapping documents."""
    out: dict[str, set[str]] = {"BNS": set(), "BNSS": set(), "BSA": set()}
    for block in context.split("\n[SECTION ")[1:]:
        head = block.split("\n", 2)[1] if "\n" in block else block
        m = re.match(r"(BNS|BNSS|BSA) Section (\d+)", head)
        if m:
            out[m.group(1)].add(m.group(2))
        for n in re.findall(r"SECTION MAPPING: .*? is now BNS (\d+)", head):
            out["BNS"].add(n)
    return out


def score(sc: dict, got: dict[str, set[str]]) -> dict:
    groups = ([("BNS", g) for g in sc.get("require", [])]
              + [("BNSS", g) for g in sc.get("require_bnss", [])])
    missed = [f"{code} {'/'.join(g)}" for code, g in groups if not got[code] & set(g)]
    return {"id": sc["id"], "tier": sc["tier"], "groups": len(groups),
            "found": len(groups) - len(missed), "missed": missed}


def main() -> None:
    ap = argparse.ArgumentParser(description="Retrieval recall on the stress scenarios.")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    import main as pipeline
    pipeline.configure_gemini_embeddings()
    collection = pipeline.build_rag_knowledge_base()

    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
    results = []
    for sc in scenarios:
        ctx, _ = pipeline.retrieve_relevant_sections_structured(collection, sc["story"], n_results=args.k)
        results.append(score(sc, retrieved_sections(ctx)))

    total = sum(r["groups"] for r in results)
    found = sum(r["found"] for r in results)
    print(f"\nprovider={pipeline.embeddings_provider()} k={args.k}: "
          f"required sections retrieved {found}/{total} ({100 * found / max(total, 1):.1f}%)")
    for tier in ("easy", "medium", "hard"):
        rs = [r for r in results if r["tier"] == tier]
        t, f = sum(r["groups"] for r in rs), sum(r["found"] for r in rs)
        print(f"  {tier:6s} {f}/{t}")
    for r in results:
        if r["missed"]:
            print(f"  missed {r['id']}: {', '.join(r['missed'])}")
    if args.out:
        Path(args.out).write_text(json.dumps({"k": args.k, "provider": pipeline.embeddings_provider(),
                                              "results": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
