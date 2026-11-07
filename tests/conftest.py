"""
pytest fixtures shared across the test suite.

Design rule: zero network calls in tests.  The Flask app, Groq, Gemini,
and Ollama all get monkey-patched to fakes so the whole suite runs
in under 5 seconds.  Tests that genuinely need a real LLM are marked
@pytest.mark.network and skipped by default.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the repo root importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Deterministic secrets for the suite, set before app.py's load_dotenv() so a
# developer's real .env can't leak in. LEX_ENV stays unset: tests run with
# production behaviour unless a test opts into development explicitly.
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef"
os.environ["AUDIT_HASH_SALT"] = "test-audit-salt-0123456789abcdef"
os.environ.pop("LEX_ENV", None)
os.environ.pop("ADMIN_TOKEN", None)


@pytest.fixture(autouse=True)
def isolate_outputs(tmp_path, monkeypatch):
    """Re-route every file path that the app writes to into a per-test temp
    dir, so tests can't pollute the real outputs/ folder and don't see
    state from each other."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "outputs").mkdir()
    monkeypatch.chdir(work)
    # Some modules cache module-level Path objects; rebind them.
    yield work


@pytest.fixture(autouse=True)
def no_background_network(monkeypatch):
    """The webhook retry drainer is a process-wide daemon thread that would
    outlive each test's temp dir and poll the real outputs/ folder, and DNS
    is network. Tests that need a resolver install `fake_dns`."""
    import webhooks
    monkeypatch.setattr(webhooks, "_ensure_drainer", lambda: None)
    import api_keys
    api_keys._RATE_BUCKETS.clear()   # per-IP limits are process-global

    def _no_dns(host, port):
        raise ValueError(f"DNS disabled in tests (looked up {host!r})")
    monkeypatch.setattr(webhooks, "_resolve_host", _no_dns)


@pytest.fixture
def fake_dns(monkeypatch):
    """Resolve hostnames from a dict; unknown names get a public address."""
    import webhooks
    table: dict[str, list[str]] = {}
    monkeypatch.setattr(webhooks, "_resolve_host",
                        lambda host, port: table.get(host, ["93.184.215.14"]))
    return table


@pytest.fixture
def fake_llm_call():
    """A llm_call(system, user) → str stand-in for tabular tests."""
    def _call(system_prompt: str, user_prompt: str) -> str:
        # Generate a plausible JSON response by parsing the contract names
        # out of the prompt and returning a fixed-form answer per contract.
        import re
        names = re.findall(r"━━━ CONTRACT: ([^ ━\n]+(?: [^ ━\n]+)*) ━━━", user_prompt)
        if not names:
            return '[]'
        return json.dumps([
            {"contract": n, "answer": f"test answer for {n}"}
            for n in names
        ])
    return _call


# ────────────────────────────── App fixture ────────────────────────────────
# We import app.py once per test session with all the slow / network-dependent
# pieces patched out.  The fixture below builds a Flask test client.

@pytest.fixture(scope="session")
def app():
    # Patch the expensive module-level work BEFORE importing app.py.
    # The patches need to survive for the lifetime of the session.

    # 1) Stub the Groq client so it never hits the network
    fake_groq = MagicMock()
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=MagicMock(content=(
        "SECTION 1: IMMEDIATE CLIENT ADVISORY\n"
        "Test advisory.\n\n"
        "SECTION 2: LEGAL ANALYSIS UNDER BNS 2023\n"
        "Test legal analysis citing BNS Section 304.\n\n"
        "SECTION 3: CASE STRATEGY & STRENGTH ASSESSMENT\n"
        "Test strategy.\n\n"
        "SECTION 4: DRAFT FIRST INFORMATION REPORT (FIR)\n"
        "Test FIR.\n\n"
        "SECTION 5: DRAFT LEGAL NOTICE\n"
        "Test notice.\n\n"
        "SECTION 6: POLICE HELP REPORT\n"
        "Test police report.\n"
    ))) ]
    fake_groq.chat.completions.create.return_value = fake_completion

    # 2) Stub ChromaDB collection to return canned hits
    fake_collection = MagicMock()
    fake_collection.query.return_value = {
        "documents":  [["BNS Section 304 doc text", "BNS Section 115 doc text"]],
        "metadatas":  [[
            {"section": "BNS Section 304", "title": "Snatching", "old_ipc": "(NEW)",
             "punishment": "Up to 3 years + fine", "bailable": "Non-bailable",
             "cognizable": "Yes", "transition_note": "..."},
            {"section": "BNS Section 115", "title": "Hurt", "old_ipc": "IPC 323",
             "punishment": "Up to 1 year + fine", "bailable": "Bailable",
             "cognizable": "Yes", "transition_note": "..."},
        ]],
        "distances":  [[0.3, 0.4]],
        "ids":        [["bns_304", "bns_115"]],
    }
    fake_collection.count.return_value = 2
    fake_collection.get.return_value = {"ids": ["bns_304", "bns_115"]}

    # 3) Stub Gemini embedding
    fake_gemini_embed = {"embedding": [0.1] * 768}

    # 4) Patch everything before app.py runs its top-level code
    with patch("main.Groq") as MockGroq, \
         patch("main.build_rag_knowledge_base", return_value=fake_collection), \
         patch("main.genai.embed_content", return_value=fake_gemini_embed), \
         patch("main.configure_groq", return_value=fake_groq), \
         patch("main._get_embedding_with_cache", return_value=[0.1] * 768):
        MockGroq.return_value = fake_groq

        # Force-reload the app module so the patches take effect
        if "app" in sys.modules:
            del sys.modules["app"]
        import app as flask_app_module

        # Also patch the live groq_client and rag_collection on the module
        flask_app_module.groq_client = fake_groq
        flask_app_module.rag_collection = fake_collection

        # Patch the analyze flow's retrieval helper so it doesn't try Gemini
        from main import _normalize_source
        def fake_retrieve(collection, story, n_results=8):
            sources = [
                _normalize_source(1, "bns_304", "snatching text",
                                  {"section": "BNS Section 304", "title": "Snatching",
                                   "old_ipc": "(NEW)", "punishment": "Up to 3 years",
                                   "bailable": "Non-bailable", "cognizable": "Yes",
                                   "transition_note": "..."}, 70.0),
            ]
            return ("=== RETRIEVED ===\n[SECTION 1 — 70.0%]\nsnatching text", sources)
        flask_app_module.retrieve_relevant_sections_structured = fake_retrieve

        yield flask_app_module.app


@pytest.fixture
def client(app):
    return app.test_client()
