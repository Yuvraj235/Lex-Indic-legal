# LEX-INDIC: The BNS Transition Engine

### AI-Powered Junior Associate for Indian Law Firms

---

## What Is This?

Lex-Indic is a Legal Tech product built for **Indian law firms** and **legal aid clinics**.
It acts as a **Junior Associate AI** -- the lawyer types in (or speaks) what a client told them,
and within 60 seconds the system produces a **complete legal case brief with 6 outputs**, a
**downloadable PDF**, and actionable next steps -- all under the **Bharatiya Nyaya Sanhita (BNS) 2023**.

> India replaced the 163-year-old Indian Penal Code (IPC) with the BNS on **1 July 2024**.
> Lex-Indic helps lawyers navigate this transition instantly.

---

## Who Is It For?

| User | How They Use It |
|------|----------------|
| **Criminal Lawyers** | Run instant legal triage on new client walk-ins |
| **Legal Aid Clinics** | Help under-resourced lawyers process more cases |
| **Junior Associates** | Get AI guidance on new BNS section numbers |
| **Law Firm Partners** | Review and sign pre-drafted FIRs and Legal Notices |
| **Clients (Self-help)** | Understand their legal position before hiring a lawyer |
| **Physically Handicapped Users** | Full voice input/output support -- no typing needed |

---

## Features at a Glance

| Feature | Description |
|---------|-------------|
| **6-Section Case Analysis** | Advisory, Legal Analysis, Strategy, Draft FIR, Legal Notice, Police Report |
| **PDF Case Brief** | Branded 9-page downloadable PDF with cover page and disclaimer |
| **Web Interface** | Browser-based UI -- no terminal needed, works on any device |
| **LEXI Chat Assistant** | Ask quick questions about any BNS section via chat |
| **Voice Input (Speech-to-Text)** | Dictate client stories and chat questions hands-free |
| **Voice Output (Text-to-Speech)** | LEXI reads replies aloud (female voice, Indian English) |
| **Edit & Supplement** | Edit the story, add new facts, attach evidence, and re-run analysis |
| **File Attachments** | Upload PDF reports, JPG/PNG screenshots -- AI extracts text automatically |
| **Find Nearby Police Station** | Browser geolocation to find nearest police station on Google Maps |
| **Find a Lawyer** | Links to LawRato, Vakil Search, Legistify, Bar Council, NALSA |
| **Case History** | Sidebar with all past analyses, click to reload any case |
| **Role-Neutral Analysis** | Works for complainants (victims) AND respondents (accused) equally |

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
    - 18 BNS sections (criminal law provisions)
    - 51 IPC-to-BNS mapping entries
    - 7 Supreme Court landmark judgments
    - 3 Legal circulars (MHA, NHRC, Supreme Court)
  Finds the TOP 6 most relevant laws for THIS specific case.

        |
        v

STEP 3: AI ANALYSIS (Groq Llama-3.3-70B)
  The retrieved laws + client story are sent to the AI with strict instructions:
  "Act as a Senior Indian Criminal Lawyer with 20+ years experience.
   Respond only with verified BNS sections from the provided context."
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

STEP 5: PDF CASE BRIEF
  9-page branded PDF with all 6 sections, cover page, and disclaimer.
  Download instantly from the browser.
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **AI Model** | Groq Llama-3.3-70B | Fast, high-quality legal reasoning |
| **Embeddings** | Google Gemini text-embedding-001 | Semantic search across law sections |
| **Vector Database** | ChromaDB (in-memory) | RAG retrieval of relevant BNS sections |
| **Web Framework** | Flask (Python) | Lightweight web server, REST API |
| **PDF Generator** | fpdf2 | 9-page branded case brief PDF |
| **File Extraction** | pdfplumber + Gemini Vision | Extract text from uploaded PDFs and images |
| **Voice Input** | Web Speech API (browser) | Speech-to-text in Indian English |
| **Voice Output** | SpeechSynthesis API (browser) | Text-to-speech with female voice |
| **Frontend** | Bootstrap 5 + Bootstrap Icons (CDN) | Responsive UI, no npm/Node needed |
| **Secret Management** | python-dotenv | API keys stay in .env, never in code |

---

## Project Structure

```
legal_ai/
|
|-- main.py                          <-- Core legal triage engine (Phase 1)
|-- app.py                           <-- Flask web server (Phase 3)
|-- pdf_generator.py                 <-- PDF Case Brief generator (Phase 2)
|-- requirements.txt                 <-- Python dependencies
|-- .env                             <-- API keys (never committed)
|-- .gitignore
|-- README.md                        <-- This file
|
|-- data/
|   |-- bns_knowledge_base.py        <-- 18 curated BNS sections
|   |-- download_legal_corpus.py     <-- Corpus downloader (SC cases, circulars, mappings)
|   |-- legal_corpus/
|       |-- ipc_bns_mapping.json     <-- 51 IPC-to-BNS section mappings
|       |-- embedding_cache.json     <-- Cached embeddings (auto-generated)
|       |-- official_sources.txt     <-- Links to official government PDFs
|       |-- case_summaries/          <-- 7 Supreme Court landmark cases
|       |-- circulars/               <-- 3 legal circulars (MHA, SC, NHRC)
|
|-- templates/
|   |-- index.html                   <-- Single-page web UI
|
|-- static/
|   |-- style.css                    <-- Brand colours, section cards, voice buttons
|
|-- outputs/                         <-- Generated analyses and PDFs (gitignored)
    |-- case_analysis_YYYYMMDD_HHMMSS.txt
    |-- CaseBrief_YYYYMMDD_HHMMSS.pdf
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

### 3. Add your API keys
Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

### 4. Run the web server
```bash
python3 app.py
```
Then open: **http://localhost:8080**

**First startup:** ~30 seconds (generates and caches embeddings for 79 law documents)
**Subsequent startups:** ~10 seconds (embeddings loaded from disk cache)

### 5. (Optional) Run the terminal engine directly
```bash
python3 main.py
```

---

## How to Use the Web Interface

### Analyze a Case
1. Open **http://localhost:8080** in your browser
2. Type or paste the client's story in the text area
3. (Optional) Click **"Attach Evidence"** to upload PDF reports or photos
4. Click **"Run Legal Analysis"** -- wait ~15 seconds
5. All 6 sections appear as colour-coded accordion cards
6. Click **"Download PDF Case Brief"** for a printable 9-page PDF

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
2. Ask questions like: "What is BNS Section 85?" or "What replaced IPC 498A?"
3. For situation-based questions, LEXI will suggest using the full Case Analysis

### Find Help Near You
After any analysis, scroll down to **"Find Help Near You"**:
- **Nearest Police Station** -- uses your browser location to open Google Maps
- **Find a Lawyer** -- links to LawRato, Vakil Search, Legistify, Bar Council of India, NALSA (free legal aid)

---

## Key Legal Facts Built Into The System

### The BNS Transition
- **Cases before 1 July 2024** --> Charged under old IPC
- **Cases from 1 July 2024 onwards** --> Charged under new BNS

### Important Supreme Court Cases Pre-loaded
| Case | What It Means |
|------|---------------|
| **Arnesh Kumar v Bihar (2014)** | Police CANNOT auto-arrest under BNS 85. Must serve notice first. |
| **Lalita Kumari v UP (2014)** | Police MUST register FIR for cognizable offences. No excuses. |
| **Vishaka v Rajasthan (1997)** | Workplace harassment: file with ICC + BNS 75 criminal case together. |
| **Pawan Kumar v Haryana (2003)** | Dowry death: harassment + death within 7 years = accused must prove innocence. |

### Emergency Numbers (shown in Police Station finder)
- Police: **100**
- Women Helpline: **1091**
- Emergency: **112**

---

## API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Main web interface |
| `/analyze` | POST | Run full legal analysis (accepts JSON or multipart with files) |
| `/chat` | POST | LEXI chat assistant (quick BNS questions) |
| `/history` | GET | List of past case analyses |
| `/load/<filename>` | GET | Load a saved case by filename |
| `/download/<filename>` | GET | Download a generated PDF |

---

## Screenshots

### Main Interface
- Navy + gold branded design
- Left sidebar with case history
- Right panel with intake form, analysis results, or edit panel

### Analysis Results
- 6 colour-coded accordion sections (red, blue, purple, green, teal, orange)
- Case strength badge (STRONG/MODERATE/WEAK)
- PDF download button
- "Edit & Supplement" button for iterating

### LEXI Chat
- Floating chat bubble (bottom-right)
- Voice input mic button
- Voice output toggle (on/off)
- Redirect to full analysis when needed

---

## Disclaimer

> **This software generates draft documents for review by a licensed Advocate.**
> All outputs must be verified by a practising Indian lawyer before filing.
> This is a legal drafting assistance tool -- not a substitute for legal advice.
> Lex-Indic is not a law firm and does not provide legal representation.

---

## Phase Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| **Phase 1** | Legal Triage Engine (6 outputs, RAG, role-neutral) | Done |
| **Phase 2** | PDF Case Brief Generator (9-page branded PDF) | Done |
| **Phase 3** | Web UI (Flask, Bootstrap, case history, chat assistant) | Done |
| **Phase 3+** | Voice support, file attachments, edit/supplement, police/lawyer finder | Done |
| **Phase 4** | Hindi + regional language support | Planned |
| **Phase 5** | Multi-user login + cloud deployment | Planned |

---

## License

This project is for educational and demonstration purposes.

## Author

**Yuvraj Pratap Singh**
- GitHub: [@Yuvraj235](https://github.com/Yuvraj235)
