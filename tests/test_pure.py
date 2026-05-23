"""
Pure-function tests — no Flask, no mocks, no network.

Covers the deterministic core: regex engines, scoring functions, schema
validation, and i18n table.  These are the units that are easy to break
during refactor and easiest to catch with cheap tests.
"""

from __future__ import annotations
import json
import pytest


# ────────────────────────────── ipc_bns_converter ──────────────────────────
class TestIpcBnsConverter:
    def test_simple_uss_match(self):
        from ipc_bns_converter import convert_text
        annotated, summary = convert_text("Accused charged u/s 302 IPC.")
        assert "BNS 103" in annotated
        assert "Murder" in annotated
        assert summary.total_matches == 1
        assert summary.mapped[0].section_numbers == ["302"]

    def test_grouped_sections_with_and(self):
        from ipc_bns_converter import convert_text
        text = "Section 498A and 304B of the Indian Penal Code"
        annotated, summary = convert_text(text)
        # Both sections should be picked up by the SECTION_GROUP regex
        nums = sum(([n for n in m.section_numbers] for m in summary.mapped), [])
        assert "498A" in nums
        assert "304B" in nums

    def test_plain_section_without_ipc_context_is_skipped(self):
        """'Section 379 (theft)' alone should NOT match — could be CPC, CrPC, etc."""
        from ipc_bns_converter import convert_text
        annotated, summary = convert_text("Note: Section 379 (theft) was filed.")
        assert summary.total_matches == 0
        # Output text must be unchanged
        assert annotated == "Note: Section 379 (theft) was filed."

    def test_unknown_section_flagged_not_invented(self):
        from ipc_bns_converter import convert_text
        annotated, summary = convert_text("Charged u/s 999 IPC")
        assert "no BNS mapping" in annotated
        assert "999" in summary.unmapped_section_numbers

    def test_multiple_separator_variants(self):
        from ipc_bns_converter import _split_section_numbers
        assert _split_section_numbers("302, 304/307 & 498A and 34 r/w 120B") == \
            ["302", "304", "307", "498A", "34", "120B"]


# ────────────────────────────── audit ──────────────────────────────────────
class TestAudit:
    def test_hash_story_is_deterministic_and_salted(self):
        from audit import hash_story
        a = hash_story("hello world")
        b = hash_story("hello world")
        c = hash_story("hello world!")
        assert a == b              # deterministic
        assert a != c              # input change → output change
        assert a.startswith("sha256:")
        assert len(a) > len("sha256:")

    def test_hash_story_format(self):
        from audit import hash_story
        # Even empty input gets a deterministic hash — the audit log uses
        # the hash as a join key, so we always want a value.
        out = hash_story("")
        assert out.startswith("sha256:")
        assert len(out) > len("sha256:")


# ────────────────────────────── monitors ───────────────────────────────────
class TestMonitors:
    def test_section_normalization(self):
        from monitors import _normalize_section
        assert _normalize_section("BNS 304") == "304"
        assert _normalize_section("Section 304") == "304"
        assert _normalize_section("S. 304") == "304"
        assert _normalize_section("bns 304") == "304"

    def test_score_ruling_section_match(self):
        from monitors import _score_ruling, Matter, SEED_RULINGS
        snatching = next(r for r in SEED_RULINGS if "Vijay Kumar" in r["title"])
        m = Matter(id="m_test", label="snatching", keywords=[],
                   sections=["BNS 304"], created_at="")
        score, reasons = _score_ruling(snatching, m)
        assert score >= 0.4
        assert any("BNS 304" in r for r in reasons)

    def test_score_ruling_keyword_match(self):
        from monitors import _score_ruling, Matter, SEED_RULINGS
        snatching = next(r for r in SEED_RULINGS if "Vijay Kumar" in r["title"])
        m = Matter(id="m_test", label="bail",
                   keywords=["chain snatching"], sections=[], created_at="")
        score, reasons = _score_ruling(snatching, m)
        assert score >= 0.1
        assert any("chain snatching" in r for r in reasons)

    def test_run_digest_with_no_matters(self):
        """Empty matters list → empty digest, no crash."""
        from monitors import run_digest
        d = run_digest()
        assert d["totals"]["matters_count"] == 0
        assert d["totals"]["total_hits"] == 0


# ────────────────────────────── matters ────────────────────────────────────
class TestMatters:
    def test_add_firm_requires_name(self):
        from matters import add_firm
        with pytest.raises(ValueError, match="required"):
            add_firm("")

    def test_add_firm_duplicate_rejected(self):
        from matters import add_firm
        add_firm("Test & Co")
        with pytest.raises(ValueError, match="exists"):
            add_firm("test & co")    # case-insensitive

    def test_matter_id_format_includes_year_and_seq(self):
        """Matter IDs look like 'FIRMABBR/YYYY/SEQ' where the abbreviation
        is the firm-name's A-Z letters, capped at 8 chars."""
        from matters import add_firm, add_lawyer, add_matter
        from datetime import datetime, timezone
        f = add_firm("Acme Legal")
        l = add_lawyer(f["id"], "Adv. X", role="partner")
        m = add_matter(f["id"], l["id"], "Client One")
        year = datetime.now(timezone.utc).year
        # "ACME LEGAL" → letters only → "ACMELEGAL" → first 8 → "ACMELEGA"
        assert m["id"] == f"ACMELEGA/{year}/0001"

    def test_conflict_check_detects_opposing(self):
        from matters import add_firm, add_lawyer, add_matter, check_conflict
        f = add_firm("Conflict Test")
        l = add_lawyer(f["id"], "Adv. Y")
        add_matter(f["id"], l["id"], "Alice", opposing_party="Bob")
        # Now check if we'd conflict by taking Bob as a new client
        hits = check_conflict(f["id"], client_name="Bob")
        assert len(hits) == 1
        assert "Alice" in hits[0]["reason"]


# ────────────────────────────── auth ───────────────────────────────────────
class TestAuth:
    def test_session_token_roundtrip(self, monkeypatch):
        from auth import make_session_token, verify_session_token, init_db
        init_db()
        tok = make_session_token("usr_abc123")
        assert verify_session_token(tok) == "usr_abc123"

    def test_session_token_bad_signature_rejected(self):
        from auth import make_session_token, verify_session_token
        tok = make_session_token("usr_abc123")
        # Tamper with the signature
        payload, sig = tok.split(".", 1)
        bad = payload + "." + "0" * len(sig)
        assert verify_session_token(bad) is None

    def test_session_token_malformed_returns_none(self):
        from auth import verify_session_token
        assert verify_session_token("") is None
        assert verify_session_token("no-dot-separator") is None
        assert verify_session_token("nopayload.nosig") is None

    def test_code_lifecycle(self):
        from auth import issue_code, verify_code, init_db
        init_db()
        code = issue_code("test@example.com")
        assert len(code) == 6 and code.isdigit()
        # First verify succeeds
        uid1 = verify_code("test@example.com", code)
        assert uid1 and uid1.startswith("usr_")
        # Single-use: second verify with same code fails
        assert verify_code("test@example.com", code) is None
        # Wrong code: never succeeds
        assert verify_code("test@example.com", "000000") is None


# ────────────────────────────── ecourts ────────────────────────────────────
class TestEcourts:
    def test_cnr_format_strict(self):
        from ecourts import is_valid_cnr
        # is_valid_cnr uppercases internally — accepts both cases
        assert is_valid_cnr("MHCC010012342024")
        assert is_valid_cnr("mhcc010012342024")
        # But structurally bad inputs are rejected
        assert not is_valid_cnr("MHCC1234")                 # too short
        assert not is_valid_cnr("MHCC01001234202X")          # non-digit in year
        assert not is_valid_cnr("12CC010012342024")          # state-code must be A-Z
        assert not is_valid_cnr("")

    def test_normalize_strips_punctuation(self):
        from ecourts import normalize_cnr
        assert normalize_cnr(" mh-cc 01/00 1234 / 2024 ") == "MHCC010012342024"

    def test_stub_lookup_returns_full_record(self):
        from ecourts import fetch_cnr_status
        rec = fetch_cnr_status("MHCC010012342024")
        assert rec is not None
        assert rec["court"]
        assert rec["status"] in ("pending", "disposed", "transferred")
        assert "BNS" in " ".join(rec["sections"])

    def test_unknown_cnr_returns_none(self):
        from ecourts import fetch_cnr_status
        assert fetch_cnr_status("ZZZZ010099992025") is None


# ────────────────────────────── tabular ────────────────────────────────────
class TestTabular:
    def test_parse_response_strips_markdown_fences(self):
        from tabular import _parse_response
        raw = "```json\n[{\"contract\": \"A\", \"answer\": \"30 days\"}]\n```"
        out = _parse_response(raw, ["A"])
        assert out == {"A": "30 days"}

    def test_parse_response_strips_prose_preamble(self):
        from tabular import _parse_response
        raw = "Here is the answer:\n[{\"contract\": \"A\", \"answer\": \"X\"}]"
        out = _parse_response(raw, ["A"])
        assert out == {"A": "X"}

    def test_parse_response_handles_missing_contract(self):
        from tabular import _parse_response
        # Only B mentioned in response; A should fall back to parse-error
        raw = '[{"contract": "B", "answer": "Y"}]'
        out = _parse_response(raw, ["A", "B"])
        assert out["A"] == "(parse error)"
        assert out["B"] == "Y"

    def test_run_comparison_with_fake_llm(self, fake_llm_call):
        from tabular import run_comparison, Contract, Clause
        contracts = [
            Contract(name="C1", text="Some contract text."),
            Contract(name="C2", text="Another contract text."),
        ]
        clauses = [Clause(label="L1", question="Q1?")]
        result = run_comparison(contracts, clauses, fake_llm_call)
        assert result["stats"]["cells_filled"] == 2
        assert result["rows"][0]["cells"]["C1"] == "test answer for C1"
        assert result["rows"][0]["cells"]["C2"] == "test answer for C2"

    def test_libraries_have_at_least_5(self):
        from tabular import CLAUSE_LIBRARIES
        assert len(CLAUSE_LIBRARIES) >= 5
        for name, clauses in CLAUSE_LIBRARIES.items():
            assert len(clauses) >= 5  # each library should be substantial
            for c in clauses:
                assert c.label and c.question


# ────────────────────────────── i18n ───────────────────────────────────────
class TestI18n:
    def test_hindi_strings_complete_for_core_keys(self):
        from i18n import get_strings
        en = get_strings("en")
        hi = get_strings("hi")
        # Both languages should have the same key set
        assert set(en.keys()) == set(hi.keys())
        # No empty translations
        for key in en:
            assert en[key], f"missing English for {key}"
            assert hi[key], f"missing Hindi for {key}"

    def test_invalid_lang_falls_back_to_english(self):
        from i18n import get_strings
        assert get_strings("klingon") == get_strings("en")

    def test_hindi_instruction_present(self):
        from i18n import HINDI_SYSTEM_INSTRUCTION
        assert "Devanagari" in HINDI_SYSTEM_INSTRUCTION or "हिन्दी" in HINDI_SYSTEM_INSTRUCTION


# ────────────────────────────── webhooks ───────────────────────────────────
class TestWebhooks:
    def test_add_sub_requires_valid_url(self):
        from webhooks import add_sub
        with pytest.raises(ValueError, match="http"):
            add_sub("not-a-url", ["analysis.completed"])

    def test_add_sub_requires_valid_event(self):
        from webhooks import add_sub
        with pytest.raises(ValueError, match="event"):
            add_sub("https://x.example", ["pretend.event"])

    def test_add_then_list_then_remove(self):
        from webhooks import add_sub, list_subs, remove_sub
        s = add_sub("https://x.example/hook", ["analysis.completed"])
        subs = list_subs()
        assert any(x["id"] == s["id"] for x in subs)
        assert remove_sub(s["id"]) is True
        assert not any(x["id"] == s["id"] for x in list_subs())

    def test_remove_unknown_returns_false(self):
        from webhooks import remove_sub
        assert remove_sub("wh_doesnotexist") is False


# ────────────────────────────── llm_provider ───────────────────────────────
class TestLlmProvider:
    def test_default_provider_is_groq(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        import llm_provider
        assert llm_provider.get_provider() == "groq"

    def test_provider_override(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        import llm_provider
        assert llm_provider.get_provider() == "ollama"

    def test_ollama_host_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://custom:1234")
        import llm_provider
        assert llm_provider.ollama_host() == "http://custom:1234"

    def test_complete_groq_path_delegates(self, monkeypatch):
        """When provider=groq, complete() returns delegate=True so the caller
        knows to use its own Groq SDK path."""
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        import llm_provider
        r = llm_provider.complete(system_messages=["s"], user_message="u")
        assert r.get("delegate") is True


# ────────────────────────────── nalsa ──────────────────────────────────────
class TestNalsa:
    def test_validation_rejects_missing_fields(self):
        from nalsa import validate
        ok, err = validate({})
        assert not ok and err

    def test_validation_rejects_bad_email(self):
        from nalsa import validate
        ok, err = validate({
            "full_name": "X", "email": "no-at-sign", "phone": "+919876543210",
            "slsa": "Maharashtra", "bar_council_no": "MAH/1/2000",
            "panel_id": "abc-123", "consent_to_contact": True,
        })
        assert not ok and "email" in err.lower()

    def test_validation_rejects_unknown_slsa(self):
        from nalsa import validate
        ok, err = validate({
            "full_name": "X", "email": "x@y.in", "phone": "+919876543210",
            "slsa": "Fakistan", "bar_council_no": "MAH/1/2000",
            "panel_id": "abc-123", "consent_to_contact": True,
        })
        assert not ok and "SLSA" in err

    def test_valid_registration_persists(self):
        from nalsa import register, is_registered
        reg = register({
            "full_name": "Adv. Test User",
            "email": "user@firm.example",
            "phone": "+91 98765 43210",
            "slsa": "Maharashtra",
            "bar_council_no": "MAH/1/2000",
            "panel_id": "TEST-PANEL-001",
            "consent_to_contact": True,
        })
        assert reg.id.startswith("nalsa_")
        assert is_registered("user@firm.example")
        assert not is_registered("never-registered@example.com")


# ────────────────────────────── mailer (Day 17) ────────────────────────────
class TestMailer:
    def test_stdout_provider_succeeds(self, monkeypatch):
        monkeypatch.delenv("MAIL_PROVIDER", raising=False)
        import mailer
        r = mailer.send(to="test@example.com", subject="hi", text="hello")
        assert r.ok
        assert r.provider == "stdout"

    def test_missing_to_returns_error(self, monkeypatch):
        import mailer
        r = mailer.send(to="", subject="hi", text="hello")
        assert not r.ok
        assert "to" in r.error.lower()

    def test_unknown_provider_returns_error(self, monkeypatch):
        monkeypatch.setenv("MAIL_PROVIDER", "carrier-pigeon")
        import mailer
        r = mailer.send(to="x@y.in", subject="hi", text="hello")
        assert not r.ok
        assert "carrier-pigeon" in r.error

    def test_smtp_provider_missing_host(self, monkeypatch):
        monkeypatch.setenv("MAIL_PROVIDER", "smtp")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        import mailer
        r = mailer.send(to="x@y.in", subject="hi", text="hello")
        assert not r.ok
        assert "SMTP_HOST" in r.error

    def test_send_login_code_includes_code_and_ttl(self, monkeypatch, capsys):
        monkeypatch.delenv("MAIL_PROVIDER", raising=False)
        import mailer
        r = mailer.send_login_code("x@y.in", "123456", ttl_minutes=15)
        assert r.ok
        out = capsys.readouterr().out
        assert "123456" in out
        assert "x@y.in" in out


# ────────────────────────────── db.py (Day 20) ─────────────────────────────
class TestDbModule:
    def test_disabled_when_no_url(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import db
        assert not db.is_enabled()

    def test_enabled_with_sqlite_url(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/lex.db")
        # Force re-evaluation of the engine
        import db
        db._engine = None
        assert db.is_enabled()
        db.create_all()
        with db.session() as s:
            # All 7 tables should be empty + queryable
            for cls in (db.Firm, db.Lawyer, db.Matter, db.MonitorMatter,
                        db.NalsaRegistration, db.Lead, db.WebhookSub):
                assert s.query(cls).count() == 0

    def test_health_check_reports_disabled_when_url_unset(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import db
        db._engine = None
        h = db.health_check()
        assert not h["ok"]
        assert "DATABASE_URL" in h["error"]

    def test_session_raises_when_disabled(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import db, pytest
        db._engine = None
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            with db.session():
                pass
