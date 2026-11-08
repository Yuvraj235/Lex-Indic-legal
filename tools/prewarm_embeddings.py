#!/usr/bin/env python3
"""
Pre-warm the embedding cache for every document in the index.

After this runs, every BNS / BNSS / BSA / case / circular / mapping / judgment
document has its embedding stored on disk — data/legal_corpus/embedding_cache.json
for Gemini (committed, so deploys start warm) or embedding_cache.local.json for
a local Ollama embedder (gitignored).
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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from main import (
    configure_gemini_embeddings,
    embeddings_provider,
    embedding_texts,
    knowledge_base_documents,
    _embedding_cache_file,
    _embedding_cache_key,
    _get_embedding_with_cache,
    _load_embedding_cache,
    _save_embedding_cache,
)


def all_documents() -> list[tuple[str, str]]:
    """[(doc_id, text that gets embedded), …] — exactly what build_rag_knowledge_base embeds."""
    docs, metas, ids, _ = knowledge_base_documents()
    return list(zip(ids, embedding_texts(docs, metas)))


def main():
    parser = argparse.ArgumentParser(description="Pre-warm the embedding cache.")
    parser.add_argument("--check", action="store_true", help="Only report cache state; do not embed anything.")
    args = parser.parse_args()

    docs = all_documents()
    print(f"Total KB documents: {len(docs)}")
    cache = _load_embedding_cache()
    print(f"Cache file: {_embedding_cache_file()}  ({len(cache)} entries currently)")

    misses = []
    for doc_id, doc_text in docs:
        if _embedding_cache_key(doc_text, "retrieval_document") not in cache:
            misses.append((doc_id, doc_text))

    print(f"Cache misses: {len(misses)} of {len(docs)}")
    if args.check:
        if misses:
            print("Sample missing IDs:", [m[0] for m in misses[:5]])
        sys.exit(0 if not misses else 1)

    if not misses:
        print("Nothing to do — cache is fully warm. ✓")
        return

    if embeddings_provider() == "gemini":
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
