#!/usr/bin/env python3
"""
One-shot JSON-files → Postgres migration tool.

Reads the existing JSON-backed registries from outputs/ and inserts them
into the configured DATABASE_URL.  Idempotent — running twice does not
duplicate rows (uses INSERT … ON CONFLICT DO NOTHING by PK).

Usage:
  export DATABASE_URL=postgresql+psycopg://lexindic:pwd@localhost:5432/lexindic
  python3 tools/migrate_to_postgres.py            # dry-run + counts
  python3 tools/migrate_to_postgres.py --apply    # actually write
  python3 tools/migrate_to_postgres.py --reset    # drop_all + create_all + reapply

Recovery: keep the outputs/ folder.  The JSON files remain canonical
until the operator chooses to switch each module's read path to the DB.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import db


def _iso(s):
    """Coerce a string timestamp to a datetime, else None."""
    if not s: return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _load(path: Path) -> list:
    if not path.exists(): return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def migrate(apply: bool):
    if not db.is_enabled():
        print("ERROR: DATABASE_URL not set.  Set it then re-run."); sys.exit(2)

    db.create_all()
    print("Schema ready.")

    sources = {
        "firms":      (_load(Path("outputs/matters/firms.json")),     db.Firm),
        "lawyers":    (_load(Path("outputs/matters/lawyers.json")),   db.Lawyer),
        "matters":    (_load(Path("outputs/matters/matters.json")),   db.Matter),
        "monitor":    (_load(Path("outputs/monitors/matters.json")),  db.MonitorMatter),
        "nalsa":      (_load(Path("outputs/nalsa/registry.json")),    db.NalsaRegistration),
        "leads":      (_load(Path("outputs/leads/leads.json")),       db.Lead),
        "webhooks":   (_load(Path("outputs/webhooks/subscriptions.json")), db.WebhookSub),
    }

    # Field coercions per table — JSON file shape → ORM shape
    coercions = {
        "firms":     lambda r: dict(id=r["id"], name=r["name"],
                                    address=r.get("address",""),
                                    created_at=_iso(r.get("created_at"))),
        "lawyers":   lambda r: dict(id=r["id"], firm_id=r["firm_id"],
                                    full_name=r["full_name"],
                                    bar_council_no=r.get("bar_council_no",""),
                                    email=r.get("email",""),
                                    role=r.get("role","associate"),
                                    created_at=_iso(r.get("created_at"))),
        "matters":   lambda r: dict(id=r["id"], firm_id=r["firm_id"],
                                    lawyer_id=r["lawyer_id"],
                                    client_name=r["client_name"],
                                    opposing_party=r.get("opposing_party",""),
                                    matter_type=r.get("matter_type",""),
                                    description=r.get("description",""),
                                    status=r.get("status","open"),
                                    created_at=_iso(r.get("created_at")),
                                    updated_at=_iso(r.get("updated_at"))),
        "monitor":   lambda r: dict(id=r["id"], label=r["label"],
                                    keywords=r.get("keywords",[]),
                                    sections=r.get("sections",[]),
                                    created_at=_iso(r.get("created_at"))),
        "nalsa":     lambda r: dict(id=r["id"], full_name=r["full_name"],
                                    panel_id=r["panel_id"], slsa=r["slsa"],
                                    bar_council_no=r.get("bar_council_no",""),
                                    email=r["email"], phone=r.get("phone",""),
                                    practice_areas=r.get("practice_areas",[]),
                                    case_volume_monthly=r.get("case_volume_monthly",0),
                                    consent_to_contact=r.get("consent_to_contact",False),
                                    registered_at=_iso(r.get("registered_at")),
                                    status=r.get("status","self_claimed")),
        "leads":     lambda r: dict(id=r["id"], full_name=r["full_name"],
                                    email=r["email"],
                                    firm_or_org=r.get("firm_or_org",""),
                                    role=r.get("role",""),
                                    practice_areas=r.get("practice_areas",[]),
                                    how_heard=r.get("how_heard",""),
                                    interests=r.get("interests",[]),
                                    referrer=r.get("referrer",""),
                                    user_agent=r.get("user_agent",""),
                                    captured_at=_iso(r.get("captured_at"))),
        "webhooks":  lambda r: dict(id=r["id"], url=r["url"],
                                    events=r.get("events",[]),
                                    description=r.get("description",""),
                                    active=r.get("active",True),
                                    created_at=_iso(r.get("created_at"))),
    }

    total = 0
    if not apply:
        for name, (rows, _) in sources.items():
            print(f"  {name:10}  {len(rows):>4} row(s) ready to insert")
            total += len(rows)
        print(f"\nDry-run.  {total} rows would be inserted.  Re-run with --apply.")
        return

    with db.session() as s:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy import insert as default_insert

        is_pg = db.database_url().startswith(("postgresql", "postgres"))
        for name, (rows, Model) in sources.items():
            if not rows:
                print(f"  {name:10}  (empty, skipped)")
                continue
            payload = []
            for r in rows:
                try:
                    payload.append(coercions[name](r))
                except KeyError as e:
                    print(f"    skipping {name} row missing key {e}: {str(r)[:80]}")
            if not payload:
                continue
            if is_pg:
                stmt = pg_insert(Model.__table__).values(payload).on_conflict_do_nothing()
            else:
                # SQLite: use INSERT OR IGNORE
                stmt = default_insert(Model.__table__).prefix_with("OR IGNORE").values(payload)
            result = s.execute(stmt)
            inserted = result.rowcount if result.rowcount and result.rowcount > 0 else len(payload)
            total += inserted
            print(f"  {name:10}  {inserted:>4} row(s) upserted")
    print(f"\nApplied. Approx {total} rows total.")


def main():
    p = argparse.ArgumentParser(description="Migrate JSON-backed registries to the configured DB.")
    p.add_argument("--apply", action="store_true", help="Actually write (default: dry-run).")
    p.add_argument("--reset", action="store_true", help="DROP all tables first.  Destructive.")
    args = p.parse_args()

    if args.reset:
        if not db.is_enabled():
            print("ERROR: DATABASE_URL not set."); sys.exit(2)
        print("Dropping all tables…")
        db.drop_all()
        db.create_all()
        print("Reset complete.  Reapplying:")
        args.apply = True

    migrate(apply=args.apply)


if __name__ == "__main__":
    main()
