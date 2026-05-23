"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Tabular contract review (Day 14 of teardown extension)          ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Upload N contracts (PDF or .docx), and one or more clause-questions
(e.g. "What's the notice period?", "Termination on bankruptcy?", "Governing
law?", "Indemnity cap?").  The system extracts text from each contract,
runs each question against each contract via the LLM, and returns a
matrix:

         | Contract A | Contract B | Contract C |
  Notice |   30 days  |   60 days  |   90 days  |
  Court  |   Mumbai   |   Delhi    |   Bengaluru|
  ...

WHY (vs Legora): Legora's "Tabular Review" is a flagship feature for
M&A due diligence in EU/UK contexts.  Same UX, but for Indian use cases:
rent control agreements, employment contracts (POSH compliance, gratuity,
PF), partnership deeds, NDAs, distributor agreements.  Reuses everything
we already have — file extraction, LLM provider, audit log.

DESIGN: Pure-Python, no new dependencies.  Built on top of the existing
extract_pdf_text() and extract_image_text() in app.py + the new
llm_provider.complete() for inference.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Contract:
    name: str         # Filename or user-given label
    text: str         # Extracted text (PDF/docx -> str)


@dataclass
class Clause:
    """One question to ask of every contract."""
    label: str        # Short label shown as the row header ("Notice period")
    question: str     # Full prompt the LLM gets ("What's the notice period?")


# ════════════════════════════════════════════════════════════════════════════
# Prompt — calibrated for short, comparable cell values
# ════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are LEXI, an Indian contract-review assistant.

You will be shown N contracts and asked a single question. Your job is to
extract the answer to that question from EACH contract, separately, in a
form that fits in a table cell.

RULES:
1. Output STRICT JSON only: a list of objects with keys "contract" (string,
   the contract's name as given) and "answer" (string, the extracted value).
   No markdown, no preface, no explanation outside the JSON.
2. Each "answer" should be 1-12 words. Direct quotes where short; paraphrase
   when the contract's wording is long.
3. If the answer is genuinely absent in a contract, "answer" must be the
   exact string "(not found)". Do not guess.
4. Preserve Indian Rupee notation (₹, INR), section numbers, statute names,
   and any specific dates verbatim.
5. Do not invent numbers, dates, or party names. If you would have to guess,
   return "(not found)".

Example output:

  [{"contract": "Contract A", "answer": "30 days written notice"},
   {"contract": "Contract B", "answer": "(not found)"},
   {"contract": "Contract C", "answer": "60 days, or 90 if for cause"}]
"""


def _build_user_prompt(contracts: list[Contract], clause: Clause) -> str:
    """One LLM call per clause-question; each call sees all contracts."""
    parts = [f"QUESTION: {clause.question}", ""]
    for i, c in enumerate(contracts):
        parts.append(f"━━━ CONTRACT: {c.name} ━━━")
        # Cap each contract at 6,000 chars so we stay well inside the TPM ceiling.
        excerpt = c.text[:6000]
        parts.append(excerpt)
        parts.append("")
    parts.append(f"Now answer for each contract, in the strict JSON format described.")
    return "\n".join(parts)


# ════════════════════════════════════════════════════════════════════════════
# Run the comparison.  Caller passes contracts + clauses + an `llm_call`
# function (so this module stays decoupled from groq/ollama).
# ════════════════════════════════════════════════════════════════════════════
def run_comparison(
    contracts: list[Contract],
    clauses: list[Clause],
    llm_call: Callable[[str, str], str],
) -> dict:
    """
    Args:
      contracts : list of Contract objects (already-extracted text).
      clauses   : list of Clause objects (the rows of the result table).
      llm_call  : function(system_prompt, user_prompt) -> raw_response_text.
                  Decoupled so we can plug either Groq or Ollama.

    Returns: {
      "contracts": [{"name": ...}],
      "rows": [
        {"label": "Notice period",
         "question": "...",
         "cells": {"Contract A": "30 days", "Contract B": "(not found)"}},
        ...
      ],
      "stats": {"clauses": N, "contracts": M, "cells_filled": K}
    }
    """
    if not contracts:
        return {"error": "Provide at least one contract."}
    if not clauses:
        return {"error": "Provide at least one clause-question."}

    rows = []
    filled = 0

    for clause in clauses:
        prompt = _build_user_prompt(contracts, clause)
        raw = llm_call(SYSTEM_PROMPT, prompt)
        cells = _parse_response(raw, [c.name for c in contracts])
        filled += sum(1 for v in cells.values() if v and v != "(not found)")
        rows.append({
            "label": clause.label,
            "question": clause.question,
            "cells": cells,
        })

    return {
        "contracts": [{"name": c.name, "chars": len(c.text)} for c in contracts],
        "rows": rows,
        "stats": {
            "clauses": len(clauses),
            "contracts": len(contracts),
            "cells_filled": filled,
            "cells_total": len(clauses) * len(contracts),
        },
    }


def _parse_response(raw: str, expected_names: list[str]) -> dict:
    """
    Parse the model's JSON output.  Robust to common deviations:
      - Wrapping markdown ```json ... ```
      - Leading/trailing prose despite SYSTEM_PROMPT rule
      - Missing contracts (filled in as "(parse error)")
    """
    out = {name: "(parse error)" for name in expected_names}
    if not raw or not raw.strip():
        return out

    # Strip markdown fences
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?\s*", "", txt)
    txt = re.sub(r"\s*```\s*$", "", txt)

    # Find the first JSON array in the response — handles models that prefix
    # the JSON with one sentence of preamble despite instructions.
    match = re.search(r"\[\s*\{.*?\}\s*\]", txt, re.DOTALL)
    if match:
        txt = match.group(0)

    try:
        parsed = json.loads(txt)
    except Exception:
        return out

    if not isinstance(parsed, list):
        return out

    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        name = entry.get("contract", "")
        ans  = entry.get("answer", "")
        # Try to match against expected_names case-insensitively
        for expected in expected_names:
            if expected.lower() == str(name).lower():
                out[expected] = str(ans)[:200]
                break

    return out


# ════════════════════════════════════════════════════════════════════════════
# Pre-baked clause libraries for the three Indian use-cases we wedge on.
# Frontend offers these as quick-pick chips.
# ════════════════════════════════════════════════════════════════════════════
CLAUSE_LIBRARIES = {
    "rent_agreement": [
        Clause("Monthly rent",       "What is the monthly rent (in INR)?"),
        Clause("Security deposit",   "What is the security deposit amount and refund terms?"),
        Clause("Term / duration",    "What is the duration of the tenancy?"),
        Clause("Notice period",      "What is the notice period for termination?"),
        Clause("Rent escalation",    "What is the annual rent escalation clause?"),
        Clause("Maintenance",        "Who is responsible for maintenance?"),
        Clause("Permitted use",      "What is the permitted use of the premises?"),
        Clause("Lock-in period",     "Is there a lock-in period? If so, how long?"),
        Clause("Stamp duty",         "Who pays the stamp duty and registration charges?"),
        Clause("Jurisdiction",       "Which court has exclusive jurisdiction?"),
    ],
    "employment": [
        Clause("Designation",        "What is the designation / role?"),
        Clause("CTC / salary",       "What is the gross compensation (CTC)?"),
        Clause("Probation period",   "What is the probation period?"),
        Clause("Notice period",      "What is the notice period for resignation?"),
        Clause("Termination",        "Under what circumstances may the employer terminate?"),
        Clause("Non-compete",        "Is there a non-compete or non-solicit clause and its duration?"),
        Clause("Confidentiality",    "What is the confidentiality obligation duration?"),
        Clause("Gratuity / PF",      "What are the gratuity and PF entitlements?"),
        Clause("POSH",               "Is there a Sexual Harassment Prevention (POSH) compliance clause?"),
        Clause("Jurisdiction",       "Which court has jurisdiction?"),
    ],
    "partnership_deed": [
        Clause("Profit-sharing",     "What is the profit-sharing ratio?"),
        Clause("Capital contrib.",   "What is each partner's capital contribution?"),
        Clause("Management",         "Who manages the firm and how are decisions taken?"),
        Clause("Admission/exit",     "What is the process for admitting or expelling a partner?"),
        Clause("Retirement",         "What are the retirement / death of partner provisions?"),
        Clause("Dispute resolution", "What is the dispute-resolution mechanism (arbitration / mediation)?"),
        Clause("Non-compete",        "Is there a non-compete clause for retiring partners?"),
        Clause("Books of accounts",  "Where are the books of accounts kept and who can inspect them?"),
        Clause("Term",               "Is the partnership at-will or for a fixed term?"),
        Clause("Jurisdiction",       "Which court has jurisdiction?"),
    ],
    "nda": [
        Clause("Definition of CI",   "How is 'Confidential Information' defined?"),
        Clause("Direction",          "Is the NDA one-way (unilateral) or mutual?"),
        Clause("Term of obligation", "For how long are the parties bound by confidentiality?"),
        Clause("Permitted use",      "For what purpose may the receiving party use the information?"),
        Clause("Exclusions",         "What categories of information are excluded from confidentiality?"),
        Clause("Return / destruction","What is the return-or-destroy obligation on termination?"),
        Clause("Equitable relief",   "Is the disclosing party entitled to injunctive relief?"),
        Clause("Liquidated damages", "Is there a liquidated-damages clause and the amount?"),
        Clause("Governing law",      "What is the governing law?"),
        Clause("Jurisdiction",       "Which court has exclusive jurisdiction?"),
    ],
    "distributor_agreement": [
        Clause("Territory",          "What is the geographic territory granted?"),
        Clause("Exclusivity",        "Is the distributorship exclusive, sole, or non-exclusive?"),
        Clause("Minimum order",      "What is the minimum order / purchase commitment?"),
        Clause("Pricing",            "How is pricing set; are there discount / rebate terms?"),
        Clause("Term & renewal",     "What is the initial term and the auto-renewal terms?"),
        Clause("Termination",        "Termination grounds and notice period for each side?"),
        Clause("IP / branding",      "What are the trademark / branding usage restrictions?"),
        Clause("Sub-distribution",   "Is sub-distribution / appointment of sub-agents allowed?"),
        Clause("Post-termination",   "Post-termination obligations (stock return, non-solicit)?"),
        Clause("Dispute resolution", "Arbitration seat and governing law?"),
    ],
}
