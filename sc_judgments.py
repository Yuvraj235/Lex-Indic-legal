"""
Supreme Court criminal judgments as retrieval documents ("similar real cases").

Reads data/judgments/judgments.db, built by tools/ingest_judgments.py from the
Indian Supreme Court Judgments open dataset (CC-BY-4.0). Each document carries
the official neutral citation and S.C.R. report, the provisions the judgment
cites, and the opening of the official report (issue for consideration /
headnote), so the model can point to a real case and the verifier can confirm
the citation against the official record.

Absent database → no documents (the app works without it).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "data" / "judgments" / "judgments.db"
MAX_EXCERPT = 900


def documents(db: Path = DB) -> tuple[list[str], list[dict], list[str]]:
    if not db.exists():
        return [], [], []
    con = sqlite3.connect(db)
    docs, metas, ids = [], [], []
    for insc, title, decided, scr, sections, ex in con.execute(
            "SELECT insc, title, decided, scr, sections, excerpt FROM judgments ORDER BY insc"):
        name = re.sub(r"\s+versus\s+", " v. ", title or "", flags=re.I).title().replace(" V. ", " v. ")
        ex = (ex or "")[:MAX_EXCERPT].rsplit(" ", 1)[0]
        docs.append(f"SUPREME COURT JUDGMENT (official record): {name} — {insc}, {scr}, decided {decided}\n"
                    f"PROVISIONS CITED: {sections}\n"
                    f"OFFICIAL REPORT EXTRACT: {ex}")
        metas.append({"type": "sc_judgment", "case_name": name, "insc": insc, "year": (insc or "")[:4],
                      "search_key": f"{name}. {sections}. {ex[:600]}"})
        ids.append("scj_" + re.sub(r"\W+", "_", insc))
    con.close()
    return docs, metas, ids
