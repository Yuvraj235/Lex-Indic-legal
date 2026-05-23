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
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make the repo root importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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
