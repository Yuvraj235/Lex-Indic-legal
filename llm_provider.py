"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Pluggable LLM provider (Day 13)                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Abstract the inference call behind a single function so /analyze and
/chat can swap between Groq (default, US-hosted, fast) and Ollama (local,
slower).

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
  - 'ollama'  Local Llama via Ollama's HTTP API.  Slower (depends on GPU);
              generation stays on the machine.

Generation is only half the path: RAG search embeds the client's story too
(main.embeddings_provider — Google Gemini by default). Nothing leaves the
machine only with LLM_PROVIDER=ollama AND EMBEDDINGS_PROVIDER=ollama;
status()["fully_local"] reports exactly that.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request


def get_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "groq").lower()


# Groq retires models (llama-3.3-70b-versatile was removed in 2026 and every
# analysis failed until this became a setting). Benchmark a replacement with
# tools/eval_pipeline.py before changing the default.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def groq_model() -> str:
    return (os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL).strip()


# Characters some models emit inside citations ("Section\u202f302"): they
# break the citation verifier's regexes and can't be drawn by the PDF fonts.
_SPACE_LIKE = dict.fromkeys(map(ord, "\u00a0\u2007\u2009\u200a\u202f\u205f\u3000"), " ")
_SPACE_LIKE.update({ord("\u2011"): "-", ord("\u2010"): "-", ord("\u200b"): None,
                    ord("\ufeff"): None})
_THINK = re.compile(r"<think>.*?</think>\s*", re.S)


def clean_model_text(text: str) -> str:
    """Normalise model output before anything parses, verifies or prints it."""
    return _THINK.sub("", (text or "").translate(_SPACE_LIKE))


def active_model() -> str:
    """The model actually answering, for audit records."""
    return f"ollama/{ollama_model()}" if get_provider() == "ollama" else groq_model()


def groq_complete(client, messages: list[dict], *, temperature: float = 0.2,
                  max_tokens: int = 4096, model: str | None = None, **extra) -> str:
    """One Groq chat call with the configured model, returning cleaned text.
    Reasoning models spend completion tokens on hidden reasoning, so they get
    extra budget on top of `max_tokens` (the answer's budget)."""
    model = model or groq_model()
    kwargs = {"model": model, "messages": messages, "temperature": temperature,
              "max_completion_tokens": max_tokens, **extra}
    if model.startswith("openai/gpt-oss"):
        kwargs["reasoning_effort"] = os.getenv("GROQ_REASONING_EFFORT", "medium")
        kwargs["max_completion_tokens"] = max_tokens + 4096
    elif model.startswith("qwen/"):
        kwargs["reasoning_format"] = "hidden"
        kwargs["max_completion_tokens"] = max_tokens + 4096
    resp = client.chat.completions.create(**kwargs)
    return clean_model_text(resp.choices[0].message.content or "")


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

    text = clean_model_text((payload.get("message") or {}).get("content") or "")
    return {
        "text": text,
        "model": f"ollama/{model}",
        "provider": "ollama",
        "duration_ms": int((time.monotonic() - start) * 1000),
    }


def status() -> dict:
    """Diagnostic — what's the current provider and is it reachable?"""
    provider = get_provider()
    embeddings = (os.getenv("EMBEDDINGS_PROVIDER") or "gemini").strip().lower()
    return {
        "provider": provider,
        "groq_model": groq_model() if provider == "groq" else None,
        "embeddings_provider": embeddings,
        # True only when neither generation nor RAG search uses a third party.
        "fully_local": provider == "ollama" and embeddings == "ollama",
        "ollama_host": ollama_host(),
        "ollama_model": ollama_model(),
        "ollama_reachable": is_ollama_reachable() if provider == "ollama" else None,
    }
