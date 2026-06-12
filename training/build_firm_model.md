# Deployment-specific model — fine-tuning on a deployment's own data

The base model (see [`README.md`](README.md)) is trained on the project's verified
BNS/BNSS/BSA knowledge base. A deployment can *additionally* fine-tune on its own
consented data — its matters, precedents, and house style — and run that model on
its own server, so nothing leaves the premises.

This is the same pipeline with one extra input.

## How it works

1. **Collect the deployment's data** as a JSONL of `{"q": ..., "a": ...}` pairs,
   drawn from won matters, internal notes, precedent briefs, and FAQs. Strip
   personal data first (consent + DPDP). One file per practice area is fine.

2. **Generate** with that data appended to the verified base:

   ```bash
   python3 tools/generate_instruction_data.py --firm-data /path/to/pairs/
   ```

   `--firm-data` accepts a `.jsonl` file or a directory of them. These pairs are
   tagged `source="firm"` and merged with the deterministic base, so the model
   keeps statutory accuracy and gains the deployment's own material.

3. **Train / package / evaluate** exactly as in [`README.md`](README.md), naming
   the model for the deployment:

   ```bash
   python3 train_qlora.py --base-model qwen --data train.jsonl --out lexindic-acme
   ollama create lexindic-acme -f Modelfile.qwen   # adjust FROM
   ```

4. **Deploy on the deployment's own hardware.** `OLLAMA_MODEL=lexindic-acme` runs
   air-gapped; updates ship as a new GGUF when the data set grows.

## Notes

- The whole loop (data → train → eval → GGUF) is scripted, so a refresh is a
  repeatable operation, not a research project.
- **Compliance:** trained *only* on that deployment's own consented data, kept on
  that deployment's server, never pooled across deployments. See [`/trust`](../compliance.py).

## Status

The `--firm-data` adapter (`firm_pairs()` in `tools/generate_instruction_data.py`)
is built and tested. Pulling matters directly from `matters.py` and parsing
precedent `.docx`/`.pdf` into pairs is deliberately deferred until there is a real
corpus to build it against.
