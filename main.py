"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          LEX-INDIC: THE BNS TRANSITION ENGINE — v1.0                        ║
║          Your AI-Powered Junior Associate for Indian Criminal Law            ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS FILE DOES (For Investor Presentations):
─────────────────────────────────────────────────
1.  LOADS the BNS Knowledge Base into ChromaDB (an in-memory vector database).
2.  SEARCHES the knowledge base to find the most relevant BNS sections for
    the client's specific situation (this is called RAG — Retrieval-Augmented
    Generation). This prevents the AI from "hallucinating" wrong law sections.
3.  SENDS the client's story + retrieved law sections to Google Gemini 2.0 Flash,
    instructing it to respond as a Senior Indian Criminal Lawyer.
4.  GENERATES five outputs:
    (a) Immediate Client Advisory  — safety + evidence collection steps
    (b) BNS Legal Analysis         — applicable charges with section numbers
    (c) Draft FIR                  — ready-to-file police complaint
    (d) Legal Notice               — formal letter to the opposing party
    (e) Police Help Report         — plain-language narrative for the police
"""

# ─── STANDARD LIBRARY ────────────────────────────────────────────────────────
import os
import sys
import time
import json
import hashlib
import textwrap
from datetime import datetime
from pathlib import Path

# ─── THIRD-PARTY LIBRARIES ───────────────────────────────────────────────────
# python-dotenv: Loads our API key from the .env file (keeps secrets safe)
from dotenv import load_dotenv

# google-generativeai: Used ONLY for embeddings (RAG vector search)
import google.generativeai as genai

# groq: Used for AI text generation (free tier, very fast)
from groq import Groq

# chromadb: In-memory vector database for our legal knowledge base (RAG)
import chromadb

# rich: Beautiful terminal output (makes it look professional in VS Code)
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box

# ─── LOCAL MODULES ────────────────────────────────────────────────────────────
# Our curated BNS knowledge base (the 'legal brain' we built)
import data.bns_knowledge_base as kb
# Case summaries, circulars, and IPC-BNS mapping corpus
import data.download_legal_corpus as corpus

# ─── INITIALIZATION ───────────────────────────────────────────────────────────
load_dotenv()                          # Read the .env file into environment
console = Console(width=100)           # Rich console for beautiful terminal output


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1A: CONFIGURE GEMINI (Embeddings only — RAG search)
# ══════════════════════════════════════════════════════════════════════════════
def configure_gemini_embeddings():
    """Configures Gemini API for embeddings only (RAG vector search)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_gemini_api_key_here":
        genai.configure(api_key=api_key)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1B: CONFIGURE GROQ (Text generation — the AI Legal Brain)
# ══════════════════════════════════════════════════════════════════════════════

# The SYSTEM INSTRUCTION defines LEXI's permanent role as a Senior Indian Lawyer.
# This runs before every query and cannot be overridden by the user prompt.
LEXI_SYSTEM_PROMPT = """You are LEXI, an expert AI Legal Assistant for Indian law firms,
specializing in Indian Criminal Law under the BHARATIYA NYAYA SANHITA (BNS) 2023.

Your role is that of a Senior Indian Criminal Lawyer with 20+ years of experience
in the Supreme Court and High Courts of India. You are meticulous, authoritative,
and impartial — you serve the CLIENT who has come to you, regardless of whether
they are a complainant (victim filing a case) or a respondent (defending against
allegations or filing a counter-case).

CRITICAL — READ THE CLIENT'S ROLE FIRST:
Before drafting anything, determine whether the client is:
  (A) COMPLAINANT / VICTIM — they were harmed and want to file a case
  (B) RESPONDENT / ACCUSED — someone filed or may file a case against them,
      OR they want to defend themselves and/or file a counter-complaint
  (C) THIRD PARTY — family member, witness, or person seeking information

ALL your output must be tailored to HELP THE CLIENT based on their role.
- For a COMPLAINANT: show sections they can file under, how to build their case.
- For a RESPONDENT: show sections being used against them AND their defences,
  bail provisions, and any counter-claims they can legitimately file.
- NEVER apply sections against the client who has come to seek help.

STRICT RULES YOU MUST FOLLOW:
1. ONLY cite BNS sections (2023). ALWAYS mention the old IPC section it replaced —
   this is critical because lawyers are still transitioning from IPC to BNS.
2. NEVER hallucinate section numbers. Use ONLY the sections provided in the context.
   If you are unsure, say "Further legal research required."
3. Your language must be professional and precise — suitable for an Indian court.
4. Prioritize the Immediate Advisory first — actions the client must take RIGHT NOW.
5. Draft FIRs must follow the format required by Indian Police stations — they
   must be formal, in first person (from the complainant), and factual.
6. All documents must be ready for immediate use by a practising Indian lawyer.
7. Always include city/station details as PLACEHOLDER text in ALL CAPS so the
   lawyer can fill them in (e.g., [POLICE STATION NAME], [CITY], [DATE])."""


def configure_groq() -> Groq:
    """
    Configures the Groq client for fast, free AI text generation.

    WHY GROQ:
    - Groq uses custom LPU (Language Processing Unit) hardware — it's 10x faster
      than standard GPU-based APIs.
    - Llama-3.3-70B is a 70-billion parameter open-source model that rivals GPT-4
      in legal reasoning tasks.
    - Free tier: 14,400 requests/day, 131,072 tokens/minute — more than enough.
    - Get your free key at: https://console.groq.com
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key or groq_key == "your_groq_api_key_here":
        console.print(
            Panel(
                "[bold red]ERROR: GROQ_API_KEY not found![/bold red]\n\n"
                "1. Go to: [bold]https://console.groq.com[/bold]\n"
                "2. Sign up (free) → Click 'API Keys' → 'Create API key'\n"
                "3. Copy the key and paste it in your [bold].env[/bold] file:\n"
                "   [italic]GROQ_API_KEY=gsk_...[/italic]",
                title="[red]Groq API Key Required[/red]",
                border_style="red",
            )
        )
        sys.exit(1)

    return Groq(api_key=groq_key)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: GEMINI EMBEDDING FUNCTION (replaces ChromaDB's local model download)
# ══════════════════════════════════════════════════════════════════════════════
EMBEDDING_CACHE_FILE = Path("data/legal_corpus/embedding_cache.json")


def _load_embedding_cache() -> dict:
    """Load cached embeddings from disk to avoid redundant API calls."""
    if EMBEDDING_CACHE_FILE.exists():
        with open(EMBEDDING_CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_embedding_cache(cache: dict):
    """Persist embeddings to disk so next run is instant (no API calls)."""
    EMBEDDING_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EMBEDDING_CACHE_FILE, "w") as f:
        json.dump(cache, f)


def _get_embedding_with_cache(text: str, task_type: str, cache: dict) -> list:
    """
    Returns a Gemini embedding, using disk cache to avoid redundant API calls.
    On first run: calls API and saves to cache.
    On subsequent runs: reads from cache instantly (0 API calls for indexing).
    """
    cache_key = hashlib.md5(f"{task_type}:{text}".encode()).hexdigest()
    if cache_key in cache:
        return cache[cache_key]

    # Not in cache — call the API with retry on rate limit
    for attempt in range(4):
        try:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type=task_type,
            )
            embedding = result["embedding"]
            cache[cache_key] = embedding
            return embedding
        except Exception as e:
            if "429" in str(e) and attempt < 3:
                wait = 35 * (attempt + 1)
                console.print(f"[yellow]Rate limit hit. Waiting {wait}s before retry...[/yellow]")
                time.sleep(wait)
            else:
                raise


class GeminiEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Uses Google Gemini's embedding model with disk-based caching.

    WHY THIS IS BETTER THAN THE DEFAULT:
    - Default ChromaDB downloads a 79MB model file on first run (slow, fails on bad internet).
    - Gemini embeddings use the API (no download), optimized for legal/professional text.
    - Disk cache: First run calls API once per document. Every subsequent run is INSTANT.
    """

    def __init__(self):
        self.cache = _load_embedding_cache()

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        embeddings = []
        new_items = 0
        for text in input:
            emb = _get_embedding_with_cache(text, "retrieval_document", self.cache)
            embeddings.append(emb)
            new_items += 1
        if new_items > 0:
            _save_embedding_cache(self.cache)  # Persist new embeddings to disk
        return embeddings


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: BUILD THE RAG KNOWLEDGE BASE (ChromaDB)
# ══════════════════════════════════════════════════════════════════════════════
def build_rag_knowledge_base() -> chromadb.Collection:
    """
    Loads all BNS law sections into ChromaDB using Gemini embeddings.

    HOW RAG WORKS (Simple Explanation for Investors):
    - Imagine you have a 500-page law book. You don't send ALL 500 pages to the AI
      every time — that would be slow and expensive.
    - Instead, ChromaDB converts each law section into a mathematical fingerprint
      (called an 'embedding' or 'vector') using Gemini's embedding model.
    - When a client describes their problem, we convert their story into a vector
      too, and find the TOP 6 most similar law sections — instantly.
    - Only those relevant sections are sent to the AI, making it fast, cheap,
      and most importantly, ACCURATE (it can only cite sections we give it).
    """
    console.print("[dim]Initializing BNS Legal Knowledge Base with Gemini embeddings...[/dim]")

    # Create an in-memory Chroma client (no database file needed for Phase 1)
    chroma_client = chromadb.Client()

    # Delete existing collection if it exists (for clean re-runs)
    try:
        chroma_client.delete_collection("bns_legal_sections")
    except Exception:
        pass

    # Create collection using Gemini embeddings — no local model download needed
    embedding_fn = GeminiEmbeddingFunction()
    collection = chroma_client.create_collection(
        name="bns_legal_sections",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},  # Cosine similarity = best for text
    )

    # ── Load BNS Sections ─────────────────────────────────────────────────────
    bns_docs, bns_metas, bns_ids = kb.get_all_documents()

    # ── Load Case Summaries + Circulars + IPC-BNS Mappings ───────────────────
    corpus_docs, corpus_metas, corpus_ids = corpus.get_corpus_as_rag_documents()

    # ── Combine all sources ───────────────────────────────────────────────────
    all_documents = bns_docs + corpus_docs
    all_metadatas = bns_metas + corpus_metas
    all_ids = bns_ids + corpus_ids

    console.print(f"[dim]Embedding {len(all_documents)} legal documents via Gemini API...[/dim]")

    # Add all documents — Gemini API generates embeddings (no local download)
    collection.add(
        documents=all_documents,
        metadatas=all_metadatas,
        ids=all_ids,
    )

    console.print(
        f"[green]✓[/green] Knowledge Base ready: "
        f"[bold]{len(bns_docs)} BNS sections[/bold] + "
        f"[bold]{len(corpus_docs)} case summaries/circulars/mappings[/bold] indexed."
    )
    return collection


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: RETRIEVE RELEVANT LAWS (The RAG Search)
# ══════════════════════════════════════════════════════════════════════════════
def _normalize_source(rank: int, doc_id: str, doc: str, meta: dict, relevance: float) -> dict:
    """
    Convert ChromaDB hit metadata (which differs by document type) into a single
    schema for the frontend Sources panel. The collection contains four kinds of
    documents — BNS sections, case summaries, legal circulars, and IPC→BNS mappings —
    each with its own metadata fields.
    """
    kind = (meta or {}).get("type")
    if kind is None and doc_id.startswith("bns_"):
        kind = "bns_section"
    elif kind is None:
        kind = "unknown"

    label = ""
    if kind == "bns_section":
        label = f"{meta.get('section', 'BNS')} — {meta.get('title', '')}"
    elif kind == "case_summary":
        label = f"{meta.get('case_name', '')} ({meta.get('year', '')})"
    elif kind == "circular":
        label = f"{meta.get('title', '')} — {meta.get('issuer', '')}"
    elif kind == "ipc_bns_mapping":
        label = f"{meta.get('ipc_section', '')} → {meta.get('bns_section', '')}"
    else:
        label = doc_id

    return {
        "rank": rank,
        "id": doc_id,
        "kind": kind,
        "label": label,
        "section": meta.get("section"),
        "old_ipc": meta.get("old_ipc"),
        "title": meta.get("title"),
        "punishment": meta.get("punishment"),
        "bailable": meta.get("bailable"),
        "cognizable": meta.get("cognizable"),
        "transition_note": meta.get("transition_note"),
        # case-specific
        "case_name": meta.get("case_name"),
        "court": meta.get("court"),
        "year": meta.get("year"),
        # circular-specific
        "issuer": meta.get("issuer"),
        "date": meta.get("date"),
        # mapping-specific
        "ipc_section": meta.get("ipc_section"),
        "bns_section": meta.get("bns_section"),
        "relevance": relevance,
        "raw_text": doc,
    }


def retrieve_relevant_sections_structured(
    collection: chromadb.Collection, client_story: str, n_results: int = 6
):
    """
    Same retrieval as ``retrieve_relevant_sections``, but also returns a list of
    structured ``source`` dicts so the frontend can show citation provenance.

    Returns: (context_string, sources_list)
    """
    cache = _load_embedding_cache()
    query_embedding = _get_embedding_with_cache(client_story, "retrieval_query", cache)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    context_parts = ["=== RETRIEVED BNS LEGAL SECTIONS (USE ONLY THESE) ===\n"]
    sources = []
    for i, (doc, meta, dist, doc_id) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            results["ids"][0],
        )
    ):
        relevance = round((1 - dist) * 100, 1)
        context_parts.append(
            f"\n[SECTION {i+1} — Relevance: {relevance}%]\n{doc}\n"
        )
        sources.append(_normalize_source(i + 1, doc_id, doc, meta, relevance))

    return "\n".join(context_parts), sources


def retrieve_relevant_sections(
    collection: chromadb.Collection, client_story: str, n_results: int = 6
) -> str:
    """
    Performs a semantic search on the knowledge base to find the most relevant
    BNS sections for the client's specific situation.

    Backwards-compatible wrapper that returns just the context string. New code
    should prefer ``retrieve_relevant_sections_structured`` to also get the
    sources list for citation provenance in the UI.
    """
    return retrieve_relevant_sections_structured(collection, client_story, n_results)[0]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: BUILD THE MASTER LEGAL PROMPT
# ══════════════════════════════════════════════════════════════════════════════
def build_legal_prompt(client_story: str, retrieved_context: str) -> str:
    """
    Constructs the final prompt sent to Gemini.

    This is the core "instruction architecture" of Lex-Indic. We give the AI:
    1. The law (retrieved BNS sections from RAG)
    2. The client's story
    3. An exact output format it MUST follow

    The structured output format is critical for the PDF generator (Phase 2).
    """
    today = datetime.now().strftime("%d %B %Y")

    prompt = f"""
DATE OF CONSULTATION: {today}

{retrieved_context}

=== CLIENT'S STATEMENT (FACTS OF THE CASE) ===
{client_story}

=== STEP 0 — DETERMINE CLIENT'S ROLE (do this silently, use it to shape ALL output below) ===
Read the client's statement carefully.
Determine: Is the client a COMPLAINANT (victim/filing party) or a RESPONDENT (defending/accused)?
ALL sections below must be written to HELP THE CLIENT — not against them.

=== YOUR MANDATORY OUTPUT FORMAT ===
Based on the client's statement and ONLY the BNS sections provided above,
produce ALL SIX sections below. Use the exact headings shown.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1: IMMEDIATE CLIENT ADVISORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Provide an urgent, numbered list of 6-8 concrete steps the CLIENT must take
 RIGHT NOW for their protection and legal position. Tailor to their role:
 - If COMPLAINANT: safety steps, evidence to preserve, what NOT to do.
 - If RESPONDENT: steps to protect themselves, evidence to preserve to disprove
   allegations, what NOT to say or do that could harm their defence.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2: LEGAL ANALYSIS UNDER BNS 2023
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Split into TWO clear sub-sections:

 A. SECTIONS THE CLIENT CAN USE (in their favour):
    - If COMPLAINANT: sections under which they can file a case.
    - If RESPONDENT: sections for counter-complaint OR bail/defence provisions.
    For each: BNS number + title, old IPC replaced, punishment, bailable status,
    how these facts support the CLIENT's position.

 B. SECTIONS THE OPPOSING PARTY MAY USE (against the client):
    - List sections the other side might invoke against the client.
    - For each: punishment, bailable status, and how the CLIENT can defend.
    - If COMPLAINANT: possible false counter-allegations by the accused.
    - If RESPONDENT: the exact sections being threatened/filed against them.

 Always mention the old IPC section replaced and the KEY legal difference.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3: CASE STRATEGY & STRENGTH ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Provide:
 - CLIENT'S ROLE: Clearly state COMPLAINANT or RESPONDENT
 - Overall case strength FOR THE CLIENT: STRONG / MODERATE / WEAK (with reason)
 - Key evidence the CLIENT needs to support their position
 - What the opposing party will argue against the client
 - Recommended legal strategy for the CLIENT in 3-4 bullet points]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4: DRAFT FIRST INFORMATION REPORT (FIR)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[If the CLIENT is a COMPLAINANT or can file a counter-complaint:
 Write a complete, formal FIR filed BY the client, in first person.
 Must include:
 - To: The Station House Officer, [POLICE STATION NAME], [CITY]
 - Subject line with relevant BNS sections
 - Details of the complainant (PLACEHOLDERS: [COMPLAINANT NAME], [AGE], [ADDRESS])
 - Chronological narration of events from the CLIENT'S perspective
 - Names of accused (PLACEHOLDERS: [ACCUSED NAME 1], [ACCUSED NAME 2])
 - Specific BNS sections being invoked IN FAVOUR of the client
 - Prayer/Relief requested by the client
 - Declaration and signature block

 If the CLIENT is purely a RESPONDENT with no counter-claim, write:
 "RESPONDENT ADVISORY: No FIR to be filed by client at this stage. Instead,
 prepare a detailed written statement to the police rebutting the allegations.
 Draft rebuttal statement follows:" and then draft that rebuttal instead.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5: DRAFT LEGAL NOTICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Write a formal legal notice from the CLIENT'S lawyer to the opposing party.
 Must include:
 - Sender: [ADVOCATE NAME], [BAR COUNCIL REG. NO.], [LAW FIRM NAME], [ADDRESS]
 - Addressee: [OPPOSING PARTY NAME], [ADDRESS]
 - Date: {today}
 - Notice Number: LN-[YEAR]-[SEQUENCE NUMBER]
 - Subject line reflecting the CLIENT's grievance or defence
 - Statement of facts from the CLIENT'S perspective in numbered paragraphs
 - Legal demands or assertions in the CLIENT'S favour with 15-day deadline
 - Consequences of non-compliance
 - Formal closing]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6: POLICE HELP REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Write a clear, plain-language narrative for the police officer, from the
 CLIENT'S perspective. Include:
 - Summary (3-4 sentences) of what happened and the CLIENT'S position
 - Incident timeline from the CLIENT'S point of view
 - Current risk level for the CLIENT: HIGH / MEDIUM / LOW
 - Police action the CLIENT is requesting (protection, investigation, bail, etc.)
 - Witness information (PLACEHOLDER: [WITNESS NAME], [CONTACT NUMBER])
 - Evidence the CLIENT has and wants the police to consider
 - Client's current location and status (PLACEHOLDER)]
"""
    return prompt


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: DISPLAY THE RESULTS BEAUTIFULLY
# ══════════════════════════════════════════════════════════════════════════════
def display_results(client_story: str, ai_response: str):
    """
    Renders the AI's output in a professional, formatted layout in the terminal.
    This makes demos and investor presentations look impressive.
    """
    console.print()
    console.rule(
        "[bold blue]LEX-INDIC: BNS TRANSITION ENGINE — CASE ANALYSIS REPORT[/bold blue]",
        style="blue",
    )

    # Print client's case summary
    console.print(
        Panel(
            client_story,
            title="[bold yellow]CLIENT'S STATEMENT (Input)[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    # Split the AI response into sections based on our headings
    sections = {
        "SECTION 1: IMMEDIATE CLIENT ADVISORY": ("red", "IMMEDIATE CLIENT ADVISORY"),
        "SECTION 2: LEGAL ANALYSIS UNDER BNS 2023": ("blue", "BNS LEGAL ANALYSIS"),
        "SECTION 3: CASE STRATEGY & STRENGTH ASSESSMENT": ("magenta", "CASE STRATEGY"),
        "SECTION 4: DRAFT FIRST INFORMATION REPORT (FIR)": ("green", "DRAFT FIR"),
        "SECTION 5: DRAFT LEGAL NOTICE": ("cyan", "DRAFT LEGAL NOTICE"),
        "SECTION 6: POLICE HELP REPORT": ("orange3", "POLICE HELP REPORT"),
    }

    response_text = ai_response

    for heading, (color, display_title) in sections.items():
        # Find the section in the response
        start_idx = response_text.find(heading)
        if start_idx == -1:
            # Try partial match
            short_heading = heading.split(":")[1].strip()
            start_idx = response_text.find(short_heading)

        if start_idx != -1:
            # Find where this section ends (next section starts)
            next_section_start = len(response_text)
            for other_heading in sections.keys():
                if other_heading == heading:
                    continue
                other_idx = response_text.find(other_heading, start_idx + 1)
                if other_idx != -1 and other_idx < next_section_start:
                    next_section_start = other_idx

            section_content = response_text[start_idx:next_section_start].strip()
            # Remove the heading itself from the content
            section_content = section_content.replace(heading, "").replace(
                "━" * 50, ""
            ).strip()

            console.print()
            console.print(
                Panel(
                    section_content,
                    title=f"[bold {color}]{display_title}[/bold {color}]",
                    border_style=color,
                    padding=(1, 2),
                    expand=True,
                )
            )

    # If section parsing fails, just print the raw response
    if not any(h in response_text for h in sections.keys()):
        console.print(
            Panel(
                response_text,
                title="[bold green]AI Legal Analysis[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )

    console.print()
    console.rule("[dim]End of Report — Lex-Indic v1.0[/dim]", style="dim")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: SAVE THE RAW OUTPUT FOR PHASE 2 (PDF GENERATION)
# ══════════════════════════════════════════════════════════════════════════════
def save_raw_output(client_story: str, ai_response: str) -> str:
    """
    Saves the raw text output to the 'outputs' folder.
    Phase 2 will read this file to generate the professional PDF report.
    """
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"outputs/case_analysis_{timestamp}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("LEX-INDIC: BNS TRANSITION ENGINE — CASE ANALYSIS REPORT\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        f.write("CLIENT'S STATEMENT:\n")
        f.write(client_story + "\n\n")
        f.write("=" * 70 + "\n\n")
        f.write(ai_response)

    return filename


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR — Ties all steps together
# ══════════════════════════════════════════════════════════════════════════════
def run_legal_triage(client_story: str):
    """
    The main pipeline that runs the complete legal triage for one client case.

    PIPELINE:
    Client Story → RAG Search (Gemini Embeddings) → Prompt → Groq Llama-3.3-70B → Output
    """
    console.print()
    console.print(
        Panel(
            "[bold white]LEX-INDIC[/bold white]: The BNS Transition Engine\n"
            "[dim]AI-Powered Junior Associate for Indian Law Firms[/dim]",
            border_style="blue",
            box=box.DOUBLE,
            padding=(1, 4),
        )
    )

    # ── Step 1: Configure APIs ────────────────────────────────────────────────
    console.print("[bold]Step 1/4:[/bold] Connecting to AI services...")
    configure_gemini_embeddings()   # Gemini: for embeddings only
    groq_client = configure_groq()  # Groq: for text generation
    console.print("[green]✓[/green] Groq (Llama-3.3-70B) + Gemini Embeddings connected.\n")

    # ── Step 2: Build Knowledge Base ─────────────────────────────────────────
    console.print("[bold]Step 2/4:[/bold] Loading BNS Legal Knowledge Base (RAG)...")
    collection = build_rag_knowledge_base()
    console.print()

    # ── Step 3: Retrieve Relevant Laws ───────────────────────────────────────
    console.print("[bold]Step 3/4:[/bold] Analyzing case and retrieving relevant BNS sections...")
    retrieved_context = retrieve_relevant_sections(collection, client_story)
    console.print("[green]✓[/green] Top relevant BNS sections identified.\n")

    # ── Step 4: Call Groq Llama-3.3-70B for Full Legal Analysis ──────────────
    console.print("[bold]Step 4/4:[/bold] Generating full legal analysis (Groq Llama-3.3-70B)...")
    console.print("[dim](Groq is extremely fast — expect results in 5-15 seconds)[/dim]\n")

    prompt = build_legal_prompt(client_story, retrieved_context)

    ai_response = None
    for attempt in range(4):
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",   # Groq's best free model
                messages=[
                    {"role": "system", "content": LEXI_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.2,        # Low = precise, consistent legal output
                max_tokens=8192,        # Long enough for full FIR + Legal Notice
            )
            ai_response = completion.choices[0].message.content
            break
        except Exception as e:
            err = str(e)
            if ("429" in err or "rate_limit" in err.lower()) and attempt < 3:
                wait = 20 * (attempt + 1)
                console.print(f"[yellow]Rate limit. Retrying in {wait}s (attempt {attempt+1}/3)...[/yellow]")
                time.sleep(wait)
            else:
                console.print(f"[bold red]ERROR calling Groq API:[/bold red] {err[:200]}")
                console.print("[yellow]HINT: Check GROQ_API_KEY in .env — get a free key at console.groq.com[/yellow]")
                sys.exit(1)

    if ai_response is None:
        console.print("[bold red]Failed after 3 retries.[/bold red]")
        sys.exit(1)

    # ── Step 5: Display Results ───────────────────────────────────────────────
    display_results(client_story, ai_response)

    # ── Step 6: Save text output + auto-generate PDF Case Brief ──────────────
    saved_path = save_raw_output(client_story, ai_response)
    console.print(
        f"\n[green]✓ Raw output saved to:[/green] [bold]{saved_path}[/bold]"
    )

    # Auto-generate the professional PDF Case Brief (Phase 2)
    try:
        from pdf_generator import generate_pdf
        console.print("[bold]Generating PDF Case Brief...[/bold]")
        pdf_path = generate_pdf(saved_path)
        console.print(
            Panel(
                f"[bold green]PDF Case Brief ready:[/bold green] [bold]{pdf_path}[/bold]\n\n"
                "Open this file to see the professional formatted report.\n"
                "[dim]IMPORTANT: Review with a licensed Advocate before use.[/dim]",
                title="[bold green]Phase 2 Complete[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )
    except Exception as e:
        console.print(f"[yellow]PDF generation skipped: {e}[/yellow]")
        console.print("[dim]Run python3 pdf_generator.py to generate the PDF manually.[/dim]")


# ══════════════════════════════════════════════════════════════════════════════
# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    # ── TEST CASES — Add your own client stories here ─────────────────────────
    # To test: Replace TEST_CASE_1 below with your client's story, then run:
    #   python3 main.py

    TEST_CASE_1 = """
    Client is a 28-year-old married woman. She says that since the first month of
    marriage, her husband and his mother have been demanding a car as additional
    dowry, threatening that they will throw her out if she doesn't comply. Three
    days ago, her husband physically assaulted her, breaking her wrist, and then
    locked her out of the house at midnight with no money or phone. A neighbour
    helped her contact us. She has WhatsApp messages showing the dowry demands
    and photos of her injuries taken at the hospital. Her husband is a government
    employee. She is currently staying at her parents' home and is scared he will
    come there. She wants to file a case and ensure she is not forced to return.
    """

    TEST_CASE_2 = """
    Client is a 35-year-old male software engineer. He says his former business
    partner has been sending threatening messages on WhatsApp saying he will
    'destroy his life' and 'make sure he never works again'. The partner has also
    been posting false statements on LinkedIn claiming the client committed fraud
    during their partnership. The client has all the WhatsApp screenshots and
    LinkedIn post URLs. He wants to know what criminal cases he can file and
    also wants to send a legal notice.
    """

    TEST_CASE_3 = """
    Client is a 22-year-old college student. A male classmate has been following
    her home every day for the past two months, sending her over 100 messages daily
    despite her clearly telling him to stop, and recently installed a hidden camera
    in the college bathroom which she discovered accidentally. She has reported it
    to the college but they have taken no action. She is terrified for her safety.
    She has screenshots of all the messages and the location of the camera.
    """

    # ── SELECT WHICH TEST CASE TO RUN ─────────────────────────────────────────
    # Change TEST_CASE_1 to TEST_CASE_2 or TEST_CASE_3 to try other scenarios
    ACTIVE_TEST_CASE = TEST_CASE_1

    # ── RUN THE ENGINE ────────────────────────────────────────────────────────
    run_legal_triage(ACTIVE_TEST_CASE)
