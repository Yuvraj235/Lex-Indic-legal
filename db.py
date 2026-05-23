"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — SQLAlchemy ORM + Postgres support (Day 20)                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: A single-file SQLAlchemy 2.0 ORM defining the 6 tables that the
JSON-file modules already use (firms, lawyers, matters, monitor_matters,
nalsa_registrations, leads, webhook_subs).  Plus the connection bootstrap
and a `create_all()` for fresh deployments.

WHY: Past 50–100 users, the JSON-file approach hits real limits — no
proper indexing, no concurrent-write safety, no transactions across
related rows.  This module is the migration target.

Status: ORM defined, schema creates cleanly on Postgres (and SQLite if
DATABASE_URL=sqlite:///outputs/lex.db).  The JSON-file modules
(matters.py, monitors.py, nalsa.py, leads.py, webhooks.py) are NOT yet
ported — tools/migrate_to_postgres.py copies their data into these
tables, and the existing modules can be switched module-by-module by
checking `db.is_enabled()`.

DESIGN PRINCIPLE: zero-touch when DATABASE_URL is unset.  All JSON-file
code paths stay exactly as they were.  Operators opt in by setting
DATABASE_URL — nothing forces them to migrate.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

try:
    from sqlalchemy import (
        Column, String, Integer, Boolean, DateTime, Text, JSON,
        create_engine, ForeignKey,
    )
    from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
    from sqlalchemy.exc import SQLAlchemyError
    _SA_AVAILABLE = True
except ImportError:
    _SA_AVAILABLE = False


def is_enabled() -> bool:
    """True iff DATABASE_URL is set AND sqlalchemy is importable."""
    return _SA_AVAILABLE and bool(os.getenv("DATABASE_URL"))


def database_url() -> str:
    return os.getenv("DATABASE_URL", "")


# ─── Engine + Session factory (lazy) ────────────────────────────────────────
_engine = None
_SessionLocal = None


def _init_engine():
    global _engine, _SessionLocal
    if not is_enabled():
        return
    if _engine is not None:
        return
    _engine = create_engine(
        database_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False,
                                  future=True)


@contextmanager
def session():
    """Yields a SQLAlchemy session. Commits on success, rolls back on error."""
    if not is_enabled():
        raise RuntimeError("db.session() called but DATABASE_URL is unset.")
    _init_engine()
    s: Session = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ─── ORM models (only defined if sqlalchemy is available) ───────────────────
if _SA_AVAILABLE:
    Base = declarative_base()

    def _now():
        return datetime.now(timezone.utc)

    class Firm(Base):
        __tablename__ = "firms"
        id          = Column(String(40), primary_key=True)        # firm_<hex>
        name        = Column(String(160), unique=True, nullable=False)
        address     = Column(String(400), default="")
        created_at  = Column(DateTime(timezone=True), default=_now, nullable=False)

    class Lawyer(Base):
        __tablename__ = "lawyers"
        id              = Column(String(40), primary_key=True)
        firm_id         = Column(String(40), ForeignKey("firms.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
        full_name       = Column(String(160), nullable=False)
        bar_council_no  = Column(String(40), default="")
        email           = Column(String(160), default="", index=True)
        role            = Column(String(40), default="associate")
        created_at      = Column(DateTime(timezone=True), default=_now, nullable=False)

    class Matter(Base):
        __tablename__ = "matters"
        id              = Column(String(40), primary_key=True)    # FIRM/YYYY/SEQ
        firm_id         = Column(String(40), ForeignKey("firms.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
        lawyer_id       = Column(String(40), ForeignKey("lawyers.id", ondelete="SET NULL"),
                                 nullable=True, index=True)
        client_name     = Column(String(200), nullable=False, index=True)
        opposing_party  = Column(String(200), default="", index=True)
        matter_type     = Column(String(60), default="")
        description     = Column(Text, default="")
        status          = Column(String(20), default="open", index=True)
        created_at      = Column(DateTime(timezone=True), default=_now, nullable=False)
        updated_at      = Column(DateTime(timezone=True), default=_now, nullable=False)

    class MonitorMatter(Base):
        __tablename__ = "monitor_matters"
        id          = Column(String(40), primary_key=True)        # m_<ts>
        label       = Column(String(160), nullable=False)
        keywords    = Column(JSON, default=list)
        sections    = Column(JSON, default=list)
        created_at  = Column(DateTime(timezone=True), default=_now, nullable=False)

    class NalsaRegistration(Base):
        __tablename__ = "nalsa_registrations"
        id                  = Column(String(40), primary_key=True)
        full_name           = Column(String(160), nullable=False)
        panel_id            = Column(String(60), index=True)
        slsa                = Column(String(80), nullable=False, index=True)
        bar_council_no      = Column(String(40))
        email               = Column(String(160), unique=True, nullable=False)
        phone               = Column(String(30))
        practice_areas      = Column(JSON, default=list)
        case_volume_monthly = Column(Integer, default=0)
        consent_to_contact  = Column(Boolean, default=False)
        registered_at       = Column(DateTime(timezone=True), default=_now, nullable=False)
        status              = Column(String(20), default="self_claimed", index=True)

    class Lead(Base):
        __tablename__ = "leads"
        id              = Column(String(40), primary_key=True)
        full_name       = Column(String(160), nullable=False)
        email           = Column(String(160), nullable=False, index=True)
        firm_or_org     = Column(String(160), default="")
        role            = Column(String(60), default="")
        practice_areas  = Column(JSON, default=list)
        how_heard       = Column(Text, default="")
        interests       = Column(JSON, default=list)
        referrer        = Column(String(400), default="")
        user_agent      = Column(String(300), default="")
        captured_at     = Column(DateTime(timezone=True), default=_now, nullable=False)

    class WebhookSub(Base):
        __tablename__ = "webhook_subs"
        id          = Column(String(40), primary_key=True)
        url         = Column(String(600), nullable=False)
        events      = Column(JSON, nullable=False)
        description = Column(String(300), default="")
        active      = Column(Boolean, default=True, index=True)
        created_at  = Column(DateTime(timezone=True), default=_now, nullable=False)


def create_all():
    """Create every table.  Safe to call repeatedly — no-ops on existing tables."""
    if not is_enabled():
        raise RuntimeError("db.create_all() called but DATABASE_URL is unset.")
    _init_engine()
    Base.metadata.create_all(bind=_engine)


def drop_all():
    """Dangerous — only used in tests + the migration tool's --reset flag."""
    if not is_enabled():
        raise RuntimeError("db.drop_all() called but DATABASE_URL is unset.")
    _init_engine()
    Base.metadata.drop_all(bind=_engine)


def health_check() -> dict:
    """Returns {ok, latency_ms, tables, version} or {ok: False, error}."""
    import time
    if not _SA_AVAILABLE:
        return {"ok": False, "error": "sqlalchemy not installed"}
    if not is_enabled():
        return {"ok": False, "error": "DATABASE_URL not set"}
    try:
        _init_engine()
        t0 = time.monotonic()
        with _engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        latency_ms = int((time.monotonic() - t0) * 1000)
        # Count tables we know about
        with session() as s:
            tables = {}
            for cls in (Firm, Lawyer, Matter, MonitorMatter, NalsaRegistration, Lead, WebhookSub):
                try:
                    tables[cls.__tablename__] = s.query(cls).count()
                except Exception as e:
                    tables[cls.__tablename__] = f"error: {str(e)[:60]}"
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "url_scheme": database_url().split(":")[0],
            "tables": tables,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
