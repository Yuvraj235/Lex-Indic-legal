"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — DPDP compliance posture (Day 6 of Legora teardown)              ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Generates a downloadable compliance pack (.docx) containing:
  - Data-flow narrative (where every byte of client data goes)
  - Standard procurement-questionnaire answers (DPDP Act 2023 + general
    information-security 28 questions)
  - The audit-log schema
  - SLA + retention defaults
  - Sub-processor list (Groq, Google Gemini, ChromaDB)

A firm GC opens this BEFORE signing.  Legora's compliance pack is EU/US
GDPR + HIPAA; ours is DPDP + India-region-specific.

Why a separate module: the trust page (/trust) can either render this as
HTML in-line, or hand it over as a .docx download for the GC's case file.
Single source of truth for the answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CompliancePosture:
    company:          str = "Lex-Indic"
    product:          str = "Lex-Indic BNS Transition Engine v1.3"
    contact_dpo:      str = "yuvraj@example.com  (Yuvraj Pratap Singh — Founder / Provisional DPO)"
    last_updated:     str = field(default_factory=lambda: datetime.now().strftime("%d %B %Y"))


POSTURE = CompliancePosture()


# ════════════════════════════════════════════════════════════════════════════
# THE 28 QUESTIONS — answers a firm GC actually asks before signing.
# Each row: (category, question, answer).  Use these to populate the trust
# page UI, the procurement-questionnaire PDF, and the data-flow narrative.
# ════════════════════════════════════════════════════════════════════════════
QUESTIONS: list[tuple[str, str, str]] = [

    # ─── 1. DPDP Act 2023 ──────────────────────────────────────────────
    ("DPDP Act 2023",
     "Are you a Data Fiduciary under DPDP Act 2023?",
     "Yes. Lex-Indic determines the purposes and means of processing client "
     "stories submitted by an empanelled advocate, so we qualify as a Data "
     "Fiduciary under §2(i). The advocate's firm acts as a separate Data "
     "Fiduciary for the underlying client matter — Lex-Indic acts on the "
     "firm's lawful instruction (§6)."),

    ("DPDP Act 2023",
     "Is the personal data of Data Principals processed only for the "
     "specified purpose?",
     "Yes. Client story text is processed solely to (a) retrieve relevant "
     "BNS sections via embedding-based search, and (b) generate the six "
     "legal sections returned to the requesting advocate. We do not "
     "process the data for advertising, model training, profiling, or "
     "any cross-customer analytics."),

    ("DPDP Act 2023",
     "Where is the data stored?  Is it transferred outside India?",
     "Default deployment: all data — including audit logs and generated "
     "PDFs — is stored on the customer's own server in India. Lex-Indic "
     "does not operate a SaaS multi-tenant cloud. For the on-premise "
     "deployment, no data ever leaves the customer's VPC. "
     "Sub-processor exception: the client story is transmitted to Groq "
     "(US) and Google Gemini (US) for inference and embeddings. Customer "
     "may opt out by hosting Llama-3.3-70B locally via Ollama (documented "
     "alternative), in which case zero data leaves India."),

    ("DPDP Act 2023",
     "How is consent obtained from the Data Principal (the firm's client)?",
     "Consent is the responsibility of the empanelled advocate, who has "
     "the existing solicitor-client privilege relationship with the Data "
     "Principal. Lex-Indic surfaces a disclaimer on every generated brief "
     "stating the document is AI-assisted and must be reviewed by a "
     "licensed advocate. The audit log records each request's hashed "
     "story so the advocate can demonstrate the consent chain to the SLSA "
     "/ regulator."),

    ("DPDP Act 2023",
     "How is data-minimisation implemented?",
     "Audit logs store SHA-256 (deployment-salted) hashes of client "
     "stories, never the raw text. Story length, retrieved-source IDs, "
     "and latency are stored as numbers and IDs. The only place raw text "
     "is persisted is the customer's outputs/ folder, which the customer "
     "controls and may delete at any time."),

    ("DPDP Act 2023",
     "How are Data Principal rights (access / correction / erasure) handled?",
     "All rights are exercised through the advocate. Data Principals "
     "contact their advocate, who has both the original story and the "
     "generated brief in their case file. Lex-Indic provides erasure "
     "tooling (tools/erase_matter.py): given an audit request_id, the "
     "tool removes the corresponding raw story, generated PDF, and "
     "embedding cache entries. Standard SLA: 7 days."),

    # ─── 2. Information security ───────────────────────────────────────
    ("Information security",
     "Encryption in transit?",
     "TLS 1.2+ enforced on all endpoints when --https mode is used. The "
     "dev cert is self-signed; production deployments use the customer's "
     "wildcard certificate or a Let's Encrypt cert."),

    ("Information security",
     "Encryption at rest?",
     "Filesystem-level encryption is the responsibility of the customer's "
     "OS layer (LUKS, FileVault, BitLocker). Lex-Indic does not encrypt "
     "individual artefacts on disk because the engine reads them "
     "continuously during the inference cycle; whole-disk encryption is "
     "the simpler and stronger control."),

    ("Information security",
     "Authentication and access control?",
     "Single-tenant deployments rely on the customer's existing network "
     "isolation (firewall, VPN). For multi-firm deployments (Q4 roadmap), "
     "SSO via SAML 2.0 / OIDC is the supported model with per-firm "
     "tenant isolation enforced at the request-routing layer."),

    ("Information security",
     "Audit logging?",
     "Every /analyze and /chat request writes one JSONL record to "
     "outputs/audit/audit-YYYY-MM-DD.log with: request_id (UUIDv4), "
     "timestamp (UTC ISO 8601), endpoint, client_ip, hashed story, "
     "retrieved source IDs, model name, status, duration_ms, response "
     "character count, and PDF filename. Files rotate daily and are "
     "append-only on the application layer. fsync after each write."),

    ("Information security",
     "Penetration testing?",
     "Pre-revenue: external one-off pentest scheduled before first paid "
     "customer (Q3 2026 target). Post-revenue: semi-annual via a "
     "CERT-Empanelled auditor (Sectona / Tata Communications recommended)."),

    ("Information security",
     "Vulnerability management?",
     "Dependency pinning in requirements.txt; weekly `pip list --outdated` "
     "review; CVE feed from python.org. Production: Dependabot enabled on "
     "the GitHub repo."),

    # ─── 3. Operations ─────────────────────────────────────────────────
    ("Operations",
     "What's the backup policy?",
     "Customer's responsibility. Lex-Indic ships a single-process Flask "
     "app; standard nightly tar of outputs/ to S3 / MinIO / customer "
     "backup target is the recommended pattern. tools/backup_check.py "
     "verifies a backup is restorable."),

    ("Operations",
     "What's the disaster-recovery RTO/RPO?",
     "Single-server deployment: RTO 1 hour (re-deploy from git, restore "
     "outputs/ from backup), RPO 24 hours (nightly backup default). "
     "For HA: customers may run two Flask processes behind a load balancer "
     "and replicate outputs/ via rsync; RPO drops to 5 minutes."),

    ("Operations",
     "What's the change-management process?",
     "All code changes flow through a GitHub PR with at least one "
     "reviewer for v1.4+. The /audit endpoint surfaces the version "
     "currently running so customers can correlate behaviour with a "
     "specific commit. Hotfix policy: documented in tools/RUNBOOK.md."),

    ("Operations",
     "Incident response?",
     "DPO contact: " + POSTURE.contact_dpo + ". P1 incident definition: "
     "any unauthorised access to the audit log, the outputs/ folder, "
     "or the .env file. Notification SLA: 72 hours to the affected "
     "customer and to the Data Protection Board (per DPDP Act 2023 "
     "§8(6))."),

    # ─── 4. Sub-processors ─────────────────────────────────────────────
    ("Sub-processors",
     "List your sub-processors.",
     "(1) Groq Inc. (US) — inference for Llama-3.3-70B. Data shared: "
     "client story + retrieved BNS sections + system prompt. Retention: "
     "Groq's stated policy is no retention beyond the request lifecycle. "
     "(2) Google LLC (US) — Gemini embedding-001 for vector search. "
     "Data shared: client story (for query embedding); document text "
     "(for KB indexing — public BNS text only, no PII). (3) For "
     "deployments that opt out of (1) and (2), local Llama-3.3-70B via "
     "Ollama + local sentence-transformers embeddings remove all "
     "sub-processors."),

    ("Sub-processors",
     "Are sub-processors notified to customers when added?",
     "Yes. Any new sub-processor requires a 30-day notice to existing "
     "customers via the trust page. Customers may object and trigger "
     "the on-premise / no-sub-processor deployment path."),

    # ─── 5. Logging and monitoring ─────────────────────────────────────
    ("Logging",
     "What is retained?  For how long?",
     "Audit logs: 365 days by default (customer-configurable). Raw "
     "client stories in outputs/: 90 days default; customer policy "
     "overrides. Generated PDFs: persisted indefinitely as part of the "
     "matter file (customer retention policy applies). Embedding cache: "
     "indefinite — contains no client data, only the public BNS / case-"
     "summary corpus."),

    ("Logging",
     "Who can access logs?",
     "On-prem: customer's IT only (whoever has filesystem access to the "
     "Lex-Indic server). Hosted (v2.0): SRE on-call rotation with break-"
     "glass approval, logged and reviewed within 24 hours."),

    # ─── 6. AI-specific ────────────────────────────────────────────────
    ("AI",
     "Will my data be used to train your models?",
     "No. Lex-Indic does not train or fine-tune any model on customer "
     "client stories. The Groq / Gemini sub-processor contracts require "
     "the same. No training, no fine-tuning, no embedding-publishing "
     "of customer text."),

    ("AI",
     "What hallucination controls do you have?",
     "Two layers. (1) Retrieval-grounded generation: the model is given "
     "8 verified KB entries and instructed to cite ONLY from that set. "
     "(2) Citation provenance UI: every cited BNS section is a clickable "
     "badge linked to the verified KB entry. Sections we did not retrieve "
     "stay plain text — the visual signal of model drift. /chat refuses "
     "out-of-KB queries entirely."),

    ("AI",
     "What is the model and how is it updated?",
     "Groq Llama-3.3-70B (versatile). Temperature 0.2. Updated only when "
     "Groq's pinned model version changes, which is documented in their "
     "release notes and surfaced to customers via the audit log "
     "(`model` field)."),

    # ─── 7. Liability and contracts ────────────────────────────────────
    ("Contractual",
     "Do you carry professional indemnity / cyber-liability insurance?",
     "Pre-revenue: not yet purchased. First-customer requirement: "
     "₹5 crore professional indemnity, ₹2 crore cyber-liability via "
     "Bajaj Allianz / ICICI Lombard."),

    ("Contractual",
     "Are SLAs in the standard MSA?",
     "Standard MSA includes 99.5% uptime SLA for hosted deployments "
     "with 2% credit per hour of downtime; on-prem deployments have a "
     "best-effort support SLA (P1: 4 hours, P2: 1 business day)."),

    ("Contractual",
     "Indemnity for AI-generated output?",
     "Lex-Indic does not indemnify the substantive legal correctness of "
     "AI-generated drafts (every output carries the 'must be reviewed by "
     "a licensed advocate' disclaimer). We do indemnify against IP "
     "infringement of our codebase up to the contract value."),

    ("Contractual",
     "Termination and data return?",
     "On termination: customer's outputs/ folder is exported as a tar.gz "
     "within 7 days and the running instance is decommissioned (hosted) "
     "or remains under customer control (on-prem). Deletion certificate "
     "provided within 14 days."),

    ("Contractual",
     "Jurisdiction and dispute resolution?",
     "Indian Arbitration & Conciliation Act 1996, seat at Mumbai, sole "
     "arbitrator. Governing law: Indian law. Subject to the jurisdiction "
     "of the Bombay High Court."),
]


# ════════════════════════════════════════════════════════════════════════════
# Data-flow narrative — describes every byte's journey in the standard
# deployment.  Renders inline on /trust and is included in the .docx pack.
# ════════════════════════════════════════════════════════════════════════════
DATA_FLOW_STAGES = [
    {
        "stage": "1. Intake",
        "actor": "Empanelled advocate",
        "what": "Types or pastes client story into the Lex-Indic web app "
                "running on the firm's server.",
        "data": "Client story (plaintext) + optional file attachments (PDF/JPG/PNG).",
        "leaves_jurisdiction": False,
    },
    {
        "stage": "2. Embedding (RAG query)",
        "actor": "Google Gemini text-embedding-001 (US)",
        "what": "Client story is sent to Gemini to produce a 768-dim vector "
                "used for similarity search against the BNS knowledge base.",
        "data": "Client story text (round-trip; not retained per Google's policy).",
        "leaves_jurisdiction": True,
    },
    {
        "stage": "3. Vector search",
        "actor": "ChromaDB (in-process, in-memory)",
        "what": "Top 8 most-similar BNS sections / case summaries / circulars "
                "retrieved by cosine distance.",
        "data": "Vector + retrieved document IDs.  No external network call.",
        "leaves_jurisdiction": False,
    },
    {
        "stage": "4. Inference (Groq)",
        "actor": "Groq Llama-3.3-70B (US)",
        "what": "Client story + retrieved BNS context + system prompt sent to "
                "Groq for legal analysis. Response streamed back in ~5 seconds.",
        "data": "Client story + retrieved BNS sections + prompt.",
        "leaves_jurisdiction": True,
    },
    {
        "stage": "5. Response render",
        "actor": "Lex-Indic Flask server (on-prem)",
        "what": "Six legal sections parsed and rendered in browser; 9-page "
                "PDF case brief generated.",
        "data": "Inference output rendered to browser; PDF written to outputs/.",
        "leaves_jurisdiction": False,
    },
    {
        "stage": "6. Audit",
        "actor": "Lex-Indic audit logger (on-prem)",
        "what": "One JSONL record written with hashed story, retrieved IDs, "
                "latency, status.",
        "data": "SHA-256 hash of story (never the raw text), metadata.",
        "leaves_jurisdiction": False,
    },
]


def to_dict() -> dict:
    """Single source of truth for the trust page and the .docx pack."""
    return {
        "posture": {
            "company": POSTURE.company,
            "product": POSTURE.product,
            "contact_dpo": POSTURE.contact_dpo,
            "last_updated": POSTURE.last_updated,
        },
        "questions": [
            {"category": cat, "q": q, "a": a} for cat, q, a in QUESTIONS
        ],
        "data_flow": DATA_FLOW_STAGES,
    }


# ════════════════════════════════════════════════════════════════════════════
# .docx pack generator — used by /trust/pack.docx
# ════════════════════════════════════════════════════════════════════════════
def build_pack_docx() -> bytes:
    """Compile the full compliance pack as a single .docx for the GC."""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # ── Cover ──
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(POSTURE.company)
    run.bold = True; run.font.size = Pt(32); run.font.color.rgb = RGBColor(0xB4, 0x8C, 0x28)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run("DPDP & Information-Security Compliance Pack")
    run.bold = True; run.font.size = Pt(16)

    sub2 = doc.add_paragraph()
    sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub2.add_run(POSTURE.product).italic = True

    doc.add_paragraph()
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        f"Last updated: {POSTURE.last_updated}  ·  "
        f"DPO: {POSTURE.contact_dpo}"
    ).font.size = Pt(9)
    doc.add_page_break()

    # ── Data flow ──
    doc.add_heading("1. Data Flow", level=1)
    doc.add_paragraph(
        "Every byte's journey in the standard on-prem deployment.  Stages "
        "marked 'leaves jurisdiction' are the only points where data crosses "
        "the Indian border; these can be eliminated by switching to the "
        "local-Ollama deployment path described in §6."
    )
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Stage"
    hdr[1].text = "Actor"
    hdr[2].text = "What happens"
    hdr[3].text = "Leaves India?"
    for s in DATA_FLOW_STAGES:
        row = table.add_row().cells
        row[0].text = s["stage"]
        row[1].text = s["actor"]
        row[2].text = s["what"] + "\nData: " + s["data"]
        row[3].text = "Yes" if s["leaves_jurisdiction"] else "No"
    doc.add_page_break()

    # ── Q&A by category ──
    doc.add_heading("2. Procurement Questionnaire", level=1)
    last_cat = None
    for cat, q, a in QUESTIONS:
        if cat != last_cat:
            doc.add_heading(cat, level=2)
            last_cat = cat
        p = doc.add_paragraph()
        run = p.add_run("Q. " + q)
        run.bold = True
        doc.add_paragraph("A. " + a)
        doc.add_paragraph()  # spacer

    # ── Footer ──
    doc.add_page_break()
    doc.add_heading("Notes", level=1)
    doc.add_paragraph(
        "This document is generated programmatically from compliance.py "
        "and reflects the current posture of the running Lex-Indic build. "
        "Customers may request a signed PDF version on letterhead from "
        f"{POSTURE.contact_dpo}."
    )

    import io
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
