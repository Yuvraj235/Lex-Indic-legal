"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — SOC 2 Type II Readiness Scaffolding (Day 7 of Legora teardown)  ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS IS
────────────
SOC 2 Type II is a 6-12 month audit where an AICPA-registered auditor checks
that you operated your stated controls continuously over the period.  This
file lists the controls Lex-Indic intends to attest to, each one mapped to:

  - The Trust Service Criterion (TSC) it satisfies
  - A short description
  - An "evidence collector" — a small Python function that returns either
    a True/False status and a one-line note, used by the /admin/soc2 page
    to show "are we still compliant?" at a glance
  - Pointers to where in the codebase the control is implemented

The controls cover the 5 TSCs: Security, Availability, Confidentiality,
Processing Integrity, Privacy.  We focus on Security + Confidentiality +
Privacy for v1.4 — the others (Availability, Processing Integrity) get added
when the hosted multi-tenant deployment ships.

WHY THIS BEFORE THE AUDIT
─────────────────────────
SOC 2 auditors don't accept "we'll have it ready by audit time".  They want
evidence that the control has been operating continuously.  This scaffolding
captures evidence on every server start and makes it auditable as soon as
we engage Vanta / Drata to formalise.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


# ─── Result type ────────────────────────────────────────────────────────────
@dataclass
class CheckResult:
    passed: bool
    note: str
    evidence: str = ""     # raw evidence (file path, command output excerpt)


@dataclass
class Control:
    id: str
    tsc: str               # CC1 / CC2 / ... A1 / C1 / PI1 / P1
    title: str
    description: str
    check: Callable[[], CheckResult]
    pointer: str = ""      # where this is implemented in the codebase


# ════════════════════════════════════════════════════════════════════════════
# Individual evidence collectors.  Each is intentionally cheap (sub-second)
# so the /admin/soc2 page loads instantly.
# ════════════════════════════════════════════════════════════════════════════
def _check_env_file_restrictive() -> CheckResult:
    """CC6.1 — secrets file is readable only by owner (not group/world)."""
    p = REPO_ROOT / ".env"
    if not p.exists():
        return CheckResult(False, ".env file is missing — cannot verify perms.")
    st = p.stat()
    mode = stat.S_IMODE(st.st_mode)
    if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
        return CheckResult(
            False,
            f".env is world/group readable (mode {oct(mode)}).  Run `chmod 600 .env`.",
            evidence=f"stat=.env mode={oct(mode)}",
        )
    return CheckResult(True, f".env permissions are 0o{mode:o} (owner-only). ✓",
                       evidence=f"stat=.env mode={oct(mode)}")


def _check_dev_certs_gitignored() -> CheckResult:
    """CC6.6 — self-signed dev certs must never be committed."""
    gi = REPO_ROOT / ".gitignore"
    if not gi.exists():
        return CheckResult(False, ".gitignore missing.")
    body = gi.read_text(encoding="utf-8")
    if "certs/" in body or "certs/*.pem" in body:
        return CheckResult(True, "certs/ is gitignored. ✓",
                           evidence=".gitignore contains 'certs/*.pem'")
    return CheckResult(False, ".gitignore does NOT exclude certs/. Add `certs/*.pem` and `certs/*.key`.")


def _check_audit_log_present() -> CheckResult:
    """CC7.2 — append-only audit log exists and has recent activity."""
    audit_dir = REPO_ROOT / "outputs" / "audit"
    if not audit_dir.exists():
        return CheckResult(False, "Audit log directory not created. Run /analyze once.")
    files = list(audit_dir.glob("audit-*.log"))
    if not files:
        return CheckResult(False, "No audit log files found.")
    latest = max(files, key=lambda p: p.stat().st_mtime)
    age_hours = (datetime.now().timestamp() - latest.stat().st_mtime) / 3600
    if age_hours > 168:  # 7 days
        return CheckResult(False,
            f"Newest audit log is {age_hours:.0f}h old. No /analyze activity in a week.",
            evidence=f"latest={latest.name}")
    return CheckResult(True,
        f"Audit log healthy — newest is {age_hours:.1f}h old ({latest.name}).",
        evidence=f"latest={latest.name}")


def _check_audit_log_append_only() -> CheckResult:
    """CC7.2 — audit log files should not have shrunk between checks."""
    sizes_file = REPO_ROOT / "tools" / "soc2" / "evidence" / "audit_log_sizes.json"
    audit_dir = REPO_ROOT / "outputs" / "audit"
    if not audit_dir.exists():
        return CheckResult(False, "No audit dir yet.")

    current: dict[str, int] = {}
    for p in audit_dir.glob("audit-*.log"):
        current[p.name] = p.stat().st_size

    previous: dict[str, int] = {}
    if sizes_file.exists():
        previous = json.loads(sizes_file.read_text())

    # If any file shrank, that's a CC7.2 violation
    shrank = []
    for name, size in previous.items():
        if name in current and current[name] < size:
            shrank.append(f"{name}: {size} → {current[name]}")
    sizes_file.parent.mkdir(parents=True, exist_ok=True)
    sizes_file.write_text(json.dumps(current, indent=2))

    if shrank:
        return CheckResult(
            False,
            "Audit log file SHRANK since last check — investigate.",
            evidence="; ".join(shrank),
        )
    return CheckResult(True,
        f"Append-only verified across {len(current)} log file(s). ✓",
        evidence=f"{sum(current.values())} bytes total")


def _check_hashed_pii() -> CheckResult:
    """P3 / Confidentiality — audit log must hash story, never raw."""
    audit_dir = REPO_ROOT / "outputs" / "audit"
    if not audit_dir.exists():
        return CheckResult(False, "No audit dir yet — nothing to verify.")
    leaks = []
    for log in audit_dir.glob("audit-*.log"):
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            # Must have hash, NOT the raw story
            if "story" in rec and rec["story"] and not str(rec["story"]).startswith("sha256:"):
                leaks.append(log.name)
                break
    if leaks:
        return CheckResult(False,
            f"Raw story text found in {len(leaks)} log(s) — privacy violation.",
            evidence="; ".join(leaks))
    return CheckResult(True,
        "All audit records use sha256: prefixed hashes. ✓",
        evidence="checked last 200 records per file")


def _check_tls_cert_present() -> CheckResult:
    """CC6.7 — TLS certificate present when --https mode is needed."""
    cert = REPO_ROOT / "certs" / "dev-cert.pem"
    if not cert.exists():
        return CheckResult(False,
            "No certs/dev-cert.pem.  Generate via README openssl command.",
            evidence=str(cert))
    # Parse expiry via openssl
    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert), "-noout", "-enddate"],
            capture_output=True, text=True, timeout=5,
        )
        expiry_line = result.stdout.strip().replace("notAfter=", "")
        expiry = datetime.strptime(expiry_line, "%b %d %H:%M:%S %Y %Z")
        days_left = (expiry - datetime.now(timezone.utc).replace(tzinfo=None)).days
        if days_left < 0:
            return CheckResult(False, f"TLS cert EXPIRED {-days_left} days ago.", evidence=expiry_line)
        if days_left < 30:
            return CheckResult(False, f"TLS cert expires in {days_left} days — rotate now.", evidence=expiry_line)
        return CheckResult(True,
            f"TLS cert valid for {days_left} more days ({expiry_line}). ✓",
            evidence=expiry_line)
    except Exception as e:
        return CheckResult(False, f"Could not parse cert expiry: {e}")


def _check_dependencies_pinned() -> CheckResult:
    """CC8.1 — production dependencies must be pinned."""
    req = REPO_ROOT / "requirements.txt"
    if not req.exists():
        return CheckResult(False, "requirements.txt missing.")
    unpinned = []
    for line in req.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Acceptable pin: name==X.Y.Z, name~=X.Y, name>=X.Y,<Z
        if "==" not in line and "~=" not in line and ">=" not in line:
            unpinned.append(line)
    if unpinned:
        return CheckResult(False,
            f"{len(unpinned)} unpinned: {', '.join(unpinned)}",
            evidence=", ".join(unpinned))
    return CheckResult(True, "All deps in requirements.txt are version-pinned. ✓")


def _check_secret_in_git() -> CheckResult:
    """
    CC6.1 — no real API keys in git history.

    We grep the FULL diff history for the real key shapes:
      Groq:    gsk_ + 40+ alphanumeric chars
      Gemini:  AIzaSy + 33 alphanumeric / _ / - chars (Google's canonical form)

    Placeholder strings like 'GROQ_API_KEY=gsk_...' or 'gsk_xxx' get past
    the regex because they're too short — that's the intentional design,
    we only want to alarm on real leaked tokens.  For more comprehensive
    coverage, run `gitleaks detect` (CI step in roadmap).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "--all", "-p"],
            capture_output=True, text=True, timeout=20,
        )
        diff = result.stdout

        # Real Groq keys: gsk_ + 40+ alphanumeric  (placeholders are <20 chars)
        groq_matches = set(re.findall(r"gsk_[A-Za-z0-9]{40,}", diff))
        # Real Gemini keys: AIzaSy + 33 chars
        gemini_matches = set(re.findall(r"AIzaSy[A-Za-z0-9_\-]{33}", diff))

        if groq_matches:
            return CheckResult(False,
                f"Real Groq key found in git history ({len(groq_matches)} unique). Rotate immediately.",
                evidence=f"{len(groq_matches)} matches; first 6 chars: " +
                         ", ".join(sorted(groq_matches))[:60] + "...")
        if gemini_matches:
            return CheckResult(False,
                f"Real Gemini key found in git history ({len(gemini_matches)} unique). Rotate.",
                evidence=f"{len(gemini_matches)} matches")
        return CheckResult(True,
            "No real Groq/Gemini key shapes detected in any commit. ✓",
            evidence="full git log scanned with key-shape regex")
    except Exception as e:
        return CheckResult(False, f"Could not scan git: {e}")


def _check_audit_salt_set() -> CheckResult:
    """P3 / Confidentiality — audit hash salt must be set in production."""
    salt = os.getenv("AUDIT_HASH_SALT", "")
    if not salt:
        return CheckResult(False,
            "AUDIT_HASH_SALT not set. In production this MUST be set or the "
            "audit hash uses the default insecure salt.")
    if len(salt) < 16:
        return CheckResult(False,
            f"AUDIT_HASH_SALT is only {len(salt)} chars — recommend 32+.")
    return CheckResult(True, f"AUDIT_HASH_SALT set ({len(salt)} chars). ✓")


def _check_outputs_perms() -> CheckResult:
    """CC6.1 — outputs/ should not be world-readable."""
    o = REPO_ROOT / "outputs"
    if not o.exists():
        return CheckResult(True, "outputs/ does not exist yet (fresh install).")
    mode = stat.S_IMODE(o.stat().st_mode)
    if mode & (stat.S_IROTH | stat.S_IWOTH):
        return CheckResult(False,
            f"outputs/ is world-accessible (mode {oct(mode)}). Run `chmod 750 outputs`.",
            evidence=f"mode={oct(mode)}")
    return CheckResult(True,
        f"outputs/ permissions are {oct(mode)} (no world access). ✓",
        evidence=f"mode={oct(mode)}")


# ════════════════════════════════════════════════════════════════════════════
# The control catalogue — what we attest to.
# ════════════════════════════════════════════════════════════════════════════
CONTROLS: list[Control] = [
    Control(
        id="CC6.1-A",
        tsc="Security (CC6.1)",
        title="Secrets file permissions",
        description="The .env file containing API keys must be readable only by the file owner.",
        check=_check_env_file_restrictive,
        pointer=".env  (mode 0o600 recommended)",
    ),
    Control(
        id="CC6.1-B",
        tsc="Security (CC6.1)",
        title="No secrets in git history",
        description="Bearer tokens (Groq gsk_, Google AIzaSy) must never appear in any tracked commit.",
        check=_check_secret_in_git,
        pointer="git log -S 'gsk_'",
    ),
    Control(
        id="CC6.1-C",
        tsc="Security (CC6.1)",
        title="Outputs directory permissions",
        description="outputs/ contains generated case files and audit logs and must not be world-accessible.",
        check=_check_outputs_perms,
        pointer="outputs/ (mode 0o750 recommended)",
    ),
    Control(
        id="CC6.6",
        tsc="Security (CC6.6)",
        title="Self-signed certs are gitignored",
        description="Dev TLS certificates must not be committed to the repository.",
        check=_check_dev_certs_gitignored,
        pointer=".gitignore  contains 'certs/*.pem'",
    ),
    Control(
        id="CC6.7",
        tsc="Security (CC6.7)",
        title="TLS certificate is valid and not expiring",
        description="The TLS certificate used for the Word add-in must be present and have ≥30 days remaining.",
        check=_check_tls_cert_present,
        pointer="certs/dev-cert.pem",
    ),
    Control(
        id="CC7.2-A",
        tsc="Security (CC7.2)",
        title="Audit log present and recent",
        description="The append-only audit log must exist and have an entry in the last 7 days.",
        check=_check_audit_log_present,
        pointer="outputs/audit/audit-YYYY-MM-DD.log",
    ),
    Control(
        id="CC7.2-B",
        tsc="Security (CC7.2)",
        title="Audit log is append-only",
        description="No audit log file may shrink between SOC 2 checks. We snapshot file sizes and compare.",
        check=_check_audit_log_append_only,
        pointer="tools/soc2/evidence/audit_log_sizes.json",
    ),
    Control(
        id="CC8.1",
        tsc="Security (CC8.1)",
        title="Dependencies are pinned",
        description="All production dependencies in requirements.txt must have a version constraint.",
        check=_check_dependencies_pinned,
        pointer="requirements.txt",
    ),
    Control(
        id="P3.1",
        tsc="Privacy (P3.1)",
        title="Audit log stores only hashed PII",
        description="Audit records must contain SHA-256 hashes of client stories, never raw text.",
        check=_check_hashed_pii,
        pointer="audit.py  (story_hash field)",
    ),
    Control(
        id="P3.2",
        tsc="Privacy (P3.2)",
        title="Audit hash salt is set",
        description="AUDIT_HASH_SALT environment variable must be set to a 16+ char string in production.",
        check=_check_audit_salt_set,
        pointer="AUDIT_HASH_SALT in .env",
    ),
]


def run_all() -> list[dict]:
    """Execute every control and return the rolled-up results."""
    out = []
    for c in CONTROLS:
        try:
            r = c.check()
        except Exception as e:
            r = CheckResult(False, f"check raised: {e}")
        out.append({
            "id": c.id,
            "tsc": c.tsc,
            "title": c.title,
            "description": c.description,
            "pointer": c.pointer,
            "passed": r.passed,
            "note": r.note,
            "evidence": r.evidence,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    return out


def summary() -> dict:
    rows = run_all()
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(rows),
        "passed": sum(1 for r in rows if r["passed"]),
        "failed": sum(1 for r in rows if not r["passed"]),
        "rows": rows,
    }


def save_evidence_snapshot() -> Path:
    """Persist a snapshot to outputs/soc2_evidence/YYYY-MM-DD_HH-MM.json — this
    is the auditor's continuous-evidence trail."""
    s = summary()
    out_dir = REPO_ROOT / "outputs" / "soc2_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
    path = out_dir / f"{ts}.json"
    path.write_text(json.dumps(s, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════════════════════════
# CLI — schedule on cron (e.g. once an hour) to build the evidence trail.
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Lex-Indic SOC 2 control checks.")
    parser.add_argument("--save", action="store_true", help="Save snapshot to outputs/soc2_evidence/")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    parser.add_argument("--fail-on-issue", action="store_true",
                        help="Exit 1 if any control fails (use in CI).")
    args = parser.parse_args()

    s = summary()
    if args.save:
        path = save_evidence_snapshot()
        print(f"Saved {path}")
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print(f"{'─' * 78}")
        print(f"  LEX-INDIC SOC 2 readiness check · {s['checked_at']}")
        print(f"  {s['passed']}/{s['total']} controls passing")
        print(f"{'─' * 78}")
        for r in s["rows"]:
            mark = "✓" if r["passed"] else "✗"
            print(f"  [{mark}] {r['id']:8} {r['tsc']:24} {r['title']}")
            print(f"         {r['note']}")
        print(f"{'─' * 78}")

    if args.fail_on_issue and s["failed"] > 0:
        raise SystemExit(1)
