"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — Per-matter document storage (Day 35)                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: Lawyers attach FIR copies, medical reports, photos, complaint forms,
to a specific matter. This module is the storage layer.

WHY: A matter without supporting documents is useless. Right now the
/analyze flow accepts attachments but doesn't persist them under the
matter. This adds proper per-matter file management.

LAYOUT:
  outputs/matters/<matter_id_safe>/files/<file_id>__<original_name>
  outputs/matters/<matter_id_safe>/files/_manifest.json   ← metadata

WHY <matter_id_safe>: matter IDs have slashes ("FIRM/2026/0042"), which
mess up filesystem paths. We replace / with __ for the directory name
but keep the original ID in the manifest.

SECURITY:
- Filename is sanitized (no path traversal)
- Size limited (default 10 MB, set MAX_UPLOAD_MB env)
- Extension whitelist (pdf/docx/jpg/png/txt)
- Files served via Flask send_from_directory — no direct path exposure
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

_MATTERS_DIR = Path("outputs") / "matters"

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
ALLOWED_EXT = {".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class FileMeta:
    id: str                    # file_<hex>
    matter_id: str
    original_name: str
    safe_name: str             # what's actually on disk
    size_bytes: int
    content_type: str
    uploaded_by: str = ""      # user email
    uploaded_at: str = ""
    description: str = ""


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _matter_dir(matter_id: str) -> Path:
    safe = matter_id.replace("/", "__")
    return _MATTERS_DIR / safe / "files"


def _manifest_path(matter_id: str) -> Path:
    return _matter_dir(matter_id) / "_manifest.json"


def _load_manifest(matter_id: str) -> list[FileMeta]:
    m = _manifest_path(matter_id)
    if not m.exists():
        return []
    return [FileMeta(**r) for r in json.loads(m.read_text(encoding="utf-8"))]


def _save_manifest(matter_id: str, files: list[FileMeta]):
    m = _manifest_path(matter_id)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(
        json.dumps([asdict(f) for f in files], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _safe_filename(name: str) -> str:
    """Strip path components + scary chars. Preserve extension."""
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9._\-]", "_", name)
    return name[:120]


# ─── Public API ───────────────────────────────────────────────────────────────
def add_file(*, matter_id: str, original_name: str, file_bytes: bytes,
             content_type: str = "application/octet-stream",
             uploaded_by: str = "", description: str = "") -> dict:
    """Add a file to a matter. Returns the saved metadata."""
    if not matter_id or "/" not in matter_id:
        raise ValueError("matter_id must look like FIRM/YYYY/SEQ")

    name = _safe_filename(original_name or "untitled")
    ext = Path(name).suffix.lower()
    if ext and ext not in ALLOWED_EXT:
        raise ValueError(f"File type '{ext}' not allowed. Allowed: {sorted(ALLOWED_EXT)}")

    size = len(file_bytes)
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"File too large ({size//1024//1024} MB). Max {MAX_UPLOAD_MB} MB.")

    file_id = f"file_{uuid.uuid4().hex[:10]}"
    safe_name = f"{file_id}__{name}"
    full_path = _matter_dir(matter_id) / safe_name
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(file_bytes)

    meta = FileMeta(
        id=file_id, matter_id=matter_id,
        original_name=name,
        safe_name=safe_name,
        size_bytes=size,
        content_type=content_type[:120],
        uploaded_by=uploaded_by.lower().strip()[:120],
        uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        description=description[:300],
    )
    files = _load_manifest(matter_id)
    files.append(meta)
    _save_manifest(matter_id, files)
    return asdict(meta)


def list_files(matter_id: str) -> list[dict]:
    return [asdict(f) for f in _load_manifest(matter_id)]


def get_file_path(matter_id: str, file_id: str) -> Path | None:
    """Return absolute path for a file, or None if not found."""
    for f in _load_manifest(matter_id):
        if f.id == file_id:
            return _matter_dir(matter_id) / f.safe_name
    return None


def get_file_meta(matter_id: str, file_id: str) -> dict | None:
    for f in _load_manifest(matter_id):
        if f.id == file_id:
            return asdict(f)
    return None


def delete_file(matter_id: str, file_id: str) -> bool:
    """Hard-delete a file (admin only — there's no soft-delete here)."""
    files = _load_manifest(matter_id)
    target = next((f for f in files if f.id == file_id), None)
    if not target:
        return False
    path = _matter_dir(matter_id) / target.safe_name
    if path.exists():
        path.unlink()
    files = [f for f in files if f.id != file_id]
    _save_manifest(matter_id, files)
    return True


def total_storage_used() -> dict:
    """Operator-view aggregate: how much space is being used across all matters."""
    total_bytes = 0
    total_files = 0
    matters_with_files = 0
    if not _MATTERS_DIR.exists():
        return {"total_bytes": 0, "total_files": 0, "matters_with_files": 0}
    for matter_dir in _MATTERS_DIR.iterdir():
        files_dir = matter_dir / "files"
        manifest = files_dir / "_manifest.json"
        if not manifest.exists():
            continue
        try:
            files = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        if files:
            matters_with_files += 1
            total_files += len(files)
            total_bytes += sum(f.get("size_bytes", 0) for f in files)
    return {
        "total_bytes":         total_bytes,
        "total_mb":            round(total_bytes / 1024 / 1024, 2),
        "total_files":         total_files,
        "matters_with_files":  matters_with_files,
    }
