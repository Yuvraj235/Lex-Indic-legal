"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Statute migration auditor                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Scan a folder of legal documents (templates, drafts, precedents) and report
every outdated IPC / CrPC / Evidence-Act reference with its BNS / BNSS / BSA
equivalent — so a firm can see, in one report, exactly what needs updating.

Reuses the statute-aware matcher in ipc_bns_converter.convert_text_multi.  Anything
we don't have a verified mapping for is reported as "unmapped" — never guessed.

  core (pure, testable):  audit_text(name, text) -> DocAudit
                          aggregate(docs)        -> AuditReport
  I/O (CLI / route):      extract_text(path), audit_paths(paths)
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import ipc_bns_converter as conv

SUPPORTED_SUFFIXES = {".txt", ".docx", ".pdf"}


# ──────────────────────────────────────────────────────────────────────────────
# Pure core
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class DocAudit:
    name: str
    refs_found: int = 0
    mapped: int = 0
    unmapped: int = 0
    by_statute: dict = field(default_factory=dict)     # statute -> count
    matches: list = field(default_factory=list)        # {statute, old, target, title}

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditReport:
    docs: list = field(default_factory=list)            # list[DocAudit]
    totals: dict = field(default_factory=dict)
    top_unmapped: list = field(default_factory=list)    # [(ref, count)]

    def to_dict(self) -> dict:
        return {
            "docs": [d.to_dict() for d in self.docs],
            "totals": self.totals,
            "top_unmapped": self.top_unmapped,
        }


def audit_text(name: str, text: str) -> DocAudit:
    """Audit one document's text. Pure — no file I/O, no network."""
    _, matches = conv.convert_text_multi(text or "")
    d = DocAudit(name=name)
    by = Counter()
    for m in matches:
        d.refs_found += 1
        by[m.statute] += 1
        if m.target:
            d.mapped += 1
        else:
            d.unmapped += 1
        d.matches.append({
            "statute": m.statute, "old": f"{m.statute} {m.old_num}",
            "target": m.target, "title": m.title,
        })
    d.by_statute = dict(by)
    return d


def aggregate(docs: list) -> AuditReport:
    """Roll per-document audits into a firm-level report."""
    totals = Counter()
    by_statute = Counter()
    unmapped_refs = Counter()
    for d in docs:
        totals["documents"] += 1
        totals["refs_found"] += d.refs_found
        totals["mapped"] += d.mapped
        totals["unmapped"] += d.unmapped
        if d.refs_found:
            totals["documents_with_refs"] += 1
        for st, n in d.by_statute.items():
            by_statute[st] += n
        for m in d.matches:
            if not m["target"]:
                unmapped_refs[m["old"]] += 1
    report = AuditReport(docs=docs)
    report.totals = {**dict(totals), "by_statute": dict(by_statute)}
    report.top_unmapped = unmapped_refs.most_common(20)
    return report


def render_markdown(report: AuditReport) -> str:
    t = report.totals
    lines = [
        "# Statute Migration Audit",
        "",
        f"- Documents scanned: **{t.get('documents', 0)}** "
        f"({t.get('documents_with_refs', 0)} contain old references)",
        f"- Outdated references found: **{t.get('refs_found', 0)}** "
        f"— {t.get('mapped', 0)} mapped, {t.get('unmapped', 0)} unmapped",
        f"- By statute: {t.get('by_statute', {})}",
        "",
        "| Document | Found | Mapped | Unmapped |",
        "|----------|------:|-------:|---------:|",
    ]
    for d in report.docs:
        lines.append(f"| `{d.name}` | {d.refs_found} | {d.mapped} | {d.unmapped} |")
    if report.top_unmapped:
        lines += ["", "## References with no verified mapping yet",
                  "_(reported honestly — extend the mapping files to cover these)_", ""]
        for ref, n in report.top_unmapped:
            lines.append(f"- `{ref}` × {n}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────────────────────────────────────
def extract_text(path: Path) -> str:
    """Best-effort text extraction for .txt / .docx / .pdf."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        from docx import Document
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.extend(c.text for c in row.cells)
        return "\n".join(parts)
    if suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    return ""


def audit_paths(paths: list) -> AuditReport:
    """Walk files/folders, audit every supported document, aggregate."""
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(f for f in sorted(p.rglob("*"))
                         if f.suffix.lower() in SUPPORTED_SUFFIXES)
        elif p.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(p)
    docs = []
    for f in files:
        try:
            text = extract_text(f)
        except Exception as e:  # noqa: BLE001 — one bad file shouldn't void the run
            print(f"  ! skipped {f}: {e}")
            continue
        docs.append(audit_text(str(f), text))
    return aggregate(docs)
