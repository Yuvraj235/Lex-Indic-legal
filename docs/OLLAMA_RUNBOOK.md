# Local Ollama deployment — zero-sub-processor runbook

This is the path for customers who want **no data to leave their machine**:
the entire Lex-Indic pipeline runs on a single laptop / firm server, with
inference handled by a local Llama-3.3-70B via [Ollama](https://ollama.com).

This is the path Lex-Indic's `/trust` page promises.  Use it for:
- Firms with strict on-premise data-residency requirements
- NBFCs / fintechs where a Groq cross-border data-transfer DPIA fails
- Government / DLSA deployments under DPDP §17

---

## Hardware requirements

| Model | Min RAM | Recommended GPU | Tokens/sec |
|---|---|---|---|
| `llama3.3:70b` | 64 GB | 2× A100 80GB or Mac Studio M2 Ultra 192GB | 8-30 |
| `llama3.3:70b-instruct-q4_K_M` (quantised) | 48 GB | RTX 4090 24GB | 12-25 |
| `llama3.1:8b-instruct` (fallback for thin hardware) | 12 GB | any modern GPU / CPU | 50+ |

For most firm-server deployments, a single Mac Studio M2/M3 Ultra with 128–192GB
or a workstation with one RTX 4090 is enough.

---

## One-time setup

```bash
# 1. Install Ollama (macOS / Linux)
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull the model (the 70B is ~40GB download)
ollama pull llama3.3:70b
# OR for thin hardware:
ollama pull llama3.1:8b-instruct-q4_K_M

# 3. Verify Ollama is running
curl http://localhost:11434/api/tags
# Should return a JSON list of installed models.

# 4. Configure Lex-Indic to use Ollama
cat >> .env <<'ENV'
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.3:70b
ENV

# 5. Restart Lex-Indic
python3 app.py
```

Visit `/llm/status` to confirm:

```json
{
  "provider": "ollama",
  "ollama_host": "http://localhost:11434",
  "ollama_model": "llama3.3:70b",
  "ollama_reachable": true
}
```

---

## What still leaves the machine (and how to fix it)

| Component | In default Lex-Indic | With Ollama provider |
|---|---|---|
| Inference (Groq) | Groq US ❌ | Ollama localhost ✅ |
| Embeddings (Gemini) | Google US ❌ | **Still Google US** ⚠️ |
| BNS bare-act fetches (indiacode.nic.in) | n/a | n/a (read-only links the user clicks) |

The Gemini embeddings call is the **one remaining sub-processor**. Two
ways to eliminate it:

### Option A — Pre-bake all embeddings, never call Gemini at runtime

The KB is small (124 docs as of v1.4) and embeddings are cached on disk
under `data/legal_corpus/embedding_cache.json`. After the first warm-up
run the cache holds every document's embedding. Set
`GEMINI_API_KEY=` (empty) and the cache will serve every retrieval.
The only operation that still needs Gemini is embedding the **query** —
which contains the client story.

### Option B — Swap to a local embedding model

For full zero-sub-processor mode, replace Gemini embeddings with a local
`sentence-transformers/all-mpnet-base-v2` (768-dim, runs CPU-only in
~80ms per query). This requires a code change in `main.py` — search
for `GeminiEmbeddingFunction` and replace with `SentenceTransformerEmbeddingFunction`.

**Documented as v1.5 work**: full local-mode `--air-gapped` flag that
sets both `LLM_PROVIDER=ollama` and switches embeddings to local. Until
then, document Option A in your DPIA and your customer's GC.

---

## Performance characteristics

| Operation | Groq cloud | Ollama on M2 Ultra | Ollama on RTX 4090 |
|---|---|---|---|
| Cold start | 0s | 30–60s (first model load) | 30–60s |
| `/analyze` end-to-end | 6–8s | 25–45s | 35–60s |
| `/chat` reply | 1–2s | 5–10s | 8–14s |
| Concurrent requests | High | 1 per GPU | 1 per GPU |

If the customer expects multi-user concurrency, scale by running
multiple Ollama processes on different GPUs and load-balancing via a
small reverse proxy (Caddy / nginx).

---

## Verifying with the dashboard

After switching to Ollama:

- `/llm/status` returns `provider: ollama` and `ollama_reachable: true`
- Run a case at `/app` — the audit log records `model: ollama/llama3.3:70b`
- `/admin/soc2` shows AUDIT controls still passing (Ollama doesn't change
  any of them; this is a substitution of one sub-processor for none).
- `/trust` — when LLM_PROVIDER=ollama is set, the page renders the
  "leaves India" Groq stage as struck-through in a future v1.5 polish.

---

## Troubleshooting

**`Ollama call failed at http://localhost:11434: Connection refused`**
→ `ollama serve` not running. Start it in another terminal.

**Response cut off mid-sentence**
→ Increase `OLLAMA_MAX_TOKENS` in `.env` (defaults to 8192). For longer
analyses, set 12288.

**Out-of-memory error when pulling the model**
→ Use the quantised variant: `ollama pull llama3.3:70b-instruct-q4_K_M`
and update `OLLAMA_MODEL` in `.env`.

**Analysis is much worse than Groq**
→ You're probably on a smaller model (8B). The 70B model produces
results comparable to Groq's hosted version. The 8B is a stop-gap
for thin hardware.

---

## When to use Groq vs Ollama

| Scenario | Recommended |
|---|---|
| Demo / sales calls | Groq (fast) |
| Solo lawyer, no special compliance | Groq (free tier, easy) |
| NBFC, RBI-regulated entity | Ollama (data residency) |
| NALSA / SLSA deployment | Ollama (constitutional duty + zero cost) |
| Tier-1 law firm, partner-grade clients | Ollama (DPDP belt-and-suspenders) |
| Air-gapped courthouse network | Ollama (no internet at all) |

Lex-Indic is the same product in both modes. The only difference is
where the GPU sits.
