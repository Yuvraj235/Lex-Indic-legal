---
title: Lex-Indic
emoji: ⚖️
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 8080
pinned: true
license: other
short_description: AI Junior Associate for Indian law — BNS transition engine
---

# LEX-INDIC: The BNS Transition Engine

### AI-Powered Junior Associate for Indian Law Firms

[![Status](https://img.shields.io/badge/status-v1.7-success)]()
[![Stack](https://img.shields.io/badge/stack-Flask%20%2B%20Three.js%20%2B%20ChromaDB-blue)]()
[![Tests](https://img.shields.io/badge/tests-80%20passing-success)]()
[![SOC2](https://img.shields.io/badge/SOC2-9%2F10%20controls%20passing-success)]()
[![API](https://img.shields.io/badge/API-v1%20%2B%20OpenAPI-blue)]()
[![License](https://img.shields.io/badge/license-Educational-lightgrey)]()

---

## What Is This?

Lex-Indic is a Legal Tech product built for **Indian law firms**, **legal aid clinics**, and **in-house compliance teams**.
It acts as a **Junior Associate AI** — the lawyer types in (or speaks) what a client told them,
and within seconds the system produces a **complete legal case brief with 6 outputs**, a
**downloadable PDF**, every citation **traceable to a verified knowledge base**, and a
**DPDP-compliant audit trail** of the request — all under the **Bharatiya Nyaya Sanhita (BNS) 2023**.

> India replaced the 163-year-old Indian Penal Code (IPC) with the BNS on **1 July 2024**.
> Lex-Indic helps lawyers navigate this transition instantly — without trusting a chatbot
> that hallucinates section numbers.

---

## What's New in v1.8

| Area | Change | File(s) | Why it matters |
|---|---|---|---|
| **Knowledge base** | IPC→BNS map expanded 51 → 76, with repealed-section handling (377 / 497 / 124A show "no BNS equivalent" rather than a guess) | `data/legal_corpus/ipc_bns_mapping.json`, `ipc_bns_converter.py` | Higher converter coverage; honest output on sections the BNS dropped. |
| **e-Courts** | Real, configurable CNR-lookup provider alongside the demo stub; in live mode it never falls back to demo data | `ecourts.py`, `.env.example` | `ECOURTS_PROVIDER=live` + `ECOURTS_API_KEY` returns real case status; the demo set stays clearly labelled. |
| **Multi-tenant isolation** | Per-matter routes (conflict-check, status, files, history) scoped to the caller's firm | `app.py`, `matters.py` | A firm can't read or modify another firm's matters by guessing a matter ID. |
| **Local-model tooling** | Instruction-data generator + held-out eval harness + full-pipeline answer eval; QLoRA→GGUF training recipe | `tools/generate_instruction_data.py`, `tools/eval_model.py`, `tools/eval_pipeline.py`, `training/` | Optional fine-tuned model for air-gapped (Ollama) deployments, with an objective accuracy gate. |
| **Go-live readiness** | `/admin/readiness` + `tools/readiness.py` report which subsystems are demo vs live; `/ecourts` shows a "Demo data" badge | `readiness.py`, `templates/ecourts.html` | One glance shows what's stubbed before launch; prospects never see demo data unlabelled. |

## What's New in v1.7

| Day | Feature | File | Why it matters |
|---|---|---|---|
| **21** | Dual-backend complete — matters + monitors wired to Postgres | `matters.py`, `monitors.py` | All 5 modules now transparently use Postgres/SQLite when `DATABASE_URL` is set. Dashboard shows storage backend per module. |
| **22** | Webhook retry queue — SQLite-backed exponential backoff | `webhooks.py` | Failed webhook deliveries retried up to 5× (10 s → 1 min → 5 min → 15 min → 1 h). No more silently dropped alerts. |
| **23** | Pricing tier enforcement — free / NALSA / firm / internal | `pricing.py` | Free: 3/day; NALSA panel: unlimited free; Firm API key: 200/day. 429 response includes upgrade URL. |
| **24** | Scheduled cron jobs — digest email, NALSA CSV, audit cleanup | `cron.py` | Daily digest email to registered lawyers; NALSA registry CSV for SLSA spot-checks; auto-delete audit logs > 90 days. |
| **25** | SMS/WhatsApp alerts — MSG91 (India) + Twilio + stdout | `sms.py` | WhatsApp welcome on NALSA signup; digest alerts; magic-link SMS. DLT-template registry for TRAI compliance. |

## What's New in v1.6

| Day | Feature | URL / file | Why it matters |
|---|---|---|---|
| **16** | REST API v1 + API keys + OpenAPI spec + Swagger UI | `/api/v1/docs`, `api_keys.py`, `openapi_spec.py` | A firm's IT team can integrate Lex-Indic with their case-management system. Rate-limited per key. |
| **17** | Pluggable email sender (stdout / SMTP / SES) | `mailer.py`, `tools/send_monitor_digest.py` | Login codes, monitor digests, and lead notifications land in real inboxes. |
| **18** | Dockerfile + docker-compose + fly.io + Render configs + on-prem guide | `Dockerfile`, `fly.toml`, `render.yaml`, `docs/DEPLOY.md` | Customer can `docker compose up` instead of installing Python. |
| **19** | Operator dashboard at `/dashboard` | `templates/dashboard.html` | Daily home page: KPIs, 7-day funnel, recent activity, top sources, 14-day chart. |
| **20** | Postgres-ready ORM + JSON-files → DB migration tool | `db.py`, `tools/migrate_to_postgres.py` | When the JSON registries hit ~100 users, one command moves the data. |

## What's New in v1.5 

| Day | Feature | URL | Why it matters |
|---|---|---|---|
| **1** | IPC → BNS pleading converter | `/convert` | Drag a Word doc, every IPC reference highlighted yellow + BNS equivalent inserted in red. |
| **2** | Microsoft Word add-in (Office.js) | `/addin/install` | Same converter, lives inside Word's task pane. |
| **3** | Supreme Court precedent monitor | `/monitors` | Daily digest of SC rulings touching your matter areas. |
| **4** | Hindi UI + Hindi analysis output | top-bar toggle | Bombay HC, MP HC accept Hindi pleadings under Article 348(2). |
| **5** | NALSA panel free-tier onboarding | `/nalsa` | Free for ~70K NALSA-empanelled legal-aid advocates. |
| **6** | DPDP compliance posture + .docx pack | `/trust` | 28 GC questions answered, India-region-first data flow. |
| **7** | SOC 2 Type II readiness dashboard | `/admin/soc2` | 10 live controls; continuous evidence trail. |
| **8** | Per-section bare-act deep-links | source modal | Each retrieved BNS section carries a PDF-page-hint deep-link. |
| **9** | Matter intake registry | `/matters` | Firm → Lawyer → Matter triple + conflict-of-interest check. |
| **10** | Multi-tenant auth (magic-link) | `/login` | Email + 6-digit code, HMAC session cookie, SQLite-backed users. |
| **11** | BNSS (procedure) + BSA (evidence) corpora | KB | 25 new sections: arrest, bail, search, e-court, evidence rules. |
| **12** | e-Courts CNR lookup | `/ecourts` | Look up Indian case-status by 16-char CNR; provider-pluggable. |
| **13** | Ollama local-inference path | `/llm/status` | Zero-sub-processor mode for DPDP-strict deployments. |
| **14** | Tabular contract review | `/tabular` | Upload N contracts → side-by-side clause matrix. Rent/employment/partnership libraries pre-baked. |
| **15** | Public status page + webhook event bus | `/status` | Live health, KB count, 9/10 SOC 2, signed outbound webhooks. |

## What's New in v1.2

| Feature | What it does | Why it matters |
|---|---|---|
| **3D marketing landing page** at `/` | Three.js knowledge-graph hero, scroll-reveal animations, mock provenance panel | Sales pitch site that opens the conversation before the demo |
| **Citation provenance UI** | Every "BNS Section NN" mention is a clickable badge that opens the verified KB entry. Plus a "Verified Sources" panel with relevance bars at the top of every analysis | The single feature that turns the output from "AI suggestion" into something a lawyer will sign their bar number on |
| **RAG-grounded LEXI chat** | The chat assistant now retrieves from the same KB as `/analyze` and refuses to answer if the section is out of KB — instead of hallucinating | Killed the "BNS 103 = voluntarily causing hurt" class of bug |
| **38 BNS sections** (up from 18) | Added homicide chapter, organised crime, terrorism, mob lynching, snatching, trafficking, cheating, robbery, dacoity, breach of trust, forgery, hate-speech, rioting, abetment, conspiracy | The 90% of fact patterns a criminal practitioner sees |
| **DPDP-compliant audit log** | Every `/analyze` and `/chat` request is logged JSONL with `request_id`, hashed story (SHA-256, salted), retrieved sections, latency, status. Daily rotation, append-only, fsync'd | Required before any firm GC will sign deployment |
| **Audit report CLI** | `python3 tools/audit_report.py` shows daily volume, p50/p95 latency, top retrieved sections, error rate | Compliance dashboard out of the box |
| **White-label PDF letterhead** | Five env vars (`LAW_FIRM_NAME`, `LAW_FIRM_TAGLINE`, `LAW_FIRM_SUBTITLE`, `LAW_FIRM_HEADER`, `LAW_FIRM_DISCLAIMER`) swap the Lex-Indic branding for the firm's. Engine attribution stays in the meta row for legal protection | One-line config = one new firm deployment |
| **Wider retrieval (n_results 6 → 8)** | The model now sees 8 sources per analysis, with documented headroom to bump to 12-15 on a paid Groq plan | Catches sections like BNS 115 (grievous hurt) that previously just missed the cutoff |

---

## Who Is It For?

| User | How They Use It |
|------|-----------------|
| **Criminal Lawyers** | Run instant legal triage on new client walk-ins |
| **Legal Aid Clinics** | Help under-resourced lawyers process more cases |
| **Junior Associates** | Get AI guidance on new BNS section numbers with full citation trace |
| **Law Firm Partners** | Review and sign pre-drafted FIRs and Legal Notices on firm letterhead |
| **In-house Compliance** (NBFC, fintech) | Triage cheating/forgery complaints under BNS 318 |
| **Clients (Self-help)** | Understand their legal position before hiring a lawyer |
| **Physically Handicapped Users** | Full voice input/output support — no typing needed |

---

## Features at a Glance

| Feature | Description |
|---------|-------------|
| **6-Section Case Analysis** | Advisory · Legal Analysis · Strategy · Draft FIR · Legal Notice · Police Report |
| **Verified Sources Panel** | Shows the 8 KB entries the system retrieved, with relevance bars. Click to view the verified bare-act-style entry |
| **Inline Citation Badges** | Every BNS section in the output is a clickable badge linking to its source. Out-of-KB sections stay plain text — your visual signal of model drift |
| **PDF Case Brief** | Branded 9-page downloadable PDF with cover page, watermark, and disclaimer |
| **White-label Letterhead** | Configure the PDF to ship under any firm's brand via `.env` |
| **Audit Log** | Every request gets a `request_id`. JSONL logs, daily rotation, hashed PII, no raw stories stored |
| **Audit Report CLI** | `tools/audit_report.py` for daily / weekly summaries |
| **3D Landing Page** | Three.js knowledge-graph hero at `/` with scroll-triggered animations |
| **Web Interface** | Browser-based UI, no terminal needed, works on any device |
| **LEXI Chat Assistant** | RAG-grounded — refuses to invent sections it doesn't have |
| **Voice Input/Output** | Web Speech API for hands-free dictation + reply readback |
| **Edit & Supplement** | Modify the story, add facts, attach evidence, re-run |
| **File Attachments** | Upload PDFs, JPGs, PNGs — Gemini Vision extracts text |
| **Find Nearby Police Station** | Browser geolocation to find the nearest station on Google Maps |
| **Find a Lawyer** | Links to LawRato, Vakil Search, Legistify, Bar Council, NALSA |
| **Case History** | Sidebar with all past analyses, click to reload |
| **Role-Neutral Analysis** | Works for complainants AND respondents equally |

---

## How Does It Work?

```
STEP 1: LAWYER INPUTS THE CLIENT STORY
  The lawyer types, pastes, or SPEAKS the client's raw story.
  Optionally attaches evidence files (PDF reports, photos, screenshots).

        |
        v

STEP 2: RAG SEARCH (Retrieval-Augmented Generation)
  The system searches a curated knowledge base of:
    - 38 BNS sections (criminal law provisions)
    - 51 IPC-to-BNS mapping entries
    - 7 Supreme Court landmark judgments
    - 3 Legal circulars (MHA, NHRC, Supreme Court)
  Total: 99 indexed documents, embedded via Gemini.
  Finds the TOP 8 most relevant entries for THIS specific case.
  Returns the structured source list to the UI for citation provenance.

        |
        v

STEP 3: AI ANALYSIS (Groq Llama-3.3-70B)
  The retrieved laws + client story are sent to the AI with strict instructions:
  "Act as a Senior Indian Criminal Lawyer with 20+ years experience.
   Respond only with verified BNS sections from the provided context.
   If unsure, say 'Further legal research required' — never invent."
  Temperature: 0.2 (precise, factual output -- no creative guesses).

        |
        v

STEP 4: SIX OUTPUTS GENERATED

  Section 1: IMMEDIATE CLIENT ADVISORY (red)
    Urgent safety steps the client must take RIGHT NOW.

  Section 2: BNS LEGAL ANALYSIS (blue)
    A. Sections the CLIENT can use (in their favour)
    B. Sections the OPPOSING PARTY may use (against them)
    Each with: BNS number, old IPC equivalent, punishment, bailable status.

  Section 3: CASE STRATEGY & STRENGTH (purple)
    STRONG / MODERATE / WEAK assessment with evidence checklist.

  Section 4: DRAFT FIR or REBUTTAL STATEMENT (green)
    If complainant: complete FIR ready to file.
    If respondent: rebuttal/defence statement.

  Section 5: DRAFT LEGAL NOTICE (teal)
    Formal legal notice with demands and 15-day deadline.

  Section 6: POLICE HELP REPORT (orange)
    Plain-language summary for the Station House Officer.

        |
        v

STEP 5: VERIFIED SOURCES PANEL + CITATION BADGES
  Above the analysis: 8 source cards (rank, kind, title, IPC replaced,
  punishment, relevance bar). Click any card for the verified KB text.
  Inside the analysis: every "BNS Section NN" is a clickable badge.

        |
        v

STEP 6: PDF CASE BRIEF + AUDIT LOG
  9-page branded PDF (firm letterhead if configured).
  Audit record written to outputs/audit/audit-YYYY-MM-DD.log
  with request_id, hashed story, retrieved sections, latency, status.
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **AI Model** | Groq Llama-3.3-70B | Fast, high-quality legal reasoning |
| **Embeddings** | Google Gemini text-embedding-001 | Semantic search across law sections |
| **Vector Database** | ChromaDB (in-memory) | RAG retrieval of relevant BNS sections |
| **Web Framework** | Flask (Python 3.10+) | Lightweight web server, REST API |
| **Frontend (App)** | Bootstrap 5 + Bootstrap Icons | Responsive intake/results UI |
| **Frontend (Landing)** | Three.js (ES modules from CDN) | 3D knowledge-graph hero |
| **PDF Generator** | fpdf2 | 9-page branded case brief PDF |
| **File Extraction** | pdfplumber + Gemini Vision | Extract text from uploaded PDFs and images |
| **Voice Input** | Web Speech API (browser) | Speech-to-text in Indian English |
| **Voice Output** | SpeechSynthesis API (browser) | Text-to-speech with female voice |
| **Audit Storage** | JSONL append-only files | Daily rotation, fsync'd, no DB needed |
| **Secret Management** | python-dotenv | API keys stay in .env, never in code |

---

## Project Structure

```
legal_ai/
|
|-- main.py                          <-- Core legal triage engine
|-- app.py                           <-- Flask web server (routes, /analyze, /chat, audit hooks)
|-- pdf_generator.py                 <-- PDF Case Brief generator (white-label via .env)
|-- audit.py                         <-- DPDP audit logger (JSONL, hashed PII)
|-- requirements.txt
|-- .env                             <-- API keys + branding + audit salt (never committed)
|-- .env.example                     <-- Template for the above
|-- .gitignore
|-- README.md
|
|-- data/
|   |-- bns_knowledge_base.py        <-- 38 curated BNS sections
|   |-- download_legal_corpus.py     <-- Corpus loader (SC cases, circulars, mappings)
|   |-- legal_corpus/
|       |-- ipc_bns_mapping.json     <-- 51 IPC-to-BNS section mappings
|       |-- embedding_cache.json     <-- Cached embeddings (auto-generated)
|       |-- official_sources.txt
|       |-- case_summaries/          <-- 7 Supreme Court landmark cases
|       |-- circulars/               <-- 3 legal circulars (MHA, SC, NHRC)
|
|-- templates/
|   |-- landing.html                 <-- 3D marketing landing page (/)
|   |-- index.html                   <-- Intake/results UI (/app)
|
|-- static/
|   |-- style.css                    <-- Brand colours, source cards, citation badges
|
|-- tools/
|   |-- audit_report.py              <-- Daily/weekly audit summary CLI
|
|-- outputs/                         <-- Generated artefacts (gitignored)
    |-- case_analysis_YYYYMMDD_HHMMSS.txt
    |-- CaseBrief_YYYYMMDD_HHMMSS.pdf
    |-- audit/
        |-- audit-YYYY-MM-DD.log     <-- JSONL audit trail (daily rotation)
```

---

## Setup & Running

### Prerequisites
- Python 3.10+
- A Gemini API key (free): https://aistudio.google.com/app/apikey
- A Groq API key (free): https://console.groq.com/keys

### 1. Clone the repository
```bash
git clone https://github.com/Yuvraj235/Lex-Indic-legal.git
cd Lex-Indic-legal
```

### 2. Install dependencies
```bash
pip3 install -r requirements.txt
```

### 3. Configure `.env`

Minimum:
```bash
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

Optional — white-label the PDF for a specific firm:
```bash
LAW_FIRM_NAME=SINGHANIA & PARTNERS
LAW_FIRM_TAGLINE=ADVOCATES & SOLICITORS
LAW_FIRM_SUBTITLE=Mumbai · Delhi · Bengaluru
LAW_FIRM_HEADER=Singhania & Partners | BNS Case Brief | CONFIDENTIAL
LAW_FIRM_DISCLAIMER=Prepared by Singhania & Partners as a draft. Must be reviewed by the assigned advocate before filing.
```

Optional — production audit salt (REQUIRED for any production deployment):
```bash
AUDIT_HASH_SALT=your-unique-deployment-salt-here
AUDIT_LOG_DIR=outputs/audit          # default; override to ship logs elsewhere
```

### 4. Run the web server
```bash
python3 app.py                    # HTTP on :8080 (default)
python3 app.py --https            # HTTPS on :8443 (required for the Word add-in)
```
Then open: **http://localhost:8080** (or **https://localhost:8443** for the add-in)

### 5. Run the test suite (recommended after any change)
```bash
pip3 install -r requirements-dev.txt
python3 -m pytest tests/
```
94 tests, runs in <2 seconds, zero network calls.  See [`tests/README.md`](tests/README.md) for details.

### 6. Share a public demo URL
```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:8080
# Ephemeral URL printed in the output. For a stable demo URL that
# survives reboots, follow docs/STABLE_TUNNEL.md.
```

The Word add-in install instructions live at `/addin/install` once the
HTTPS server is up.  Generate the self-signed dev cert once with:
```bash
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/dev-key.pem -out certs/dev-cert.pem \
  -days 365 -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

**First startup:** ~30 seconds (generates and caches embeddings for 99 documents)
**Subsequent startups:** ~10 seconds (embeddings loaded from disk cache)

### 5. (Optional) Run the terminal engine directly
```bash
python3 main.py
```

### 6. (Optional) Read the audit log
```bash
python3 tools/audit_report.py            # today (UTC)
python3 tools/audit_report.py 2026-05-09 # specific date
python3 tools/audit_report.py --week     # last 7 days, aggregated
python3 tools/audit_report.py --tail 20  # last 20 raw records
```

---

## How to Use the Web Interface

### The Landing Page (`/`)
The marketing site explains the product to a new prospect. Three.js 3D hero,
animated stats, mock Verified Sources panel, compliance pillars, CTA to the
actual engine at `/app`.

### Analyze a Case (`/app`)
1. Open **http://localhost:8080/app** in your browser (or click "Try the engine" from `/`)
2. Type or paste the client's story in the text area
3. (Optional) Click **"Attach Evidence"** to upload PDF reports or photos
4. Click **"Run Legal Analysis"** — wait ~7 seconds
5. The **Verified Sources** panel appears at the top with 8 cards
6. All 6 sections appear as colour-coded accordion cards below
7. Inside the legal analysis, every "BNS Section NN" is a **clickable citation badge**
8. Click any source card or citation badge to view the verified KB text
9. Click **"Download PDF Case Brief"** for the printable 9-page PDF

### Edit & Re-run
1. After getting results, click **"Edit & Supplement"**
2. Modify the client story or add new facts in the "Additional Information" box
3. Attach new evidence files if needed
4. Click **"Re-run Analysis with Changes"** for an updated analysis

### Use Voice (Accessibility)
1. Click the **microphone button** next to "Client's Statement" to dictate
2. In the LEXI chat, click the **mic icon** to ask questions by voice
3. LEXI reads all chat replies aloud automatically
4. Toggle **"Voice On/Off"** in the chat header to mute

### LEXI Chat Assistant
1. Click the **LEXI bubble** (bottom-right corner)
2. Ask questions like: "What is BNS Section 304?" or "What replaced IPC 498A?"
3. **LEXI is RAG-grounded** — if the section isn't in the KB, it refuses and
   points you to the official bare act, instead of inventing a number
4. Below each reply, a **Sources** strip shows the 4 KB entries LEXI consulted
5. For situation-based questions, LEXI suggests using the full Case Analysis

### Find Help Near You
After any analysis, scroll down to **"Find Help Near You"**:
- **Nearest Police Station** — uses your browser location to open Google Maps
- **Find a Lawyer** — links to LawRato, Vakil Search, Legistify, Bar Council of India, NALSA (free legal aid)

---

## The Three Things That Make This Sellable to a Real Firm

### 1. Citation Provenance — every claim traceable

The model never gets to invent law. The Verified Sources panel above the analysis
shows the 8 KB entries the RAG system actually retrieved, with their relevance
scores. Inside the legal analysis, every "BNS Section NN" mention is wrapped in
a citation badge. Sections that weren't retrieved stay plain text — your visual
signal that the model has wandered off-source.

A senior advocate audits the output by clicking 8 cards. Trust restored.

### 2. Audit Trail — DPDP Act 2023 compliance built in

Every `/analyze` and `/chat` request writes a JSONL record:

```json
{
  "request_id": "d761bc8f-2649-4914-9fff-7441102a69e1",
  "ts": "2026-05-09T14:07:44.223+00:00",
  "endpoint": "/analyze",
  "client_ip": "127.0.0.1",
  "story_hash": "sha256:9a9ef4d43f4c3c3bafaf8caa87eaacda",
  "story_length": 208,
  "sources": ["bns_351","bns_115","bns_78","bns_66","bns_356","bns_125","bns_336","bns_75"],
  "model": "llama-3.3-70b-versatile",
  "status": "ok",
  "duration_ms": 12391,
  "response_chars": 6826,
  "pdf_filename": "CaseBrief_20260509_193744.pdf"
}
```

The raw client story is **never** logged — only its salted SHA-256 hash, so
duplicate detection works without storing PII. Files rotate daily and are
gitignored. One cron job ships them to your SIEM.

### 3. White-label PDFs — one env edit per firm

```bash
LAW_FIRM_NAME=KHAITAN & CO
LAW_FIRM_TAGLINE=ADVOCATES & SOLICITORS
LAW_FIRM_SUBTITLE=Mumbai · Delhi · Bengaluru · Kolkata
LAW_FIRM_DISCLAIMER=Prepared by Khaitan & Co as a draft.
```

Restart the server. Every PDF from that point ships under their brand. The
"Lex-Indic BNS Transition Engine" attribution stays in the meta row — that's
deliberate. It disclaims AI authorship and protects the firm legally.

---

## Key Legal Facts Built Into The System

### The BNS Transition
- **Cases before 1 July 2024** → Charged under old IPC
- **Cases from 1 July 2024 onwards** → Charged under new BNS

### Important Supreme Court Cases Pre-loaded
| Case | What It Means |
|------|---------------|
| **Arnesh Kumar v Bihar (2014)** | Police CANNOT auto-arrest under BNS 85. Must serve notice first. |
| **Lalita Kumari v UP (2014)** | Police MUST register FIR for cognizable offences. No excuses. |
| **Vishaka v Rajasthan (1997)** | Workplace harassment: file with ICC + BNS 75 criminal case together. |
| **Pawan Kumar v Haryana (2003)** | Dowry death: harassment + death within 7 years = accused must prove innocence. |
| **Tehseen Poonawalla v UoI (2018)** | Mob lynching directives — implemented in BNS 103(2). |

### Emergency Numbers
- Police: **100**
- Women Helpline: **1091**
- Emergency: **112**

---

## API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | 3D marketing landing page |
| `/app` | GET | Intake form + results UI |
| `/analyze` | POST | Run full legal analysis. Returns `sections`, `sources`, `pdf_filename`, `request_id` |
| `/chat` | POST | RAG-grounded LEXI assistant. Returns `reply`, `sources`, `request_id` |
| `/history` | GET | List of past case analyses |
| `/load/<filename>` | GET | Load a saved case by filename |
| `/download/<filename>` | GET | Download a generated PDF |
| `/convert` | GET | IPC → BNS converter UI (drag-drop) |
| `/convert/text` | POST | Convert pasted text (also called by the Word add-in) |
| `/convert/upload` | POST | Convert an uploaded `.docx`, returns a converted filename |
| `/convert/download/<filename>` | GET | Download a converted `.docx` |
| `/addin/install` | GET | Word add-in sideload instructions |
| `/addin/manifest.xml` | GET | OfficeApp manifest (download into Word) |
| `/addin/taskpane` | GET | Task pane HTML loaded inside Word |
| `/addin/commands` | GET | Required Office commands stub |
| `/monitors` | GET | SC precedent monitor UI |
| `/monitors/api/matters` | GET/POST/DELETE | Register & manage watched matters |
| `/monitors/api/digest` | GET | Run today's digest (JSON) |
| `/monitors/digest.txt` | GET | Plain-text digest (pipe to cron / mail) |
| `/i18n/strings.json` | GET | Hindi + English UI strings table |
| `/nalsa` | GET | NALSA free-tier landing |
| `/nalsa/api/register` | POST | Self-claim NALSA panel registration |
| `/nalsa/api/export.csv` | GET | SLSA spot-check CSV (token-gated) |
| `/trust` | GET | DPDP compliance posture + 28-question Q&A |
| `/trust/pack.docx` | GET | Auto-generated .docx compliance pack |
| `/trust/posture.json` | GET | Machine-readable posture for procurement tools |
| `/admin/soc2` | GET | SOC 2 readiness dashboard (token-gated) |
| `/admin/soc2/summary.json` | GET | JSON control results |
| `/admin/soc2/snapshot` | POST | Save evidence snapshot to outputs/soc2_evidence/ |
| `/matters` | GET | Firm/lawyer/matter intake registry |
| `/matters/api/firms` | GET/POST | Firm CRUD |
| `/matters/api/lawyers` | GET/POST | Lawyer CRUD |
| `/matters/api/matters` | GET/POST | Matter CRUD with conflict-of-interest check |
| `/matters/api/conflict-check` | POST | Pre-create conflict scan |
| `/login` | GET | Magic-link login page |
| `/auth/code` | POST | Issue 6-digit login code |
| `/auth/verify` | POST | Consume code, set session cookie |
| `/auth/me` | GET | Current authenticated user |
| `/auth/logout` | POST | Clear session cookie |
| `/auth/bind-firm` | POST | Bind user to a firm (multi-tenant boundary) |
| `/ecourts` | GET | CNR lookup UI |
| `/ecourts/api/lookup/<cnr>` | GET | Fetch case-status by CNR |
| `/llm/status` | GET | Active LLM provider + reachability |
| `/tabular` | GET | Tabular contract review UI |
| `/tabular/api/compare` | POST | Compare N contracts × M clauses |
| `/status` | GET | Public status page (auto-refreshes) |
| `/status.json` | GET | Machine-readable health for monitoring |
| `/webhooks/api/subscriptions` | GET/POST | Register webhook URLs |
| `/webhooks/api/subscriptions/<id>` | DELETE | Remove subscription |
| `/webhooks/api/deliveries` | GET | Recent delivery log |
| `/try` | GET | Lead-capture page for new prospects |
| `/try/submit` | POST | Save lead, fire `lead.captured` webhook |
| `/try/api/leads` | GET | Admin: list captured leads (token-gated) |
| `/dashboard` | GET | Operator dashboard — KPIs + funnel + activity (token-gated) |
| `/dashboard/data.json` | GET | JSON aggregate for the dashboard |
| `/db/health` | GET | Postgres health probe (token-gated) |
| `/api/v1/docs` | GET | Swagger UI for the JSON API |
| `/api/v1/openapi.json` | GET | OpenAPI 3.0 spec |
| `/api/v1/health` | GET | Liveness probe (no auth) |
| `/api/v1/analyze` | POST | Run analysis (X-Api-Key required) |
| `/api/v1/convert/text` | POST | IPC→BNS regex conversion |
| `/api/v1/sections` | GET | Browse the KB |
| `/api/v1/ecourts/lookup/<cnr>` | GET | CNR lookup |
| `/api/v1/monitors/digest` | GET | Today's SC precedent digest |
| `/api/v1/leads` | POST | External lead capture |
| `/admin/api-keys` | GET / POST | Manage API keys |
| `/admin/api-keys/<id>` | DELETE | Revoke a key |

Every successful and every error response carries an `X-Request-Id`-like
field in the JSON body, so users can quote it in support tickets and ops
can grep the audit log to find the exact request.

---

## BNS Sections in the Knowledge Base (38)

**Sexual offences:** 64, 74, 75, 77, 78, 79
**Dowry / matrimonial:** 80, 83, 84, 85
**Homicide:** 100, 101, 103, 103(2), 105, 106, 109
**Mob lynching / organised crime / terror:** 103(2), 111, 113
**Hurt / endangerment:** 115, 125
**Wrongful confinement:** 126
**Kidnapping / trafficking:** 137, 140, 143
**Public order:** 191, 196
**Theft / robbery / dacoity / snatching:** 303, 304, 309, 310
**Cheating / forgery / breach of trust:** 316, 318, 336
**Defamation / intimidation:** 351, 356
**Inchoate offences:** 45, 61

Plus 51 IPC→BNS mapping entries, 7 Supreme Court landmark cases, and 3 legal
circulars (MHA, SC, NHRC) — all retrievable via the same RAG pipeline.

---

## Disclaimer

> **This software generates draft documents for review by a licensed Advocate.**
> All outputs must be verified by a practising Indian lawyer before filing.
> This is a legal drafting assistance tool — not a substitute for legal advice.
> Lex-Indic is not a law firm and does not provide legal representation.

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| **Phase 1** | Legal Triage Engine (6 outputs, RAG, role-neutral) | Done |
| **Phase 2** | PDF Case Brief Generator | Done |
| **Phase 3** | Web UI, voice, file attachments, edit/supplement | Done |
| **v1.1** | RAG-grounded LEXI chat, KB expansion (18 → 38 sections) | Done |
| **v1.2** | Citation provenance UI, audit log, white-label PDFs, 3D landing page | Done |
| **v1.3** | IPC→BNS converter (web + Word add-in) — the Legora wedge | Done |
| **v1.4** | SC precedent monitor + Hindi UI/output + NALSA tier + DPDP trust page + SOC 2 dashboard | Done |
| **v1.5** | Deep-links, matter intake, multi-tenant auth, BNSS+BSA, e-Courts, Ollama, tabular review, status+webhooks | Done |
| **v1.6** | REST API + OpenAPI, email sender (SES/SMTP), Dockerfile + fly.io + Render, operator dashboard, Postgres-ready ORM | Done |
| **v1.7** | Dual-backend complete, webhook retry queue, pricing tiers, cron jobs, SMS/WhatsApp (MSG91 + Twilio) | Done |
| **v1.8** | Optional local-model fine-tuning + evaluation tooling (`tools/`, `training/`) for air-gapped Ollama deployments; KB expansion (76 IPC→BNS mappings); e-Courts live provider; multi-tenant isolation hardening; go-live readiness audit. | In progress |
| **v2.0** | Cut over each JSON-registry module to Postgres (using db.py); formal SOC 2 Type II via Vanta/Drata | Planned |
| **v2.1** | BNS full-358 corpus, regional languages (Marathi, Tamil, Bengali), AppSource Word add-in submission | Planned |
| **v2.0** | Postgres + multi-tenant auth, India-region deployment guide, BNSS + BSA corpora | Planned |
| **v2.1** | Hindi + regional language support, on-prem Llama-3.3-70B via Ollama | Planned |

---

## License

This project is for educational and demonstration purposes.

## Author

**Yuvraj Pratap Singh**
- GitHub: [@Yuvraj235](https://github.com/Yuvraj235)
- Repository: [Lex-Indic-legal](https://github.com/Yuvraj235/Lex-Indic-legal)
