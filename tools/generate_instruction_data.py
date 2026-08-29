#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Instruction-data generator for the local legal model (Day 26)  ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS DOES
──────────────
Turns the *verified* knowledge base into a fine-tuning dataset so a small local
model (Qwen 2.5 7B / Llama 3.1 8B) can be taught Indian criminal law cold and
served air-gapped through the existing Ollama path (llm_provider.py).

Two kinds of training pairs:
  1. DETERMINISTIC / TEMPLATED (the backbone) — built straight from the fields
     of data/bns_knowledge_base.py, data/bnss_bsa_knowledge_base.py and
     data/legal_corpus/ipc_bns_mapping.json.  Because every answer is a literal
     read of a verified field, these pairs *cannot* hallucinate.  This is the
     same "synthetic data from trusted sources" idea, but safer: no LLM writes
     the gold answer, so there is nothing to spot-check.
  2. LLM-AUGMENTED (diversity, optional --augment) — Groq (already wired, free
     tier) paraphrases each section into a realistic client-scenario question.
     A 10% slice is written to review_sample.jsonl for manual eyeballing.

WHY THE TRAIN/EVAL SPLIT IS SACRED
──────────────────────────────────
The held-out evaluation reduces model quality to one number (section-mapping
accuracy).  That number is only honest if the eval
questions were never in the training set.  So we hold out a deterministic slice
of IPC codes; every pair that touches a held-out code goes to eval, never train.

OUTPUTS (data/finetune/)
  train.jsonl          — chat-format pairs for Unsloth/Axolotl (gitignored, large)
  eval.jsonl           — held-out gold questions for tools/eval_model.py
  review_sample.jsonl  — 10% of LLM-augmented pairs, for manual spot-check

USAGE
  python3 tools/generate_instruction_data.py --no-augment      # deterministic only
  python3 tools/generate_instruction_data.py                   # + Groq augment + Hindi
  python3 tools/generate_instruction_data.py --firm-data path/ # append a firm's pairs
"""

from __future__ import annotations

import argparse
import glob
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()                # so the --augment Groq path sees GROQ_API_KEY
except ImportError:
    pass

import data.bns_knowledge_base as bns_kb

try:
    import data.bnss_bsa_knowledge_base as bnss_bsa_kb
except ImportError:
    bnss_bsa_kb = None

from i18n import HINDI_SYSTEM_INSTRUCTION

# ──────────────────────────────────────────────────────────────────────────────
# Paths + constants
# ──────────────────────────────────────────────────────────────────────────────
MAPPING_PATH = ROOT / "data" / "legal_corpus" / "ipc_bns_mapping.json"
CASE_DIR = ROOT / "data" / "legal_corpus" / "case_summaries"
LANDMARK_PATH = ROOT / "data" / "legal_corpus" / "landmark_judgments.json"
OUT_DIR = ROOT / "data" / "finetune"

# A trimmed, self-contained statement of LEXI's role.  Kept here (rather than
# imported from main.py) so the deterministic path has no heavy dependencies
# (chromadb / google-generativeai) and stays import-light for tests.  Faithful
# to LEXI's rules #1 and #2 in main.py.
SYSTEM_EN = (
    "You are LEXI, an expert assistant on Indian criminal law under the Bharatiya "
    "Nyaya Sanhita (BNS) 2023, which replaced the Indian Penal Code (IPC) 1860. "
    "Answer precisely and professionally. Always cite the BNS section and the IPC "
    "section it replaced. Never invent section numbers."
)
SYSTEM_HI = HINDI_SYSTEM_INSTRUCTION

# Default fraction of IPC mapping codes held out for the eval set.
DEFAULT_HOLDOUT_FRAC = 0.25
DEFAULT_SEED = 7  # matches the repo's lucky number; deterministic by default.


# ──────────────────────────────────────────────────────────────────────────────
# Pure helpers (no network, no heavy imports) — unit-tested in tests/test_pure.py
# ──────────────────────────────────────────────────────────────────────────────
def ipc_code(raw: str) -> str | None:
    """
    Pull the bare IPC section code out of any of the shapes the KB uses:
        "IPC 302"            -> "302"
        "IPC Section 498A"   -> "498A"
        "CrPC Section 154"   -> None  (not an IPC code; BNSS/BSA records)
    Returns None when the string does not reference the IPC.
    """
    if not raw:
        return None
    upper = raw.upper()
    if "N/A" in upper:           # 'IPC N/A' / 'IPC N/A2' = brand-new BNS offence
        return None
    if "IPC" not in upper and "PENAL CODE" not in upper:
        return None
    # last token that looks like 302 / 498A / 304B
    token = ""
    for ch in upper.replace("IPC", " ").replace("SECTION", " "):
        if ch.isdigit() or (ch.isalpha() and token and token[-1].isdigit()):
            token += ch
        elif token:
            break
    return token or None


def bns_number(raw: str) -> str | None:
    """'BNS 103' / 'BNS Section 103' / 'BNS 103(2)' -> '103' (or '103(2)')."""
    if not raw:
        return None
    s = raw.upper().replace("BNS", " ").replace("SECTION", " ").strip()
    out = ""
    for ch in s:
        if ch.isdigit() or ch in "()" or (ch.isalpha() and out and out[-1].isdigit()):
            out += ch
        elif out:
            break
    return out or None


@dataclass
class Pair:
    """One question/answer training example, before chat-wrapping."""
    question: str
    answer: str
    lang: str = "en"
    ipc: str | None = None   # the IPC code this pair touches (for holdout routing)
    source: str = "template"


def chat_example(pair: Pair) -> dict:
    """Wrap a Pair into the OpenAI/Unsloth chat-messages shape."""
    system = SYSTEM_HI if pair.lang == "hi" else SYSTEM_EN
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": pair.question},
            {"role": "assistant", "content": pair.answer},
        ]
    }


# ──────────────────────────────────────────────────────────────────────────────
# Templated-pair builders (deterministic, guaranteed-correct)
# ──────────────────────────────────────────────────────────────────────────────
def mapping_pairs(ipc_key: str, m: dict) -> list[Pair]:
    """From one ipc_bns_mapping.json entry, e.g. 'IPC 302' -> {bns,title,change}."""
    bns = m.get("bns", "")
    bnum = bns_number(bns)
    title = m.get("title", "").strip()
    change = (m.get("change") or "").strip()
    code = ipc_code(ipc_key)
    if m.get("repealed"):
        # IPC section with NO BNS successor (377, 497, 124A): teach the absence,
        # never a fabricated number.
        return [
            Pair(f"What is the BNS equivalent of IPC {code}?",
                 f"IPC Section {code} ({title}). {change}", ipc=code),
            Pair(f"Is IPC {code} still in force under the BNS 2023?",
                 f"No. {change}", ipc=code),
        ]
    if not bnum:
        return []
    if not code:
        # Brand-new BNS offence (organised crime, terrorism) — no IPC ancestor.
        # Teach it as a NEW offence, never as a fake mapping.
        return [
            Pair(f"What is {bns}?",
                 f"{bns} ({title}) is a new offence introduced by the BNS 2023 "
                 f"with no direct IPC equivalent." + (f" {change}." if change else ""),
                 source="template"),
            Pair(f"Is there an IPC equivalent of {bns}?",
                 f"No. {bns} ({title}) is a brand-new BNS 2023 offence with no IPC "
                 f"predecessor.", source="template"),
        ]
    return [
        Pair(f"What is the BNS equivalent of IPC {code}?",
             f"IPC Section {code} ({title}) maps to {bns}."
             + (f" Change: {change}." if change else ""),
             ipc=code),
        Pair(f"Which IPC section did {bns} replace?",
             f"{bns} ({title}) replaced IPC Section {code}.", ipc=code),
        Pair(f"Under the new BNS, what replaced IPC Section {code}?",
             f"IPC Section {code} ({title}) is now {bns} under the BNS 2023.", ipc=code),
        Pair(f"My old file cites Section {code} IPC. What's the new BNS section?",
             f"Section {code} IPC ({title}) is now {bns} under the BNS 2023."
             + (f" {change}." if change else ""),
             ipc=code),
    ]


def mapping_pairs_hi(ipc_key: str, m: dict) -> list[Pair]:
    """Hindi templated mapping pairs — section numbers are script-agnostic, so
    these stay correct while reading naturally to a Hindi-belt practitioner."""
    code = ipc_code(ipc_key)
    bnum = bns_number(m.get("bns", ""))
    title = m.get("title", "").strip()
    if not code or not bnum:
        return []
    return [
        Pair(f"IPC धारा {code} का BNS में समकक्ष कौन सी धारा है?",
             f"IPC धारा {code} ({title}) अब BNS धारा {bnum} है।",
             lang="hi", ipc=code),
    ]


def section_pairs(rec: dict) -> list[Pair]:
    """From one BNS/BNSS/BSA knowledge-base record."""
    section = rec.get("section", "").strip()        # e.g. "BNS Section 85"
    bnum = bns_number(section)
    title = rec.get("title", "").strip()
    old = rec.get("old_ipc", "").strip()
    code = ipc_code(old)
    punishment = (rec.get("punishment") or "").strip()
    bailable = (rec.get("bailable") or "").strip()
    cognizable = (rec.get("cognizable") or "").strip()
    note = (rec.get("transition_note") or "").strip()
    if not section:
        return []

    pairs: list[Pair] = []

    # What is this section?
    summary = f"{section} — {title}."
    if old and old.upper() not in ("N/A", ""):
        summary += f" It replaced {old}."
    if punishment and punishment.upper() != "N/A":
        summary += f" Punishment: {punishment}."
    if note:
        summary += f" {note}"
    pairs.append(Pair(f"What is {section}?", summary, ipc=code))
    pairs.append(Pair(f"Explain {section} ({title}) in brief.", summary, ipc=code))

    # Punishment
    if punishment and punishment.upper() != "N/A":
        pairs.append(Pair(
            f"What is the punishment under {section}?",
            f"Under {section} ({title}), the punishment is: {punishment}.",
            ipc=code))

    # Bailable / cognizable — only when the KB states it (procedural rows are N/A)
    if bailable and bailable.upper().startswith(("BAIL", "NON")):
        verdict = "non-bailable" if bailable.upper().startswith("NON") else "bailable"
        pairs.append(Pair(
            f"Is the offence under {section} bailable or non-bailable?",
            f"The offence under {section} ({title}) is {verdict}.",
            ipc=code))
    if cognizable and cognizable.upper().startswith(("Y", "N")):
        verdict = "cognizable" if cognizable.upper().startswith("Y") else "non-cognizable"
        pairs.append(Pair(
            f"Is {section} a cognizable offence?",
            f"Yes, {section} is {verdict}." if verdict == "cognizable"
            else f"No, {section} is {verdict}.",
            ipc=code))

    return pairs


def section_pairs_hi(rec: dict) -> list[Pair]:
    """Hindi bailable/non-bailable fact pair (highest-value, script-safe)."""
    section = rec.get("section", "").strip()
    bnum = bns_number(section)
    title = rec.get("title", "").strip()
    code = ipc_code(rec.get("old_ipc", ""))
    bailable = (rec.get("bailable") or "").strip().upper()
    if not bnum or not bailable.startswith(("BAIL", "NON")):
        return []
    verdict = "गैर-जमानती" if bailable.startswith("NON") else "जमानती"
    return [Pair(
        f"BNS धारा {bnum} के अंतर्गत अपराध जमानती है या गैर-जमानती?",
        f"BNS धारा {bnum} ({title}) के अंतर्गत अपराध {verdict} है।",
        lang="hi", ipc=code)]


def case_pairs() -> list[Pair]:
    """Best-effort SC-judgment pairs from data/legal_corpus/case_summaries/*.json.
    Defensive: uses whatever fields exist, skips silently if the dir is absent."""
    pairs: list[Pair] = []
    for fp in sorted(glob.glob(str(CASE_DIR / "*.json"))):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        title = (c.get("title") or c.get("case_name") or "").strip()
        holding = (c.get("holding") or c.get("principle")
                   or c.get("summary") or c.get("ratio") or "").strip()
        if not title or not holding:
            continue
        pairs.append(Pair(f"What did the Supreme Court hold in {title}?",
                          f"In {title}, the Supreme Court held: {holding}",
                          source="case"))
    return pairs


def landmark_case_pairs() -> list[Pair]:
    """Rich precedent pairs from landmark_judgments.json so the model cites REAL
    cases (name + citation + good-law status), never invented ones. Directly
    addresses the eval finding that the model gave zero case references."""
    pairs: list[Pair] = []
    try:
        data = json.loads(LANDMARK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return pairs
    for j in data.get("judgments", []):
        case = (j.get("case") or "").strip()
        cite = (j.get("citation") or "").strip()
        ratio = (j.get("ratio") or "").strip()
        status = (j.get("status") or "good_law").replace("_", " ")
        note = (j.get("status_note") or "").strip()
        practice = (j.get("practice") or "").strip()
        court = (j.get("court") or "").strip()
        secs = ", ".join(j.get("sections", []))
        if not case or not ratio:
            continue
        full = f"{case}, {cite}" if cite else case
        pairs.append(Pair(
            f"What did the court hold in {case}?",
            f"In {full} ({court}): {ratio} Good-law status: {status}."
            + (f" {note}" if note else ""),
            source="landmark"))
        pairs.append(Pair(
            f"Is {case} still good law?",
            (f"Status: {status}. {note}" if note else f"Status: {status}."),
            source="landmark"))
        pairs.append(Pair(f"Give the full citation for {case}.",
                          f"{full}.", source="landmark"))
        if practice:
            pairs.append(Pair(
                f"When should an advocate cite {case}?",
                practice + (f" Relevant sections: {secs}." if secs else ""),
                source="landmark"))
        for kw in (j.get("keywords") or [])[:2]:
            pairs.append(Pair(
                f"Which landmark judgment deals with {kw} in Indian criminal law?",
                f"{full} — {ratio[:200]}", source="landmark"))
    return pairs


# Worked case scenarios: client story -> the correct BNS/BNSS/BSA sections applied
# to the facts + the real precedent to cite. Hand-written and KB-accurate; teaches
# the model to reason from facts to law (the pipeline eval's weak spot) and to
# name real cases. ipc=None so they are never holdout-gated.
_SCENARIOS: list[tuple[str, str]] = [
    ("My client's husband and mother-in-law beat her and keep demanding a car as dowry. What sections apply?",
     "Applicable: BNS 85 (cruelty by husband or his relatives, replacing IPC 498A); the demand itself is an offence under the Dowry Prohibition Act 1961; if death results within seven years, BNS 80 (dowry death). Arrest safeguard for the accused: Arnesh Kumar v. State of Bihar (2014) — no automatic arrest for offences up to 7 years; police must first issue a BNSS 35 notice. If police refuse the FIR, cite Lalita Kumari v. Govt. of U.P. (2014) — registration is mandatory."),
    ("A speeding truck hit my client's father at night and drove off without stopping; he died. There was no enmity.",
     "Applicable: BNS 106 (causing death by negligence; sub-section (2) covers hit-and-run where the driver escapes without reporting to police). This is NOT murder or culpable homicide because there was no intention to kill. Rash driving itself is BNS 281. For doctors, note the gross-negligence standard in Jacob Mathew v. State of Punjab (2005)."),
    ("A man threw acid on my client's face because she refused to marry him. He had threatened her twice before.",
     "Applicable: BNS 124(1) (voluntarily causing grievous hurt by use of acid — minimum 10 years up to life, with fine paid to the victim for treatment); an attempt is BNS 124(2). The earlier threats attract BNS 351 (criminal intimidation). For any CCTV or phone evidence, file the BSA 63(4) certificate — Arjun Panditrao Khotkar v. Kailash Gorantyal (2020)."),
    ("A mob of more than ten villagers beat a man to death over a WhatsApp child-lifter rumour; videos identify seven.",
     "Applicable: BNS 103(2) (murder by a group of five or more on grounds such as identity — mob lynching; death or life imprisonment), read with BNS 190 (every member of an unlawful assembly is liable for the common object) and BNS 189 (unlawful assembly). Bystander videos need a BSA 63 certificate to be admissible — Arjun Panditrao Khotkar (2020)."),
    ("A society treasurer collected maintenance money entrusted to him and moved Rs 31 lakh into his own fixed deposits.",
     "Applicable: BNS 316 (criminal breach of trust) — the property was lawfully entrusted and then dishonestly misappropriated, which distinguishes it from cheating (BNS 318). If accounts were falsified, add BNS 344 (falsification of accounts)."),
    ("A man on a motorcycle snatched my client's phone from her hand at a speed-breaker; no weapon, no threat, over in seconds.",
     "Applicable: BNS 304 (snatching — sudden or quick seizing of property from a person). It is NOT robbery (BNS 309), because no force or threat was used, and it is more than ordinary theft (BNS 303). CCTV of the road needs a BSA 63 certificate."),
    ("A fake buyer posing as an army officer sent a QR code; when my client scanned it, Rs 47,000 was debited.",
     "Applicable: BNS 318 (cheating and dishonestly inducing delivery of property, replacing IPC 420) and BNS 319 (cheating by personation) for impersonating an army officer; add IT Act Section 66D for impersonation using a computer resource. Note IT Act 66A is void — Shreya Singhal v. Union of India (2015). Chat screenshots require a BSA 63 certificate."),
    ("Three men demand monthly protection money from my client's shop, beat him with iron rods breaking his arm, and smashed his display cases.",
     "Applicable: BNS 308 (extortion — putting a person in fear of injury to obtain money); BNS 118(2) (grievous hurt by dangerous weapons — iron rods); BNS 351 (criminal intimidation — threat to kill/burn the shop); BNS 324 (mischief — smashed cases). If it is an organised syndicate, BNS 111 (organised crime) or BNS 112 (petty organised crime)."),
    ("The police are refusing to register my client's FIR even though a cognizable offence occurred.",
     "Cite Lalita Kumari v. Govt. of U.P. (2014): registration of an FIR is mandatory once information discloses a cognizable offence. The remedy ladder is the Superintendent of Police, then a Magistrate under BNSS 175(3) — Sakiri Vasu v. State of U.P. (2008). FIR copies must also be uploaded promptly — Youth Bar Association of India v. Union of India (2016)."),
    ("Police are threatening to arrest my client over his wife's cruelty complaint though he received no notice.",
     "Cite Arnesh Kumar v. State of Bihar (2014) and Satender Kumar Antil v. CBI (2022): for offences punishable up to 7 years such as BNS 85, arrest is not automatic; police must record reasons and serve a BNSS 35 notice of appearance. Anticipatory bail lies under BNSS 482 and need not be time-limited — Sushila Aggarwal v. State (NCT of Delhi) (2020)."),
    ("Our murder case rests only on circumstantial evidence. What is the standard?",
     "Apply the five golden principles of circumstantial evidence from Sharad Birdhichand Sarda v. State of Maharashtra (1984): the circumstances must be fully established and the chain so complete that it excludes every reasonable hypothesis except the guilt of the accused. The charge is BNS 103 (murder). Last-seen evidence alone is insufficient without proximity of time and corroboration."),
    ("I have WhatsApp screenshots and CCTV footage as evidence. What must I do to make them admissible?",
     "File the certificate under BSA 63(4) (replacing IEA 65B) — it is a condition precedent for secondary electronic evidence. The governing authority is Arjun Panditrao Khotkar v. Kailash Gorantyal (2020), which affirmed Anvar P.V. (2014) and overruled Shafhi Mohammad (2018). Do not rely on Shafhi Mohammad to skip the certificate."),
    ("A prosecution has charged my client under IT Act Section 66A for a Facebook post.",
     "Section 66A of the IT Act was struck down as unconstitutional in Shreya Singhal v. Union of India (2015); any charge under it is void and should be quashed. If the post insulted a woman's modesty it is BNS 79; online cheating by personation is BNS 319 read with IT Act 66D."),
    ("My client's daughter is 16 and was married off; her husband had intercourse with her.",
     "This is rape: Independent Thought v. Union of India (2017) held that intercourse by a husband with a wife under 18 is rape, so the marital exception does not apply. Charge under BNS 63-65 (rape and rape of a minor) together with the POCSO Act 2012."),
]


def scenario_pairs() -> list[Pair]:
    return [Pair(q, a, source="scenario") for q, a in _SCENARIOS]


# ──────────────────────────────────────────────────────────────────────────────
# Dataset assembly (deterministic) + holdout routing
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Dataset:
    train: list[Pair] = field(default_factory=list)
    eval: list[dict] = field(default_factory=list)   # eval uses a gold schema


def select_holdout(mapping_keys: list[str], frac: float, seed: int) -> set[str]:
    """Deterministically choose the IPC codes reserved for evaluation."""
    codes = sorted({c for k in mapping_keys if (c := ipc_code(k))})
    rng = random.Random(seed)
    rng.shuffle(codes)
    n = max(1, round(len(codes) * frac))
    return set(codes[:n])


def eval_gold_for_holdout(mapping: dict, kb_records: list[dict],
                          holdout: set[str]) -> list[dict]:
    """Build the held-out gold questions tools/eval_model.py will score."""
    gold: list[dict] = []
    for ipc_key, m in mapping.items():
        code = ipc_code(ipc_key)
        bnum = bns_number(m.get("bns", ""))
        if code in holdout and bnum:
            gold.append({
                "id": f"map_{code}",
                "kind": "mapping",
                "question": f"What is the BNS section equivalent to IPC {code}? "
                            f"Answer with the BNS section number.",
                "expected_bns": bnum,
                "expected_ipc": code,
            })
    for rec in kb_records:
        code = ipc_code(rec.get("old_ipc", ""))
        bnum = bns_number(rec.get("section", ""))
        bailable = (rec.get("bailable") or "").strip().upper()
        if code in holdout and bnum and bailable.startswith(("BAIL", "NON")):
            gold.append({
                "id": f"fact_{bnum}_bailable",
                "kind": "fact",
                "question": f"Under BNS Section {bnum}, is the offence bailable "
                            f"or non-bailable?",
                "expected_substring": "non-bailable" if bailable.startswith("NON")
                                      else "bailable",
            })
    return gold


def build_dataset(*, hindi: bool, holdout_frac: float, seed: int) -> Dataset:
    """The deterministic core — no network. Returns train Pairs + eval gold."""
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    kb_records = list(bns_kb.BNS_SECTIONS)
    if bnss_bsa_kb is not None:
        kb_records += list(getattr(bnss_bsa_kb, "BNSS_SECTIONS", []))
        kb_records += list(getattr(bnss_bsa_kb, "BSA_SECTIONS", []))

    holdout = select_holdout(list(mapping.keys()), holdout_frac, seed)
    ds = Dataset()

    # eval gold (held-out only)
    ds.eval = eval_gold_for_holdout(mapping, kb_records, holdout)

    # train: every pair whose IPC code is NOT held out
    def keep(p: Pair) -> bool:
        return p.ipc is None or p.ipc not in holdout

    for ipc_key, m in mapping.items():
        for p in mapping_pairs(ipc_key, m):
            if keep(p):
                ds.train.append(p)
        if hindi:
            for p in mapping_pairs_hi(ipc_key, m):
                if keep(p):
                    ds.train.append(p)

    for rec in kb_records:
        for p in section_pairs(rec):
            if keep(p):
                ds.train.append(p)
        if hindi:
            for p in section_pairs_hi(rec):
                if keep(p):
                    ds.train.append(p)

    for p in case_pairs():        # case pairs have no IPC code → always train
        ds.train.append(p)

    # v1.9 firm-grade upgrade: real precedent (landmark judgments) + worked
    # fact→law scenarios. Neither is holdout-gated (ipc=None).
    for p in landmark_case_pairs():
        ds.train.append(p)
    for p in scenario_pairs():
        ds.train.append(p)

    return ds


# ──────────────────────────────────────────────────────────────────────────────
# LLM augmentation (Groq) — network; lazily imported so the core stays light
# ──────────────────────────────────────────────────────────────────────────────
def augment_with_groq(kb_records: list[dict], n: int, holdout: set[str],
                      seed: int) -> list[Pair]:
    """Ask Groq to write realistic client-scenario questions grounded in a
    section. Best-effort: returns [] (with a warning) if Groq is unavailable."""
    try:
        from main import configure_groq
        client = configure_groq()
    except SystemExit:
        print("  ! GROQ_API_KEY not set — skipping augmentation (--no-augment to silence).")
        return []
    except Exception as e:  # noqa: BLE001 — degrade gracefully on any import error
        print(f"  ! Groq unavailable ({e}) — skipping augmentation.")
        return []

    pool = [r for r in kb_records if ipc_code(r.get("old_ipc", "")) not in holdout]
    rng = random.Random(seed)
    rng.shuffle(pool)
    out: list[Pair] = []
    for rec in pool[:n]:
        section = rec.get("section", "")
        title = rec.get("title", "")
        desc = rec.get("description", "")
        prompt = (
            "Write THREE distinct, realistic questions an Indian client might ask "
            "a lawyer whose situation falls squarely under this section, each with "
            "a 2-3 sentence answer that names the section and its IPC origin. Vary "
            "the client's role (complainant vs accused). "
            "Return strict JSON: {\"pairs\": [{\"q\": ..., \"a\": ...}, ...]}.\n\n"
            f"Section: {section} ({title})\nText: {desc}"
        )
        try:
            comp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": SYSTEM_EN},
                          {"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=900,
                response_format={"type": "json_object"},
            )
            obj = json.loads(comp.choices[0].message.content)
            for item in obj.get("pairs", []):
                q, a = (item.get("q") or "").strip(), (item.get("a") or "").strip()
                if q and a:
                    out.append(Pair(q, a, ipc=ipc_code(rec.get("old_ipc", "")),
                                    source="groq"))
        except Exception as e:  # noqa: BLE001
            print(f"  ! augment failed for {section}: {e}")
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Deployment-specific data — optional, opt-in
# ──────────────────────────────────────────────────────────────────────────────
def firm_pairs(firm_data: str) -> list[Pair]:
    """Read a deployment's own Q&A pairs from a JSONL of {"q","a"} (or
    {"question","answer"}) and append them to the base set, so a model can be
    fine-tuned on that deployment's own consented data. Minimal by design."""
    p = Path(firm_data)
    if not p.exists():
        raise ValueError(f"--firm-data path not found: {firm_data}")
    out: list[Pair] = []
    files = [p] if p.is_file() else sorted(p.glob("*.jsonl"))
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                q = (obj.get("q") or obj.get("question") or "").strip()
                a = (obj.get("a") or obj.get("answer") or "").strip()
                if q and a:
                    out.append(Pair(q, a, source="firm"))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# IO
# ──────────────────────────────────────────────────────────────────────────────
def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Lex-Indic fine-tuning data.")
    ap.add_argument("--augment", action=argparse.BooleanOptionalAction, default=True,
                    help="Groq-augmented scenario pairs (needs GROQ_API_KEY).")
    ap.add_argument("--hindi", action=argparse.BooleanOptionalAction, default=True,
                    help="Include Hindi templated pairs.")
    ap.add_argument("--n-augment", type=int, default=60,
                    help="How many sections to LLM-augment.")
    ap.add_argument("--holdout-frac", type=float, default=DEFAULT_HOLDOUT_FRAC)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--firm-data", default=None,
                    help="Path to a firm's JSONL of {q,a} pairs to append.")
    args = ap.parse_args()

    print("Building deterministic dataset from the verified KB …")
    ds = build_dataset(hindi=args.hindi, holdout_frac=args.holdout_frac, seed=args.seed)
    n_template = len(ds.train)
    print(f"  templated pairs: {n_template}   |   held-out eval questions: {len(ds.eval)}")

    review: list[Pair] = []
    if args.augment:
        with open(MAPPING_PATH, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        holdout = select_holdout(list(mapping.keys()), args.holdout_frac, args.seed)
        kb_records = list(bns_kb.BNS_SECTIONS)
        if bnss_bsa_kb is not None:
            kb_records += list(getattr(bnss_bsa_kb, "BNSS_SECTIONS", []))
            kb_records += list(getattr(bnss_bsa_kb, "BSA_SECTIONS", []))
        print(f"Augmenting {args.n_augment} sections via Groq …")
        aug = augment_with_groq(kb_records, args.n_augment, holdout, args.seed)
        ds.train += aug
        # 10% of augmented pairs → manual review sample
        rng = random.Random(args.seed)
        review = [p for p in aug if rng.random() < 0.10]
        print(f"  augmented pairs: {len(aug)}   (review sample: {len(review)})")

    if args.firm_data:
        fp = firm_pairs(args.firm_data)
        ds.train += fp
        print(f"  firm pairs: {len(fp)}")

    # shuffle train for good measure (deterministic)
    random.Random(args.seed).shuffle(ds.train)

    train_rows = [chat_example(p) for p in ds.train]
    write_jsonl(OUT_DIR / "train.jsonl", train_rows)
    write_jsonl(OUT_DIR / "eval.jsonl", ds.eval)
    if review:
        write_jsonl(OUT_DIR / "review_sample.jsonl", [chat_example(p) for p in review])

    n_hi = sum(1 for p in ds.train if p.lang == "hi")
    print("\n✓ wrote:")
    print(f"    {OUT_DIR/'train.jsonl'}   ({len(train_rows)} pairs, {n_hi} Hindi)")
    print(f"    {OUT_DIR/'eval.jsonl'}    ({len(ds.eval)} held-out gold questions)")
    if review:
        print(f"    {OUT_DIR/'review_sample.jsonl'}  ({len(review)} pairs to eyeball)")
    print("\nNext: upload train.jsonl to a GPU box and run training/train_qlora.py.")


if __name__ == "__main__":
    main()
