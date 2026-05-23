"""
Flask route smoke tests.  No network: ChromaDB build, Groq, and Gemini
are all stubbed at import time so the app loads in <2 seconds.

These tests verify URL routing, JSON contracts, status codes, and basic
auth gates — the kind of regressions that would otherwise only show up
after a deploy.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ────────────────────────────── App fixture ────────────────────────────────
# We import app.py once per test session with all the slow / network-dependent
# pieces patched out.  The fixture below builds a Flask test client.

@pytest.fixture(scope="session")
def app():
    # Patch the expensive module-level work BEFORE importing app.py.
    # The patches need to survive for the lifetime of the session.

    # 1) Stub the Groq client so it never hits the network
    from groq import Groq as _RealGroq
    fake_groq = MagicMock()
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=MagicMock(content=(
        "SECTION 1: IMMEDIATE CLIENT ADVISORY\n"
        "Test advisory.\n\n"
        "SECTION 2: LEGAL ANALYSIS UNDER BNS 2023\n"
        "Test legal analysis citing BNS Section 304.\n\n"
        "SECTION 3: CASE STRATEGY & STRENGTH ASSESSMENT\n"
        "Test strategy.\n\n"
        "SECTION 4: DRAFT FIRST INFORMATION REPORT (FIR)\n"
        "Test FIR.\n\n"
        "SECTION 5: DRAFT LEGAL NOTICE\n"
        "Test notice.\n\n"
        "SECTION 6: POLICE HELP REPORT\n"
        "Test police report.\n"
    ))) ]
    fake_groq.chat.completions.create.return_value = fake_completion

    # 2) Stub ChromaDB collection to return canned hits
    fake_collection = MagicMock()
    fake_collection.query.return_value = {
        "documents":  [["BNS Section 304 doc text", "BNS Section 115 doc text"]],
        "metadatas":  [[
            {"section": "BNS Section 304", "title": "Snatching", "old_ipc": "(NEW)",
             "punishment": "Up to 3 years + fine", "bailable": "Non-bailable",
             "cognizable": "Yes", "transition_note": "..."},
            {"section": "BNS Section 115", "title": "Hurt", "old_ipc": "IPC 323",
             "punishment": "Up to 1 year + fine", "bailable": "Bailable",
             "cognizable": "Yes", "transition_note": "..."},
        ]],
        "distances":  [[0.3, 0.4]],
        "ids":        [["bns_304", "bns_115"]],
    }
    fake_collection.count.return_value = 2
    fake_collection.get.return_value = {"ids": ["bns_304", "bns_115"]}

    # 3) Stub Gemini embedding
    fake_gemini_embed = {"embedding": [0.1] * 768}

    # 4) Patch everything before app.py runs its top-level code
    with patch("main.Groq") as MockGroq, \
         patch("main.build_rag_knowledge_base", return_value=fake_collection), \
         patch("main.genai.embed_content", return_value=fake_gemini_embed), \
         patch("main.configure_groq", return_value=fake_groq), \
         patch("main._get_embedding_with_cache", return_value=[0.1] * 768):
        MockGroq.return_value = fake_groq

        # Force-reload the app module so the patches take effect
        if "app" in sys.modules:
            del sys.modules["app"]
        import app as flask_app_module

        # Also patch the live groq_client and rag_collection on the module
        flask_app_module.groq_client = fake_groq
        flask_app_module.rag_collection = fake_collection

        # Patch the analyze flow's retrieval helper so it doesn't try Gemini
        from main import _normalize_source
        def fake_retrieve(collection, story, n_results=8):
            sources = [
                _normalize_source(1, "bns_304", "snatching text",
                                  {"section": "BNS Section 304", "title": "Snatching",
                                   "old_ipc": "(NEW)", "punishment": "Up to 3 years",
                                   "bailable": "Non-bailable", "cognizable": "Yes",
                                   "transition_note": "..."}, 70.0),
            ]
            return ("=== RETRIEVED ===\n[SECTION 1 — 70.0%]\nsnatching text", sources)
        flask_app_module.retrieve_relevant_sections_structured = fake_retrieve

        yield flask_app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


# ────────────────────────────── Public pages ───────────────────────────────
class TestPublicPages:
    @pytest.mark.parametrize("path", [
        "/", "/app", "/trust", "/convert", "/monitors",
        "/tabular", "/ecourts", "/matters", "/nalsa",
        "/status", "/login", "/try", "/addin/install", "/addin/taskpane",
    ])
    def test_all_pages_render_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert len(r.data) > 1000, f"{path} returned suspiciously small body"


# ────────────────────────────── JSON contracts ─────────────────────────────
class TestJsonContracts:
    def test_status_json_shape(self, client):
        r = client.get("/status.json")
        assert r.status_code == 200
        d = r.get_json()
        assert "version" in d
        assert "kb" in d and "total" in d["kb"]
        assert "llm" in d and "provider" in d["llm"]
        assert "uptime" in d

    def test_trust_posture_json(self, client):
        r = client.get("/trust/posture.json")
        assert r.status_code == 200
        d = r.get_json()
        assert "questions" in d and len(d["questions"]) >= 25
        assert "data_flow" in d and len(d["data_flow"]) >= 5

    def test_i18n_strings_full(self, client):
        r = client.get("/i18n/strings.json")
        assert r.status_code == 200
        d = r.get_json()
        assert "nav.landing" in d
        assert d["nav.landing"]["hi"]

    def test_i18n_strings_hindi_only(self, client):
        r = client.get("/i18n/strings.json?lang=hi")
        assert r.status_code == 200
        d = r.get_json()
        # Flat dict when lang= is specified
        assert isinstance(d["nav.landing"], str)
        # Hindi entries should contain Devanagari
        assert any("ऀ" <= c <= "ॿ" for c in d["nav.landing"])

    def test_llm_status_default(self, client, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        r = client.get("/llm/status")
        assert r.status_code == 200
        d = r.get_json()
        assert d["provider"] == "groq"


# ────────────────────────────── /analyze ───────────────────────────────────
class TestAnalyze:
    def test_empty_story_rejected_with_request_id(self, client):
        r = client.post("/analyze", json={"client_story": ""})
        assert r.status_code == 400
        d = r.get_json()
        assert "request_id" in d
        assert "error" in d

    def test_short_story_rejected(self, client):
        r = client.post("/analyze", json={"client_story": "too short"})
        assert r.status_code == 400

    def test_valid_story_returns_six_sections(self, client):
        story = "Client was a victim of chain snatching on 15 May 2026 in Pune, near MG Road. The accused was caught on CCTV."
        r = client.post("/analyze", json={"client_story": story})
        assert r.status_code == 200
        d = r.get_json()
        assert "sections" in d
        # Must have all 6 sections in the response
        for n in range(1, 7):
            key = f"section_{n}"
            assert key in d["sections"]
        assert "sources" in d
        assert "request_id" in d
        assert d["language"] == "en"

    def test_hindi_flag_accepted(self, client):
        story = "Client was a victim of chain snatching on 15 May 2026 in Pune. The accused was caught on CCTV."
        r = client.post("/analyze", json={"client_story": story, "language": "hi"})
        assert r.status_code == 200
        d = r.get_json()
        assert d["language"] == "hi"


# ────────────────────────────── /convert (text path) ───────────────────────
class TestConvert:
    def test_convert_text_round_trip(self, client):
        r = client.post("/convert/text", json={"text": "Charged u/s 302 IPC and Section 420 IPC for cheating."})
        assert r.status_code == 200
        d = r.get_json()
        assert "BNS 103" in d["annotated"]
        assert "BNS 318(4)" in d["annotated"]
        assert d["summary"]["mapped_count"] >= 2

    def test_convert_text_empty_rejected(self, client):
        r = client.post("/convert/text", json={"text": ""})
        assert r.status_code == 400


# ────────────────────────────── Matters CRUD ───────────────────────────────
class TestMattersRoutes:
    def test_firm_lawyer_matter_flow(self, client):
        r = client.post("/matters/api/firms",
                        json={"name": "RouteTest Firm", "address": "Anywhere"})
        assert r.status_code == 200
        firm = r.get_json()["firm"]
        assert firm["id"].startswith("firm_")

        r = client.post("/matters/api/lawyers",
                        json={"firm_id": firm["id"], "full_name": "Adv. T",
                              "role": "associate"})
        assert r.status_code == 200
        lwy = r.get_json()["lawyer"]

        r = client.post("/matters/api/matters",
                        json={"firm_id": firm["id"], "lawyer_id": lwy["id"],
                              "client_name": "Alice", "opposing_party": "Bob"})
        assert r.status_code == 200
        d = r.get_json()
        assert "matter" in d
        assert "conflicts" in d        # always present, may be empty
        assert d["matter"]["client_name"] == "Alice"

    def test_conflict_check_route(self, client):
        # Create the test firm + a matter against Bob
        firm = client.post("/matters/api/firms", json={"name": "ConflictFirm"}).get_json()["firm"]
        lwy  = client.post("/matters/api/lawyers", json={"firm_id": firm["id"], "full_name": "Adv. Z"}).get_json()["lawyer"]
        client.post("/matters/api/matters", json={
            "firm_id": firm["id"], "lawyer_id": lwy["id"],
            "client_name": "Alice", "opposing_party": "Bob"})

        # Now check for conflict if we'd take Bob as a new client
        r = client.post("/matters/api/conflict-check", json={
            "firm_id": firm["id"], "client_name": "Bob"})
        assert r.status_code == 200
        hits = r.get_json()["conflicts"]
        assert len(hits) >= 1


# ────────────────────────────── Auth ───────────────────────────────────────
class TestAuthRoutes:
    def test_login_page_renders(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert b"Sign in" in r.data or b"Lex-Indic" in r.data

    def test_auth_code_then_verify_then_me(self, client):
        # We issue the code via the auth module directly (so this test
        # works in BOTH dev mode and prod mode — prod hides the code
        # from the /auth/code response).
        import auth as auth_module
        code = auth_module.issue_code("routetest@example.com")

        # Verify via the route
        r = client.post("/auth/verify", json={
            "email": "routetest@example.com", "code": code})
        assert r.status_code == 200
        cookies = r.headers.getlist("Set-Cookie")
        assert any("lex_session=" in c for c in cookies)

        # /auth/me with cookie returns the user
        r = client.get("/auth/me")
        assert r.status_code == 200
        u = r.get_json()
        assert u["authenticated"] is True
        assert u["user"]["email"] == "routetest@example.com"

    def test_bad_code_rejected(self, client):
        client.post("/auth/code", json={"email": "bad-code-test@example.com"})
        r = client.post("/auth/verify", json={
            "email": "bad-code-test@example.com", "code": "999999"})
        assert r.status_code == 401

    def test_unauthenticated_me_returns_401(self, client):
        client.delete_cookie("lex_session")
        r = client.get("/auth/me")
        assert r.status_code == 401


# ────────────────────────────── Admin gate ─────────────────────────────────
class TestAdminGate:
    def test_admin_open_when_token_unset(self, client, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        r = client.get("/admin/soc2/summary.json")
        assert r.status_code == 200

    def test_admin_blocked_without_token(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token-abc")
        r = client.get("/admin/soc2/summary.json")
        assert r.status_code == 401

    def test_admin_accepts_token_header(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token-abc")
        r = client.get("/admin/soc2/summary.json",
                       headers={"X-Admin-Token": "test-token-abc"})
        assert r.status_code == 200

    def test_admin_accepts_token_query(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token-abc")
        r = client.get("/admin/soc2/summary.json?token=test-token-abc")
        assert r.status_code == 200


# ────────────────────────────── Monitors API ───────────────────────────────
class TestMonitorRoutes:
    def test_matter_list_starts_empty(self, client):
        r = client.get("/monitors/api/matters")
        assert r.status_code == 200
        assert r.get_json()["matters"] == []

    def test_add_matter_requires_label(self, client):
        r = client.post("/monitors/api/matters", json={"sections": ["BNS 304"]})
        assert r.status_code == 400

    def test_add_matter_requires_sections_or_keywords(self, client):
        r = client.post("/monitors/api/matters", json={"label": "X"})
        assert r.status_code == 400

    def test_add_then_digest(self, client):
        client.post("/monitors/api/matters", json={
            "label": "snatching watch",
            "sections": ["BNS 304"],
            "keywords": ["chain"],
        })
        r = client.get("/monitors/api/digest")
        assert r.status_code == 200
        d = r.get_json()
        assert d["totals"]["matters_count"] == 1


# ────────────────────────────── e-Courts ───────────────────────────────────
class TestEcourtsRoutes:
    def test_known_cnr_returns_record(self, client):
        r = client.get("/ecourts/api/lookup/MHCC010012342024")
        assert r.status_code == 200
        d = r.get_json()
        assert d["cnr"] == "MHCC010012342024"

    def test_bad_format_returns_400(self, client):
        r = client.get("/ecourts/api/lookup/BAD")
        assert r.status_code == 400

    def test_unknown_returns_404(self, client):
        r = client.get("/ecourts/api/lookup/ZZZZ010099992025")
        assert r.status_code == 404


# ────────────────────────────── Webhooks routes ────────────────────────────
class TestWebhookRoutes:
    def test_subscriptions_crud(self, client):
        # Initially empty
        r = client.get("/webhooks/api/subscriptions")
        assert r.status_code == 200
        assert r.get_json()["subscriptions"] == []

        # Create
        r = client.post("/webhooks/api/subscriptions", json={
            "url": "https://test.example/hook",
            "events": ["analysis.completed"],
        })
        assert r.status_code == 200
        sub = r.get_json()["subscription"]

        # Listed
        r = client.get("/webhooks/api/subscriptions")
        subs = r.get_json()["subscriptions"]
        assert len(subs) == 1

        # Delete
        r = client.delete(f"/webhooks/api/subscriptions/{sub['id']}")
        assert r.status_code == 200
        # Gone
        assert client.get("/webhooks/api/subscriptions").get_json()["subscriptions"] == []

    def test_invalid_url_rejected(self, client):
        r = client.post("/webhooks/api/subscriptions", json={
            "url": "not-a-url",
            "events": ["analysis.completed"],
        })
        assert r.status_code == 400


# ────────────────────────────── NALSA ──────────────────────────────────────
class TestNalsaRoutes:
    def test_register_full_flow(self, client):
        r = client.post("/nalsa/api/register", json={
            "full_name": "Adv. Route Test",
            "email": "route-test@firm.example",
            "phone": "+91 9876543210",
            "slsa": "Maharashtra",
            "bar_council_no": "MAH/1/2000",
            "panel_id": "ROUTE-TEST-001",
            "consent_to_contact": True,
        })
        assert r.status_code == 200
        reg = r.get_json()["registration"]
        assert reg["id"].startswith("nalsa_")

    def test_invalid_rejected(self, client):
        r = client.post("/nalsa/api/register", json={"full_name": ""})
        assert r.status_code == 400

    def test_stats_returns_counts(self, client):
        r = client.get("/nalsa/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert "total_registrations" in d
        assert "by_slsa" in d


# ────────────────────────────── /try lead capture ──────────────────────────
class TestTryRoutes:
    def test_try_page_renders(self, client):
        r = client.get("/try")
        assert r.status_code == 200

    def test_submit_requires_name_and_email(self, client):
        r = client.post("/try/submit", json={})
        assert r.status_code == 400

    def test_submit_full_payload(self, client):
        r = client.post("/try/submit", json={
            "full_name": "Adv. Test Prospect",
            "email": "prospect@firm.example",
            "firm_or_org": "Test Firm",
            "role": "partner",
            "interests": ["bns_transition", "word_addin"],
            "how_heard": "via Yuvraj's email",
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["lead"]["id"].startswith("lead_")
        assert d["lead"]["full_name"] == "Adv. Test Prospect"

    def test_leads_list_requires_admin_when_token_set(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token-abc")
        r = client.get("/try/api/leads")
        assert r.status_code == 401


# ────────────────────────────── /api/v1 (Day 16) ───────────────────────────
class TestApiV1:
    def test_openapi_spec_served(self, client):
        r = client.get("/api/v1/openapi.json")
        assert r.status_code == 200
        spec = r.get_json()
        assert spec["openapi"].startswith("3.")
        assert spec["info"]["title"] == "Lex-Indic API"
        # Must document /analyze, /convert/text, /ecourts/lookup, etc.
        assert "/analyze" in spec["paths"]
        assert "/convert/text" in spec["paths"]
        assert "/health" in spec["paths"]

    def test_swagger_ui_loads(self, client):
        r = client.get("/api/v1/docs")
        assert r.status_code == 200
        assert b"swagger" in r.data.lower()
        assert b"/api/v1/openapi.json" in r.data

    def test_health_no_auth_required(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["version"]

    def test_analyze_requires_api_key(self, client):
        r = client.post("/api/v1/analyze", json={"client_story": "x" * 50})
        assert r.status_code == 401
        d = r.get_json()
        assert "X-Api-Key" in d["error"]

    def test_analyze_rejects_bad_key(self, client):
        r = client.post("/api/v1/analyze",
                        json={"client_story": "x" * 50},
                        headers={"X-Api-Key": "lex_live_doesnotexist:00"})
        assert r.status_code == 401

    def test_analyze_with_valid_key(self, client):
        import api_keys
        # First issue a key for a fake user
        api_keys.init_db()
        key = api_keys.issue_key("usr_test_routes", label="test", rate_per_min=60)
        r = client.post("/api/v1/analyze",
                        json={"client_story": "A real client story with enough chars to pass validation."},
                        headers={"X-Api-Key": key["full_key"]})
        assert r.status_code == 200
        d = r.get_json()
        assert "sections" in d and "sources" in d and "request_id" in d

    def test_sections_endpoint(self, client):
        import api_keys
        key = api_keys.issue_key("usr_test_routes_2", label="sections")
        r = client.get("/api/v1/sections?kind=bns",
                       headers={"X-Api-Key": key["full_key"]})
        assert r.status_code == 200
        d = r.get_json()
        assert d["count"] > 0
        # Every entry must have id, kind, section, title
        for s in d["sections"][:3]:
            assert s["id"].startswith("bns_")
            assert s["kind"] == "bns"
            assert s["section"]
            assert s["title"]

    def test_rate_limit_enforced(self, client):
        import api_keys
        # Issue a key with a very tight rate limit
        key = api_keys.issue_key("usr_rate_test", label="rate", rate_per_min=2)
        # First two requests OK
        for _ in range(2):
            r = client.get("/api/v1/sections?kind=bns",
                           headers={"X-Api-Key": key["full_key"]})
            assert r.status_code == 200
        # Third → 429
        r = client.get("/api/v1/sections?kind=bns",
                       headers={"X-Api-Key": key["full_key"]})
        assert r.status_code == 429

    def test_revoked_key_rejected_after_grace(self, client):
        import api_keys, time
        key = api_keys.issue_key("usr_revoke_test", label="revoke")
        # Revoke with 0-min grace → immediate
        api_keys.revoke_key(key["key_id"], grace_period_min=0)
        time.sleep(0.05)
        r = client.get("/api/v1/sections",
                       headers={"X-Api-Key": key["full_key"]})
        assert r.status_code == 401


# ────────────────────────────── Operator dashboard (Day 19) ────────────────
class TestDashboard:
    def test_open_without_admin_token(self, client, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        r = client.get("/dashboard")
        assert r.status_code == 200

    def test_blocked_without_token(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-tok-xyz")
        r = client.get("/dashboard")
        assert r.status_code == 401

    def test_query_token_unlocks_data(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-tok-xyz")
        r = client.get("/dashboard/data.json?token=test-tok-xyz")
        assert r.status_code == 200
        d = r.get_json()
        assert "kpis" in d and "funnel" in d
        assert "daily_analyses" in d
        # daily_analyses is always exactly 14 days (zero-filled if no data)
        assert len(d["daily_analyses"]) == 14
        for kpi in ("leads_total", "analyses_24h", "matters_total",
                    "users_total", "api_keys_active", "errors_24h"):
            assert kpi in d["kpis"]
