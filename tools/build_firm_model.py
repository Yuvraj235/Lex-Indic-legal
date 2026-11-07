#!/usr/bin/env python3
"""
Orchestrate a per-deployment fine-tune end-to-end:
  ingest matters → build data → (GPU train) → package → evaluate → serve.

The GPU steps are printed, not run (no GPU on the dev box). Run with --run to
execute the local, non-GPU steps (ingest + data build).

  python3 tools/build_firm_model.py --firm FIRM_ID
  python3 tools/build_firm_model.py --firm FIRM_ID --base-model llama --run
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Per-deployment fine-tune pipeline.")
    ap.add_argument("--firm", required=True)
    ap.add_argument("--base-model", default="qwen", choices=["qwen", "llama"])
    ap.add_argument("--run", action="store_true",
                    help="Execute the local (non-GPU) steps 1-2.")
    args = ap.parse_args()

    firm = args.firm
    pairs = f"data/finetune/firm_{firm.replace('/', '_')}_pairs.jsonl"
    model = f"lexindic-{firm.replace('/', '-').lower()}"
    steps = [
        ("ingest firm matters → redacted pairs",
         f"python3 tools/firm_corpus.py --firm {firm} --out {pairs}"),
        ("merge with verified base → train.jsonl",
         f"python3 tools/generate_instruction_data.py --firm-data {pairs}"),
        ("[GPU / RunPod] QLoRA fine-tune → GGUF",
         f"python3 training/train_qlora.py --base-model {args.base_model} "
         f"--data train.jsonl --out {model}"),
        ("[GPU box] package for Ollama",
         f"ollama create {model} -f training/Modelfile.{args.base_model}"),
        ("evaluate vs the generic baseline",
         f"python3 tools/eval_model.py --models groq,ollama:{model}"),
        ("serve on the firm's own box (air-gapped)",
         f"LLM_PROVIDER=ollama OLLAMA_MODEL={model} python3 app.py"),
    ]

    print(f"\nPer-deployment model pipeline for firm '{firm}':\n")
    for i, (label, cmd) in enumerate(steps, 1):
        print(f"  {i}. {label}\n     {cmd}\n")

    if args.run:
        for label, cmd in steps[:2]:
            print(f"--- running: {label} ---")
            # No shell: `firm` comes from the command line and is interpolated
            # into cmd, so shell metacharacters in it must stay inert.
            subprocess.run(shlex.split(cmd), check=False)
    else:
        print("Re-run with --run to execute the local steps 1-2; the GPU steps "
              "(3-4) stay manual on a rented GPU.")


if __name__ == "__main__":
    main()
