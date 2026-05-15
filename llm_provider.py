"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Pluggable LLM provider (Day 13)                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Abstract the inference call behind a single function so /analyze and
/chat can swap between Groq (default, US-hosted, fast) and Ollama (local,
zero-sub-processors, slower).

WHY THIS MATTERS COMMERCIALLY: The DPDP trust page promises that a customer
can opt out of Groq + Gemini and run entirely on their own machine.  Until
this module, that was a promise without code.  Now it's a single env-var
flip:

    LLM_PROVIDER=ollama     OLLAMA_MODEL=llama3.3:70b

Activation by zero-config: if the user has Ollama running on the default
host (http://localhost:11434), we detect and use it automatically when
LLM_PROVIDER=ollama is set.

THE PROVIDERS:
  - 'groq'    Groq Llama-3.3-70B via groq SDK.  Fast (~5s), US-hosted.
  - 'ollama'  Local Llama via Ollama's HTTP API.  Slower (depends on GPU),
              zero data leaves the machine.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


def get_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "groq").lower()


def ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.3:70b")


def is_ollama_reachable(timeout: float = 1.5) -> bool:
    """Quick TCP-probe so the UI can show 'Ollama detected' or fall back."""
    try:
        with urllib.request.urlopen(f"{ollama_host()}/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════════════
# Public API — call this from /analyze and /chat.
# Same signature regardless of provider.
# ════════════════════════════════════════════════════════════════════════════
def complete(
    *,
    system_messages: list[str],
    user_message: str,
    temperature: float = 0.2,
    max_tokens: int = 8192,
    timeout_s: int = 180,
) -> dict:
    """
    Generate a completion.

    Returns:  { 'text': str, 'model': str, 'provider': str, 'duration_ms': int }

    Raises if all providers fail.
    """
    provider = get_provider()
    if provider == "ollama":
        return _complete_ollama(
            system_messages=system_messages,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )
    # default = groq via the existing groq SDK; we don't import it here to
    # keep this module dependency-light.  The caller (app.py) already knows
    # how to call Groq; provider='groq' means "let the caller do it".
    return {"text": None, "model": None, "provider": "groq", "delegate": True}


def _complete_ollama(
    *,
    system_messages: list[str],
    user_message: str,
    temperature: float,
    max_tokens: int,
    timeout_s: int,
) -> dict:
    """
    Ollama's /api/chat endpoint — drop-in replacement for OpenAI's
    chat-completions shape.  No SDK needed; pure stdlib.
    """
    model = ollama_model()
    messages = [{"role": "system", "content": s} for s in system_messages]
    messages.append({"role": "user", "content": user_message})

    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{ollama_host()}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Ollama call failed at {ollama_host()}: {e.reason}. "
            f"Is `ollama serve` running and is the model '{model}' pulled? "
            f"Try: `ollama pull {model}` then restart Lex-Indic."
        ) from e

    text = (payload.get("message") or {}).get("content") or ""
    return {
        "text": text,
        "model": f"ollama/{model}",
        "provider": "ollama",
        "duration_ms": int((time.monotonic() - start) * 1000),
    }


def status() -> dict:
    """Diagnostic — what's the current provider and is it reachable?"""
    provider = get_provider()
    return {
        "provider": provider,
        "ollama_host": ollama_host(),
        "ollama_model": ollama_model(),
        "ollama_reachable": is_ollama_reachable() if provider == "ollama" else None,
    }
