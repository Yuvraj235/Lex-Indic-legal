"""
Deployment mode + secret handling, shared by every module that signs or hashes.

LEX_ENV
    development | dev | local | test  → developer conveniences are allowed
                                         (login code echoed in the response,
                                         admin pages open when ADMIN_TOKEN is
                                         unset, http:// webhook targets).
    anything else, or unset           → production behaviour.  Unset means
                                         production on purpose: forgetting the
                                         flag must never open the app up.

SECRET_KEY
    Signs session cookies, download links, firm invites and API-key hashes.
    Falls back to AUDIT_HASH_SALT so existing deployments keep their sessions.
    Set it separately so that rotating AUDIT_HASH_SALT (DPDP erasure) doesn't
    log every user out or invalidate API keys.

In production a missing or short secret raises instead of falling back to a
built-in constant — a constant that ships in the source is public.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

_DEV_VALUES = {"development", "dev", "local", "test"}
_MIN_SECRET_LEN = 16
_DEV_KEY_PATH = Path("outputs") / ".dev_secret_key"


class ConfigError(RuntimeError):
    """Raised when a production deployment is missing a required secret."""


def is_dev() -> bool:
    return os.getenv("LEX_ENV", "").strip().lower() in _DEV_VALUES


def _dev_key() -> str:
    """Random per-checkout key for local development, persisted under outputs/
    (gitignored) so dev sessions survive a restart."""
    try:
        if _DEV_KEY_PATH.exists():
            key = _DEV_KEY_PATH.read_text(encoding="utf-8").strip()
            if len(key) >= _MIN_SECRET_LEN:
                return key
        _DEV_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_hex(32)
        _DEV_KEY_PATH.write_text(key, encoding="utf-8")
        return key
    except OSError:
        return secrets.token_hex(32)   # read-only FS: per-process key


def _require(name: str, value: str) -> str:
    if len(value) >= _MIN_SECRET_LEN:
        return value
    if is_dev():
        return _dev_key()
    raise ConfigError(
        f"{name} must be set to a random value of at least {_MIN_SECRET_LEN} "
        "characters in production (python3 -c 'import secrets; "
        "print(secrets.token_hex(32))'). For local development set "
        "LEX_ENV=development."
    )


def secret_key() -> str:
    """Base secret for signing. SECRET_KEY, else AUDIT_HASH_SALT."""
    value = os.getenv("SECRET_KEY") or os.getenv("AUDIT_HASH_SALT") or ""
    return _require("SECRET_KEY", value)


def audit_salt() -> str:
    """Salt for hashing personal data in the audit log."""
    return _require("AUDIT_HASH_SALT", os.getenv("AUDIT_HASH_SALT") or "")


def check_production_config() -> None:
    """Call once at boot: fail fast instead of on the first login."""
    secret_key()
    audit_salt()
