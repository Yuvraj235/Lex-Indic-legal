#!/usr/bin/env python3
"""
Pre-warm the Gemini embedding cache for every document in the KB.

After this runs, every BNS / BNSS / BSA / case / circular / mapping document
has its embedding stored in data/legal_corpus/embedding_cache.json on disk.
On subsequent server starts, Lex-Indic reads the cache instead of calling
Gemini — meaning a customer running LLM_PROVIDER=ollama can air-gap the
deployment AND still serve every indexed-doc query without an outbound
Gemini call (only the query embedding itself still calls Gemini at runtime).

Why this is the "Option A" path from docs/OLLAMA_RUNBOOK.md:
  Option A pre-bakes the corpus embeddings; only query embedding still hits
  Gemini.  Option B is a deeper code change (swap to sentence-transformers).

Usage:
  python3 tools/prewarm_embeddings.py            # warm everything
  python3 tools/prewarm_embeddings.py --check    # just report cache hit rate
"""

from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import data.bns_knowledge_base as bns_kb
import data.download_legal_corpus as corpus
try:
    import data.bnss_bsa_knowledge_base as bnss_bsa_kb
except ImportError:
    bnss_bsa_kb = None

from main import (
    configure_gemini_embeddings,
    _get_embedding_with_cache,
    _load_embedding_cache,
    _save_embedding_cache,
    EMBEDDING_CACHE_FILE,
)


def all_documents() -> list[tuple[str, str]]:
    """Return [(doc_id, doc_text), …] for every document the RAG pipeline indexes."""
    out = []
    bns_docs, _, bns_ids = bns_kb.get_all_documents()
    out += list(zip(bns_ids, bns_docs))
    if bnss_bsa_kb is not None:
        b_docs, _, b_ids = bnss_bsa_kb.get_all_documents()
        out += list(zip(b_ids, b_docs))
    c_docs, _, c_ids = corpus.get_corpus_as_rag_documents()
    out += list(zip(c_ids, c_docs))
    return out


def main():
    parser = argparse.ArgumentParser(description="Pre-warm the embedding cache.")
    parser.add_argument("--check", action="store_true", help="Only report cache state; do not call Gemini.")
    args = parser.parse_args()

    docs = all_documents()
    print(f"Total KB documents: {len(docs)}")
    cache = _load_embedding_cache()
    print(f"Cache file: {EMBEDDING_CACHE_FILE}  ({len(cache)} entries currently)")

    misses = []
    for doc_id, doc_text in docs:
        key = hashlib.md5(f"retrieval_document:{doc_text}".encode()).hexdigest()
        if key not in cache:
            misses.append((doc_id, doc_text))

    print(f"Cache misses: {len(misses)} of {len(docs)}")
    if args.check:
        if misses:
            print("Sample missing IDs:", [m[0] for m in misses[:5]])
        sys.exit(0 if not misses else 1)

    if not misses:
        print("Nothing to do — cache is fully warm. ✓")
        return

    configure_gemini_embeddings()
    print(f"Embedding {len(misses)} documents…")
    for i, (doc_id, doc_text) in enumerate(misses, 1):
        try:
            _get_embedding_with_cache(doc_text, "retrieval_document", cache)
            if i % 10 == 0 or i == len(misses):
                print(f"  …{i}/{len(misses)}  (saving)")
                _save_embedding_cache(cache)
        except Exception as e:
            print(f"  FAIL {doc_id}: {e}")

    _save_embedding_cache(cache)
    print(f"Done. Cache now at {len(cache)} entries.")
    print()
    print("Next: confirm Lex-Indic can serve queries without Gemini after this:")
    print("  GEMINI_API_KEY= python3 -c \"from main import build_rag_knowledge_base; build_rag_knowledge_base()\"")
    print("If it errors, the cache is missing entries (re-run this script).")


if __name__ == "__main__":
    main()
