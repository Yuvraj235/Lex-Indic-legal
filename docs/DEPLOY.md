# Deploy Lex-Indic

Three documented paths, ranked by ease.  Pick one based on who's running
the instance.

| Option | Best for | Time to first request |
|---|---|---|
| **A. Local Docker** | Single user, demo on your laptop | 5 min |
| **B. fly.io (Mumbai)** | Shared demo URL surviving reboots | 20 min |
| **C. Render** | A small firm without ops capacity | 25 min |
| **D. Customer VPC (on-prem)** | NBFC / DPDP-strict deployment | 1-2 hours |

---

## A.  Local Docker — `docker compose up`

```bash
cp .env.example .env
# Fill in GEMINI_API_KEY + GROQ_API_KEY at minimum.
# Optionally: ADMIN_TOKEN, AUDIT_HASH_SALT, MAIL_PROVIDER, etc.

docker compose up -d
docker compose logs -f lex-indic    # watch boot

# Hit http://localhost:8080
```

Stop with `docker compose down`.  Your data (audit logs, generated PDFs,
the SQLite DB, leads, matters) is persisted in `./outputs/` on the host
— survives container restarts.

### With local Ollama (zero sub-processors)

```bash
# Add to .env:
#   LLM_PROVIDER=ollama
#   OLLAMA_HOST=http://ollama:11434

docker compose --profile local-llm up -d
docker compose exec ollama ollama pull llama3.3:70b
```

Requires a GPU on the host.  See `docs/OLLAMA_RUNBOOK.md` for hardware sizing.

---

## B.  fly.io — single command deploy to Mumbai

```bash
# 1. Install fly CLI
brew install flyctl

# 2. Sign in (creates a free account if needed)
fly auth login

# 3. Launch — uses fly.toml in the repo root.  Pick "Mumbai (bom)" when
#    prompted for region.  Skip the offered Postgres + Redis (we don't
#    need them at this scale).
fly launch --no-deploy

# 4. Set secrets — never put these in fly.toml
fly secrets set \
   GEMINI_API_KEY="..."        \
   GROQ_API_KEY="..."          \
   ADMIN_TOKEN="$(openssl rand -hex 16)" \
   AUDIT_HASH_SALT="$(openssl rand -hex 24)"

# 5. Optionally set mail secrets too
fly secrets set MAIL_PROVIDER=smtp SMTP_HOST=smtp.mailgun.org \
                SMTP_USERNAME=postmaster@... SMTP_PASSWORD=...

# 6. First deploy
fly deploy

# 7. Open the live URL
fly open
```

Fly gives you `https://lex-indic.fly.dev` automatically.  Add a custom
domain later via `fly certs add demo.lexindic.in`.

**Costs**: ~$5/month for the shared-cpu-1x VM + 5GB volume on the
hobby plan.  Free tier is enough to host one customer; scale up if a
second arrives.

---

## C.  Render — Blueprint deploy

1. Push the repo to GitHub.
2. Go to https://dashboard.render.com/blueprints, click "New Blueprint".
3. Pick this repo.  Render reads `render.yaml` and configures the
   service automatically.
4. In the dashboard, set the secret env vars under "Environment":
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY`
   - `ADMIN_TOKEN`
   - `AUDIT_HASH_SALT`
   - Mail vars (if using)
5. Click "Apply".

Render builds the Dockerfile, mounts a 5GB persistent disk at
`/app/outputs`, and gives you `https://lex-indic.onrender.com`.

**Costs**: $7/month for the starter plan.  Free tier sleeps after 15 min
idle — not suitable for a demo URL prospects might revisit.

---

## D.  Customer VPC (on-prem) — for DPDP-strict deployments

This is the path NBFCs / firms with India-region data-residency
mandates ask for.

**Prerequisites on the customer's host:**
- Ubuntu 22.04 LTS or RHEL 9, 4 vCPU, 8 GB RAM minimum
- Docker + Docker Compose installed
- Outbound HTTPS to either Groq+Gemini (cloud LLM) or just Gemini
  (with `LLM_PROVIDER=ollama` for inference)
- Inbound port 8080 from the firm's internal network only

**Install**:

```bash
# 1. Clone, set up .env
git clone https://github.com/Yuvraj235/Lex-Indic-legal.git
cd Lex-Indic-legal
cp .env.example .env
# Edit .env with the customer's credentials + ADMIN_TOKEN + AUDIT_HASH_SALT
# + their LAW_FIRM_NAME / LAW_FIRM_TAGLINE / etc. for the white-labelled PDF

# 2. Pre-warm the embedding cache so subsequent /analyze calls don't
#    need Gemini at runtime (Option A from OLLAMA_RUNBOOK.md)
docker compose run --rm lex-indic python tools/prewarm_embeddings.py

# 3. Start the service
docker compose up -d

# 4. Verify
curl http://localhost:8080/api/v1/health
```

**Behind a reverse proxy** (recommended):

```nginx
# /etc/nginx/sites-available/lex-indic.conf
server {
    listen 443 ssl http2;
    server_name lex.firm.example;

    ssl_certificate /etc/letsencrypt/live/lex.firm.example/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lex.firm.example/privkey.pem;

    client_max_body_size 25M;     # for PDF + image attachments

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;   # /analyze can take 8-12s on busy days
    }
}
```

**Backups**:

```bash
# Daily — back up the entire outputs/ folder (sqlite + JSON + PDFs)
0 3 * * *  cd /opt/lex-indic && \
           tar czf /backup/lex-indic-$(date +%Y%m%d).tar.gz outputs/ && \
           find /backup -name 'lex-indic-*.tar.gz' -mtime +30 -delete
```

---

## Post-deploy checklist (any path)

| | |
|---|---|
| `/api/v1/health` returns 200 | ✓ |
| `/status` shows all 6 endpoint probes green | ✓ |
| `/admin/soc2` (with token) shows 9/10 controls passing | ✓ |
| Run `/api/v1/analyze` once with a real story; PDF downloads | ✓ |
| Webhook to your Slack / Notion configured at `/status` | ✓ |
| `MONITOR_DIGEST_TO` set + cron schedules `tools/send_monitor_digest.py` | ✓ |
| Test the magic-link login at `/login` (real email lands) | ✓ |
| `tools/prewarm_embeddings.py --check` reports 0 misses | ✓ |

---

## When you actually have customers

Each customer = one new fly.io app OR one customer's docker-compose
deployment.  Don't try to multi-tenant a single instance until v2.0
(Postgres migration + proper firm isolation, planned in roadmap).

Per-customer effort to spin up:
- fly.io path: ~20 minutes
- on-prem path: 1–2 hours including reverse proxy + TLS

Each instance is identical in code; only `.env` differs (their API keys,
their letterhead, their `ADMIN_TOKEN`).  Use `fly secrets set` or
their `.env` file — never commit customer creds.
