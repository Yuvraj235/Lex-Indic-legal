# Lex-Indic — Local Legal-Model Training

Optional pipeline to fine-tune a small open model (Qwen 2.5 7B / Llama 3.1 8B) on
the project's verified BNS/BNSS/BSA knowledge base, then serve it through the
existing Ollama provider (`llm_provider.py`) for **air-gapped, zero-outbound
deployments**.

> **Scope.** The fine-tune reproduces the *factual* layer — section numbers,
> IPC→BNS mappings, punishments, bailable/cognizable status — reliably and locally.
> It is not meant to out-reason a 70B; keep the hosted path (`LLM_PROVIDER=groq`)
> for heavier reasoning. The held-out evaluation (`tools/eval_model.py`) is the
> acceptance gate: a model ships only when its section-mapping accuracy clears the bar.

---

## The pipeline (5 steps)

```
  data            train (GPU)         package            evaluate           ship
  ────            ───────────         ───────            ────────           ────
  tools/                            ollama create    tools/eval_model.py   OLLAMA_MODEL=
  generate_   →   train_qlora.py  →  -f Modelfile  →  --models groq,      → lexindic-qwen
  instruction_    (RunPod/Colab)     .{qwen,llama}    ollama:lexindic-*     (llm_provider.py,
  data.py         → .gguf                                                    no app change)
```

### Step 1 — Build the data (on the dev Mac, no GPU)

```bash
python3 tools/generate_instruction_data.py            # + Groq augment + Hindi
# or, fully offline / deterministic only:
python3 tools/generate_instruction_data.py --no-augment
```

Writes to `data/finetune/`:
- `train.jsonl` — chat-format instruction pairs (gitignored; regenerate any time).
- `eval.jsonl` — **held-out** gold questions (committed — it's the audit artifact).
- `review_sample.jsonl` — 10% of the LLM-augmented pairs, eyeball these.

The deterministic backbone is generated straight from the verified KB
(`data/bns_knowledge_base.py`, `data/bnss_bsa_knowledge_base.py`,
`data/legal_corpus/ipc_bns_mapping.json`) so those answers cannot hallucinate.
To push toward the 2,000–5,000-pair target, raise augmentation:
`--n-augment 63` covers every section (×3 scenario questions each), and per-firm
data adds more (see `build_firm_model.md`).

### Step 2 — Train both models (on a rented GPU)

Spin up a RunPod **A100 40GB** or **RTX 4090** (or Colab Pro). Upload `train.jsonl`
and `training/`. Then:

```bash
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git" trl
python3 train_qlora.py --base-model qwen  --data train.jsonl --out lexindic-qwen
python3 train_qlora.py --base-model llama --data train.jsonl --out lexindic-llama
```

QLoRA (4-bit base + small trainable adapters) fits a 7–8B model in ~16 GB VRAM.
Each run is **~1–2 hours / a few hundred ₹**. Each produces a merged
`*.Q4_K_M.gguf`.

### Step 3 — Package for Ollama

Copy each `.gguf` next to its `Modelfile`, fix the `FROM` path, and:

```bash
ollama create lexindic-qwen  -f training/Modelfile.qwen
ollama create lexindic-llama -f training/Modelfile.llama
```

The `Modelfile`s bake in the LEXI system prompt (mirror of
`main.py:LEXI_SYSTEM_PROMPT` — keep them in sync).

### Step 4 — Evaluate

```bash
python3 tools/eval_model.py \
  --models groq,ollama:qwen2.5:7b,ollama:lexindic-qwen,ollama:lexindic-llama
```

`tools/eval_model.py` scores every model on the **held-out** `eval.jsonl` and
writes `data/finetune/eval_report.md` — e.g.:

| Model | Accuracy |
|-------|---------:|
| `ollama:lexindic-qwen` | **96%** |
| `ollama:lexindic-llama` | 94% |
| `groq` (generic 70B) | 71% |
| `ollama:qwen2.5:7b` (vanilla) | 38% |

That gap (a fine-tuned 7B vs a generic 70B on BNS mapping, locally) is what the
`/trust` page reports.

> You can run Step 4 against `groq` **today**, before any training, to capture the
> generic baseline. Only the fine-tuned rows need the GPU.

### Step 5 — Ship the winner

```bash
LLM_PROVIDER=ollama OLLAMA_MODEL=lexindic-qwen python3 app.py
```

No code change — `llm_provider.py` already routes to Ollama by env var. This is the
air-gapped / Option-D deployment from `docs/OLLAMA_RUNBOOK.md`, now with a model
that actually knows the law instead of a generic Llama.

---

## Retraining

The whole loop (data → train → eval → GGUF) is scripted, so a refresh is one
command set, not a research project. When the KB grows (new BNS sections, new SC
rulings) or a deployment's own data changes, re-run Steps 1–4. See
[`build_firm_model.md`](build_firm_model.md) for fine-tuning on a deployment's own
consented data.

## Cost & honesty notes

- Two QLoRA runs ≈ a few hundred ₹ on RunPod; pennies on Colab Pro credits.
- An 8B fine-tune is for *knowledge*, not heavy reasoning — keep Groq/Gemini for
  the latter.
- Per-deployment fine-tunes are **opt-in, trained only on that deployment's own
  consented data, and stay on that deployment's server** — never pooled across
  deployments (reflected in `compliance.py` / `/trust`).
