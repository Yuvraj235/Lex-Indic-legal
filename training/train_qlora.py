#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — QLoRA fine-tune → GGUF  (Day 26, runs on a rented GPU)          ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS DOES
──────────────
Fine-tunes a small base model on the instruction data built by
tools/generate_instruction_data.py, then exports a GGUF that drops straight into
Lex-Indic's existing Ollama path (llm_provider.py) — no app-code change, just
`OLLAMA_MODEL=lexindic-qwen`.

WHERE THIS RUNS
───────────────
NOT on the dev Mac (no GPU). Run it on a single rented GPU — RunPod A100/4090 or
Colab Pro. QLoRA fits a 7-8B model in ~16 GB VRAM and trains in a couple of
hours for a few hundred rupees. See training/README.md for the click-by-click.

WHY UNSLOTH
───────────
~2x faster, ~half the VRAM of vanilla HF, and it ships a one-call GGUF exporter
(`save_pretrained_gguf`) — so data → trained → GGUF is one script.

USAGE (on the GPU box)
  pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git" trl
  python3 train_qlora.py --base-model qwen   --data train.jsonl --out lexindic-qwen
  python3 train_qlora.py --base-model llama  --data train.jsonl --out lexindic-llama

Per the sprint decision we train BOTH and let tools/eval_model.py pick the winner.
"""

from __future__ import annotations

import argparse

# Base models — both run on one consumer GPU via Ollama after GGUF export.
# Qwen handles Devanagari/Hindi noticeably better (our differentiator); Llama has
# the widest tooling. We evaluate both and ship whichever scores higher.
BASE_MODELS = {
    "qwen": "unsloth/Qwen2.5-7B-Instruct",
    "llama": "unsloth/Meta-Llama-3.1-8B-Instruct",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="QLoRA fine-tune → GGUF for Lex-Indic.")
    ap.add_argument("--base-model", choices=BASE_MODELS, required=True)
    ap.add_argument("--data", default="train.jsonl",
                    help="Chat-format JSONL from tools/generate_instruction_data.py")
    ap.add_argument("--out", required=True, help="Output dir / model name prefix")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--max-seq-len", type=int, default=2048)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--quant", default="q4_k_m", help="GGUF quant for Ollama")
    args = ap.parse_args()

    # Heavy imports live inside main() so the file imports cleanly on the dev box
    # (for linting / review) without unsloth + torch installed.
    from datasets import load_dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template

    base = BASE_MODELS[args.base_model]
    print(f"Loading {base} in 4-bit …")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base,
        max_seq_length=args.max_seq_len,
        load_in_4bit=True,           # QLoRA: 4-bit base + trainable LoRA adapters
        dtype=None,
    )
    tokenizer = get_chat_template(
        tokenizer,
        chat_template="qwen-2.5" if args.base_model == "qwen" else "llama-3.1",
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16, lora_alpha=16, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
        random_state=7,
    )

    # Our data is already in {"messages":[...]} chat shape → render with the
    # tokenizer's chat template into a single training string per row.
    def fmt(batch):
        return {"text": [tokenizer.apply_chat_template(m, tokenize=False,
                                                       add_generation_prompt=False)
                         for m in batch["messages"]]}

    ds = load_dataset("json", data_files=args.data, split="train").map(fmt, batched=True)
    print(f"Training on {len(ds)} examples for {args.epochs} epoch(s) …")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        args=SFTConfig(
            dataset_text_field="text",
            max_seq_length=args.max_seq_len,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            warmup_ratio=0.05,
            logging_steps=10,
            optim="adamw_8bit",
            seed=7,
            output_dir=f"{args.out}-ckpt",
        ),
    )
    trainer.train()

    # One-call export: merged GGUF that `ollama create` consumes directly.
    print(f"Exporting GGUF ({args.quant}) → {args.out} …")
    model.save_pretrained_gguf(args.out, tokenizer, quantization_method=args.quant)
    print(f"\n✓ Done. Copy {args.out}/*.gguf next to training/Modelfile.{args.base_model},")
    print(f"  then: ollama create lexindic-{args.base_model} -f Modelfile.{args.base_model}")


if __name__ == "__main__":
    main()
