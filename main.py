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
import re
import hashlib
import secrets
import textwrap
import urllib.error
import urllib.request
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
from chromadb.config import Settings

# rich: Beautiful terminal output (makes it look professional in VS Code)
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box

# ─── LOCAL MODULES ────────────────────────────────────────────────────────────
# Our curated BNS knowledge base (the 'legal brain' we built)
import data.bns_knowledge_base as kb
import llm_provider
# Day 11 — BNSS (procedure) + BSA (evidence) corpora.  Optional import: if the
# file is absent, the RAG build still works with BNS-only.
try:
    import data.bnss_bsa_knowledge_base as bnss_bsa_kb
except ImportError:
    bnss_bsa_kb = None
# Case summaries, circulars, and IPC-BNS mapping corpus
import data.download_legal_corpus as corpus
# Official Gazette text of every BNS / BNSS / BSA section
import statutes
# Supreme Court criminal judgments (local store, optional)
import sc_judgments

# ─── INITIALIZATION ───────────────────────────────────────────────────────────
load_dotenv()                          # Read the .env file into environment
console = Console(width=100)           # Rich console for beautiful terminal output


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1A: CONFIGURE GEMINI (Embeddings only — RAG search)
# ══════════════════════════════════════════════════════════════════════════════
def embeddings_provider() -> str:
    """Who turns text into vectors for RAG search — and therefore who sees the
    client's story:
      gemini  Google's embedding API (default). The story leaves the machine.
      ollama  A local embedding model via Ollama (OLLAMA_EMBED_MODEL, default
              qwen3-embedding:4b). Nothing leaves the machine; pair it with
              LLM_PROVIDER=ollama for a fully local deployment.
    Switching provider means re-embedding the knowledge base (first start)."""
    return (os.getenv("EMBEDDINGS_PROVIDER") or "gemini").strip().lower()


def _ollama_embed_model() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL") or "qwen3-embedding:4b"   # 90% vs 80% (bge-m3) on the stress set


def configure_gemini_embeddings():
    """Configures Gemini API for embeddings only (RAG vector search)."""
    if embeddings_provider() != "gemini":
        return
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
1. Cite BNS sections (2023) and ALWAYS mention the old IPC section each replaced —
   this is critical because lawyers are still transitioning from IPC to BNS.
1A. The date of the OFFENCE decides the law: an offence committed before
   1 July 2024 is charged under the IPC (give the BNS equivalent for reference
   only); procedure for an FIR registered on or after 1 July 2024 follows the BNSS.
2. NEVER hallucinate section numbers. Use ONLY the sections provided in the context.
   If you are unsure, say "Further legal research required."
   When you pair an old IPC section with its BNS section, use the pairing given
   in the context ("old IPC" line) — never infer one from the section number.
   Write each section's title exactly as the context gives it.
2B. The sections in the context are CANDIDATES found by similarity search, not a
   charge list — they include look-alikes on purpose. Charge a section ONLY when
   every ingredient in its text is shown by the facts; leave out the rest. Apply
   the DISTINGUISH notes in the context before choosing.
2A. Cite case law ONLY from LANDMARK CASE and SUPREME COURT JUDGMENT entries in
   the context, with the citation exactly as given there, and say only what the
   entry itself says about the case. NEVER cite a case from memory. NEVER rely on
   a case whose GOOD-LAW STATUS is OVERRULED or SUPERSEDED as current law.
   A SUPREME COURT JUDGMENT entry is a real case on related provisions — present
   it as an example of how the Court dealt with similar facts, not as binding on
   the client's facts unless the extract shows the same point of law.
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
EMBEDDING_CACHE_FILE = Path("data/legal_corpus/embedding_cache.json")          # Gemini (committed)
LOCAL_EMBEDDING_CACHE_FILE = Path("data/legal_corpus/embedding_cache.local.json")  # Ollama (gitignored)
_CACHES: dict[Path, dict] = {}


def _embedding_cache_file() -> Path:
    """Gemini vectors ship with the repo for warm deploys; local-model vectors
    are larger (one set per model) and stay on the machine that made them."""
    return EMBEDDING_CACHE_FILE if embeddings_provider() == "gemini" else LOCAL_EMBEDDING_CACHE_FILE


def _load_embedding_cache() -> dict:
    """Cached embeddings for the current provider, read from disk once per
    process (the file is large; queries reuse the in-memory copy)."""
    path = _embedding_cache_file()
    if path not in _CACHES:
        cache = {}
        if path.exists():
            with open(path, "r") as f:
                cache = json.load(f)
        _CACHES[path] = cache
    return _CACHES[path]


def _save_embedding_cache(cache: dict):
    """Persist embeddings to disk so next run is instant (no API calls).
    Written to a temp file and renamed, so a concurrent reader never sees half a file."""
    path = _embedding_cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(cache, f)
    tmp.replace(path)


def _embed_ollama(text: str, task_type: str) -> list:
    """One embedding from the local Ollama server — no third party involved."""
    model = _ollama_embed_model()
    if "nomic" in model:   # nomic-embed-text expects task prefixes
        text = ("search_query: " if task_type == "retrieval_query" else "search_document: ") + text
    elif "qwen3-embedding" in model and task_type == "retrieval_query":
        # Qwen3-Embedding: queries carry a one-line task instruction; documents don't.
        text = ("Instruct: Given a client's account of what happened, retrieve the Indian "
                "criminal-law provisions and judgments that apply\nQuery: " + text)
    host = (os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    req = urllib.request.Request(
        f"{host}/api/embed", data=json.dumps({"model": model, "input": text}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["embeddings"][0]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(
            f"Ollama could not embed with model {model!r} ({e.code}: {detail}). "
            f"Use an embedding model: `ollama pull nomic-embed-text`."
        ) from e


def _embedding_cache_key(text: str, task_type: str) -> str:
    """Gemini keys keep their original form so the committed cache stays valid;
    other providers are namespaced so vectors of different sizes never mix."""
    provider = embeddings_provider()
    raw_key = (f"{task_type}:{text}" if provider == "gemini"
               else f"{provider}:{_ollama_embed_model()}:{task_type}:{text}")
    return hashlib.md5(raw_key.encode(), usedforsecurity=False).hexdigest()


def _get_embedding_with_cache(text: str, task_type: str, cache: dict) -> list:
    """
    Returns an embedding from the configured provider, using the disk cache to
    avoid redundant work. On first run: embeds and caches. On subsequent runs:
    reads from cache instantly (0 calls for indexing).
    """
    provider = embeddings_provider()
    cache_key = _embedding_cache_key(text, task_type)
    if cache_key in cache:
        return cache[cache_key]

    if provider == "ollama":
        embedding = _embed_ollama(text, task_type)
        cache[cache_key] = embedding
        return embedding
    if provider != "gemini":
        raise ValueError(f"Unknown EMBEDDINGS_PROVIDER {provider!r} (use gemini or ollama).")

    # Not in cache — call the API with retry on rate limit. Indexing the KB at
    # startup can afford long waits; a query inside a web request can't (it
    # would hold the worker for minutes), so queries retry briefly.
    patient = task_type == "retrieval_document"
    for attempt in range(4 if patient else 2):
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
            if "429" in str(e) and attempt < (3 if patient else 1):
                wait = 35 * (attempt + 1) if patient else 2
                console.print(f"[yellow]Rate limit hit. Waiting {wait}s before retry...[/yellow]")
                time.sleep(wait)
            else:
                raise


class GeminiEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Embeds the knowledge base with the configured provider (Gemini by default,
    or local Ollama — see embeddings_provider), with disk-based caching.

    - Gemini: no model download; the API is optimised for professional text.
    - Ollama: runs locally; the model is pulled once with `ollama pull`.
    - Disk cache: the first run embeds each document once; later runs are instant.
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
    console.print(f"[dim]Initializing BNS Legal Knowledge Base with {embeddings_provider()} embeddings...[/dim]")

    # Create an in-memory Chroma client (no database file needed for Phase 1).
    # Telemetry off: Chroma otherwise reports usage events to PostHog (a US
    # analytics service) on every start — an outbound call this app must not make.
    chroma_client = chromadb.Client(Settings(anonymized_telemetry=False))

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

    all_documents, all_metadatas, all_ids, counts = knowledge_base_documents()
    console.print(f"[dim]Embedding {len(all_documents)} legal documents via {embeddings_provider()}...[/dim]")
    collection.add(
        documents=all_documents,
        metadatas=all_metadatas,
        ids=all_ids,
        embeddings=embedding_fn(embedding_texts(all_documents, all_metadatas)),
    )

    console.print(
        f"[green]✓[/green] Knowledge Base ready: "
        f"[bold]{counts['statutes']} official BNS/BNSS/BSA sections[/bold] + "
        f"[bold]{counts['corpus']} corpus[/bold] + "
        f"[bold]{counts['judgments']} Supreme Court judgments[/bold] indexed."
    )
    return collection


def knowledge_base_documents() -> tuple[list[str], list[dict], list[str], dict[str, int]]:
    """Every document the index holds: (docs, metadatas, ids, counts by source).
    Shared by build_rag_knowledge_base and tools/prewarm_embeddings.py."""
    # ── Statutes: the official Gazette text of every BNS / BNSS / BSA section
    #    (1,059), with the curated KB's plain-language keywords and practice
    #    notes folded in. The curated KB alone covered 89 of 358 BNS sections,
    #    so anything outside it was answered from the model's memory.
    curated = kb.get_all_documents()[0]
    if bnss_bsa_kb is not None:
        curated += bnss_bsa_kb.get_all_documents()[0]
    statute_docs, statute_metas, statute_ids = statutes.official_documents(curated)
    # ── Case Summaries + Circulars + IPC-BNS Mappings, then SC judgments ─────
    corpus_docs, corpus_metas, corpus_ids = corpus.get_corpus_as_rag_documents()
    judgment_docs, judgment_metas, judgment_ids = sc_judgments.documents()
    counts = {"statutes": len(statute_docs), "corpus": len(corpus_docs), "judgments": len(judgment_docs)}
    return (statute_docs + corpus_docs + judgment_docs,
            statute_metas + corpus_metas + judgment_metas,
            statute_ids + corpus_ids + judgment_ids, counts)


def embedding_texts(docs: list[str], metas: list[dict]) -> list[str]:
    """What gets embedded: each document's search key (title + keywords +
    opening text) where it has one; the full text is what the model reads."""
    return [m.get("search_key") or d for d, m in zip(docs, metas)]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: RETRIEVE RELEVANT LAWS (The RAG Search)
# ══════════════════════════════════════════════════════════════════════════════
try:
    from data.bns_bare_act_urls import deep_link_summary as _bns_deep_link
except ImportError:
    def _bns_deep_link(_):  # type: ignore
        return None

# Day 26: generic deep-link generator for BNSS + BSA (and any future statute)
try:
    from deep_links import deep_link_for as _dl_for, deep_link_label as _dl_label
    def _generic_deep_link(doc_id: str):
        url = _dl_for(doc_id or "")
        if not url:
            return None
        return {"url": url, "label": _dl_label(doc_id), "source": "indiacode.nic.in"}
except ImportError:
    def _generic_deep_link(_):
        return None


def _normalize_source(rank: int, doc_id: str, doc: str, meta: dict, relevance: float) -> dict:
    """
    Convert ChromaDB hit metadata (which differs by document type) into a single
    schema for the frontend Sources panel. The collection contains four kinds of
    documents — BNS sections, case summaries, legal circulars, and IPC→BNS mappings —
    each with its own metadata fields.
    """
    kind = (meta or {}).get("type")
    if kind is None and doc_id.startswith("bnss_"):
        kind = "bnss_section"
    elif kind is None and doc_id.startswith("bsa_"):
        kind = "bsa_section"
    elif kind is None and doc_id.startswith("bns_"):
        kind = "bns_section"
    elif kind is None:
        kind = "unknown"

    label = ""
    if kind in ("bns_section", "bnss_section", "bsa_section"):
        label = f"{meta.get('section', 'Section')} — {meta.get('title', '')}"
    elif kind == "case_summary":
        label = f"{meta.get('case_name', '')} ({meta.get('year', '')})"
    elif kind == "circular":
        label = f"{meta.get('title', '')} — {meta.get('issuer', '')}"
    elif kind == "ipc_bns_mapping":
        label = f"{meta.get('ipc_section', '')} → {meta.get('bns_section', '')}"
    elif kind == "sc_ruling":
        label = f"News report: {meta.get('title', '')} ({meta.get('date', '')})"
    elif kind == "sc_judgment":
        label = f"{meta.get('case_name', '')}, {meta.get('insc', '')}"
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
        # Day-8 + Day-26: deep-link bundle. Day 8 = curated BNS URLs.
        # Day 26 = programmatic fallback for BNSS / BSA via deep_links.py.
        "deep_link": (
            _bns_deep_link(meta.get("section", ""))
            if kind == "bns_section"
            else _generic_deep_link(doc_id)
        ),
        "relevance": relevance,
        "raw_text": doc,
    }


_DISTINCTIONS_FILE = Path(__file__).parent / "data" / "legal_corpus" / "distinctions.json"
_DISTINCTIONS: list[dict] | None = None


def distinction_notes(bns_sections: set[str], limit: int = 3) -> list[str]:
    """Notes that separate look-alike sections (theft vs snatching vs robbery …)
    for the families the search returned — similarity ranks siblings almost
    equally, so the model needs the ingredient that tells them apart."""
    global _DISTINCTIONS
    if _DISTINCTIONS is None:
        try:
            _DISTINCTIONS = json.loads(_DISTINCTIONS_FILE.read_text(encoding="utf-8"))["groups"]
        except (OSError, ValueError, KeyError):
            _DISTINCTIONS = []
    hits = [(len(bns_sections & set(g["sections"])), i, g["note"])
            for i, g in enumerate(_DISTINCTIONS)]
    return [note for n, _, note in sorted(hits, key=lambda h: (-h[0], h[1])) if n][:limit]


# Retrieval pools with fixed shares. With every section of three Acts indexed,
# one similarity ranking let 701 procedure/evidence sections crowd the
# offences out (a pickpocketing story retrieved BNSS 399 and BSA 119, not theft).
# Offences come in two tiers: sections with a plain-language curated card are
# matched far more reliably than the rest of the Act (measured on the stress
# set: 6 curated + 1 other + 1 procedure slots = 80% recall vs 68% for one
# ranking over everything), but one slot keeps every other section reachable.
_POOLS = (("offences", {"$and": [{"type": "bns_section"}, {"curated": True}]}),
          ("other_offences", {"type": {"$in": ["bns_section", "ipc_bns_mapping", "special_section"]}}),
          ("procedure", {"type": {"$in": ["bnss_section", "bsa_section"]}}),
          ("authorities", {"type": {"$in": ["case_summary", "circular", "sc_ruling", "sc_judgment"]}}))


def _pool_sizes(n_results: int) -> dict[str, int]:
    procedure = 1 if n_results >= 6 else 0
    authorities = 2 if n_results >= 10 else 1
    return {"offences": max(1, n_results - 1 - procedure - authorities), "other_offences": 1,
            "procedure": procedure, "authorities": authorities}


def _query_pools(collection, query_embedding, n_results: int,
                 selected: list[str] | None = None) -> dict:
    """collection.query, one pool at a time, merged in pool order (offences
    first) into the single-query result shape. `selected` BNS sections (from
    charge_selector) lead the offence pool, fetched by number; similarity
    search fills the offence slots they leave."""
    merged = {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
    sizes = _pool_sizes(n_results)
    if selected:
        got = collection.get(ids=[f"bns_{n}" for n in selected[:sizes["offences"]]],
                             include=["documents", "metadatas", "embeddings"])
        order = {f"bns_{n}": i for i, n in enumerate(selected)}
        for doc_id, doc, meta, emb in sorted(
                zip(got["ids"], got["documents"], got["metadatas"], got["embeddings"]),
                key=lambda row: order[row[0]]):
            dot = sum(a * b for a, b in zip(query_embedding, emb))
            norm = (sum(a * a for a in query_embedding) * sum(b * b for b in emb)) ** 0.5 or 1.0
            merged["ids"][0].append(doc_id)
            merged["documents"][0].append(doc)
            merged["metadatas"][0].append(meta)
            merged["distances"][0].append(1 - dot / norm)
    for pool, where in _POOLS:
        k = sizes[pool] - (len(merged["ids"][0]) if pool == "offences" else 0)
        if k <= 0:
            continue
        try:
            r = collection.query(query_embeddings=[query_embedding], n_results=k + 8,
                                 where=where,
                                 include=["documents", "metadatas", "distances"])
        except Exception:  # noqa: BLE001 — pool empty in a partial index
            continue
        rows = [row for row in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])
                if row[0] not in merged["ids"][0]][:k]
        for doc_id, doc, meta, dist in rows:
            merged["ids"][0].append(doc_id)
            merged["documents"][0].append(doc)
            merged["metadatas"][0].append(meta)
            merged["distances"][0].append(dist)
    try:
        _add_punishing_sections(collection, merged)
    except Exception:  # noqa: BLE001 — partial index in tests / older collections
        pass
    return merged


# The BNS often defines an offence in one section and punishes it in another;
# a story that retrieves the definition must also bring the punishing section.
_PUNISHED_IN = {"bns_101": "bns_103", "bns_100": "bns_105", "bns_63": "bns_64",
                "bns_114": "bns_115", "bns_116": "bns_117", "bns_86": "bns_85"}

_ISSUES_SYSTEM = (
    "You are an Indian criminal lawyer. Restate the client's facts as the legal issues they raise, "
    "in 2-3 short lines of plain legal English: the wrongs done (e.g. theft, cheating, assault, cruelty, "
    "death, threat), how they were done, and any procedural problem (FIR refused, arrest, bail). "
    "Do NOT give section numbers.")


def _issue_summary(client_story: str) -> str:
    """The client's facts restated as legal issues by the local model, added to
    the search query (stress set: 90% → 93% of required sections retrieved).
    On when a local model serves this app (LLM_PROVIDER=ollama/hybrid) or
    QUERY_REWRITE=local; never a dependency — any failure searches the story alone."""
    flag = (os.getenv("QUERY_REWRITE") or "").strip().lower()
    if flag in ("off", "0", "false"):
        return ""
    if flag != "local" and llm_provider.get_provider() not in ("ollama", "hybrid"):
        return ""
    try:
        return llm_provider.complete_local(
            system_messages=[_ISSUES_SYSTEM], user_message=client_story,
            temperature=0.0, max_tokens=120, timeout_s=60, think=False)["text"].strip()[:600]
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]Issue summary unavailable ({type(e).__name__}); searching the story alone.[/yellow]")
        return ""


def _add_punishing_sections(collection, merged: dict) -> None:
    """Append the punishing section of any retrieved definition section."""
    want = [p for d, p in _PUNISHED_IN.items() if d in merged["ids"][0] and p not in merged["ids"][0]]
    if not want:
        return
    got = collection.get(ids=want, include=["documents", "metadatas"])
    for doc_id, doc, meta in zip(got["ids"], got["documents"], got["metadatas"]):
        merged["ids"][0].append(doc_id)
        merged["documents"][0].append(doc)
        merged["metadatas"][0].append(meta)
        merged["distances"][0].append(merged["distances"][0][merged["ids"][0].index(
            next(d for d, p in _PUNISHED_IN.items() if p == doc_id))])


def _selected_sections(client_story: str, n_results: int) -> list[str]:
    """BNS sections the local model picks from the official title list, or []
    when selection is off or the local model is unavailable."""
    import charge_selector
    if not charge_selector.enabled():
        return []
    try:
        return charge_selector.select_sections(client_story, limit=_pool_sizes(n_results)["offences"])
    except Exception as e:  # noqa: BLE001 — selection is an improvement, never a dependency
        console.print(f"[yellow]Section selector unavailable ({type(e).__name__}); "
                      f"using similarity search only.[/yellow]")
        return []


def retrieve_relevant_sections_structured(
    collection: chromadb.Collection, client_story: str, n_results: int = 8
):
    """
    Same retrieval as ``retrieve_relevant_sections``, but also returns a list of
    structured ``source`` dicts so the frontend can show citation provenance.

    Why n_results=8: bumped from 6 to catch sections that previously just missed
    the cutoff (e.g. BNS 115 grievous hurt for an injury fact pattern). Capped at
    8 because Groq's free-tier per-request TPM is 12,000 and 10 sections push the
    prompt to ~12,200. If you upgrade Groq, raise this to 12-15 — there is real
    accuracy headroom above 8.

    Returns: (context_string, sources_list)
    """
    cache = _load_embedding_cache()
    issues = _issue_summary(client_story)
    query_text = f"{client_story}\nLEGAL ISSUES: {issues}" if issues else client_story
    query_embedding = _get_embedding_with_cache(query_text, "retrieval_query", cache)
    results = _query_pools(collection, query_embedding, n_results,
                           _selected_sections(client_story, n_results))

    context_parts = ["=== RETRIEVED LAW — CANDIDATES, NOT A CHARGE LIST ===\n"
                     "Cite only from these. They were found by similarity and include "
                     "look-alike sections: charge a section only when the facts show every "
                     "ingredient in its text.\n"]
    sources = []
    retrieved_bns: set[str] = set()
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
        retrieved_bns.update(re.findall(r"\bBNS(?:\s+Section)?\s+(\d{1,3})\b", doc.split("\n", 1)[0]))

    notes = distinction_notes(retrieved_bns)
    if notes:
        context_parts.append("\n=== DISTINGUISH LOOK-ALIKE SECTIONS (apply before choosing charges) ===")
        context_parts.extend(f"- {n}" for n in notes)

    return "\n".join(context_parts), sources


def retrieve_relevant_sections(
    collection: chromadb.Collection, client_story: str, n_results: int = 8
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
    the ingredients of the offence with the fact that proves each one, and how
    these facts support the CLIENT's position. Cite a section here only if
    every ingredient is met.

 B. SECTIONS THE OPPOSING PARTY MAY USE (against the client):
    - List sections the other side might invoke against the client.
    - For each: punishment, bailable status, and how the CLIENT can defend.
    - If COMPLAINANT: possible false counter-allegations by the accused.
    - If RESPONDENT: the exact sections being threatened/filed against them.

 C. SECTIONS CONSIDERED AND RULED OUT:
    - Look-alike sections from the law above that do NOT apply — one line each
      naming the ingredient the facts do not show.

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
    # Random suffix: two analyses in the same second must never share a file
    # (that would hand one client's case to another). "x" refuses to overwrite.
    filename = f"outputs/case_analysis_{timestamp}_{secrets.token_hex(4)}.txt"

    with open(filename, "x", encoding="utf-8") as f:
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
            ai_response = llm_provider.groq_complete(   # model: GROQ_MODEL
                groq_client,
                [{"role": "system", "content": LEXI_SYSTEM_PROMPT},
                 {"role": "user",   "content": prompt}],
                temperature=0.2,        # Low = precise, consistent legal output
                max_tokens=8192,        # Long enough for full FIR + Legal Notice
            )
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
