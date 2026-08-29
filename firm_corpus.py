"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Per-deployment training corpus builder                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Turn one firm's own matters + uploaded precedent documents into the
{"q","a"} instruction pairs that tools/generate_instruction_data.py --firm-data
consumes — so a model can be fine-tuned on that firm's own consented data and run
on its own server.

DPDP: every pair is redacted of the matter's party names before it leaves this
module. The redaction is the load-bearing guarantee and is unit-tested.

  core (pure):  redact(text, names), matter_to_pairs(matter, doc_texts)
  I/O:          build_firm_pairs(firm_id)  (reads matters.py + uploads.py)
"""

from __future__ import annotations

import re

PLACEHOLDERS = ("[CLIENT]", "[OPPOSING PARTY]")


def redact(text: str, names: list[tuple[str, str]]) -> str:
    """Replace each (name, placeholder) — case-insensitive — so party identities
    never enter the training data. Short/blank names are ignored to avoid
    over-redaction."""
    out = text or ""
    for name, placeholder in names:
        name = (name or "").strip()
        if len(name) >= 3:
            out = re.sub(re.escape(name), placeholder, out, flags=re.IGNORECASE)
    return out


def matter_to_pairs(matter: dict, doc_texts: list[str] | None = None) -> list[dict]:
    """Build redacted {q,a} pairs from one matter dict + any precedent doc texts."""
    mt = (matter.get("matter_type") or "general").strip() or "general"
    names = [
        (matter.get("client_name", ""), PLACEHOLDERS[0]),
        (matter.get("opposing_party", ""), PLACEHOLDERS[1]),
    ]
    pairs: list[dict] = []
    desc = (matter.get("description") or "").strip()
    if len(desc) >= 20:
        pairs.append({
            "q": f"Summarise how the firm has approached a {mt} matter.",
            "a": redact(desc, names),
        })
    for t in (doc_texts or []):
        t = redact(t, names).strip()
        if len(t) >= 80:
            pairs.append({
                "q": f"Provide the firm's drafting style for a {mt} matter.",
                "a": t[:1500],
            })
    return pairs


# ──────────────────────────────────────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────────────────────────────────────
def _matter_doc_texts(matter_id: str) -> list[str]:
    """Best-effort extraction of a matter's uploaded precedent documents."""
    try:
        import uploads as uploads_module
        import migration_audit as ma
    except ImportError:
        return []
    texts: list[str] = []
    for meta in uploads_module.list_files(matter_id):
        try:
            path = uploads_module.get_file_path(matter_id, meta.get("file_id", ""))
            if path and path.exists() and path.suffix.lower() in ma.SUPPORTED_SUFFIXES:
                texts.append(ma.extract_text(path))
        except Exception:  # noqa: BLE001 — one bad file shouldn't void ingestion
            continue
    return texts


def build_firm_pairs(firm_id: str) -> list[dict]:
    """Pull a firm's matters (+ uploaded precedents) → redacted {q,a} pairs."""
    if not firm_id:
        raise ValueError("firm_id is required.")
    import matters as matters_module
    pairs: list[dict] = []
    for m in matters_module.list_matters(firm_id=firm_id):
        pairs += matter_to_pairs(m, _matter_doc_texts(m.get("id", "")))
    return pairs
