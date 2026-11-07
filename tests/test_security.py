"""
Security regression tests — one class per audit finding. Each test pins the
fixed behaviour: who gets a 401/403/404, which secrets fail closed, which
inputs are refused. The suite runs with production behaviour (LEX_ENV unset)
unless a test opts into development.
"""

from __future__ import annotations

import time

import pytest

STORY = ("Client was a victim of chain snatching on 15 May 2026 in Pune, near "
         "MG Road. The accused was caught on CCTV.")


# ─── helpers ────────────────────────────────────────────────────────────────
def login(client, email: str) -> dict:
    """Sign `client` in as `email` (creating the user) and return the user."""
    import auth
    code = auth.issue_code(email)
    r = client.post("/auth/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.get_json()
    return auth.get_user_by_email(email)


def put_in_firm(user: dict, firm_id: str, role: str = "associate") -> dict:
    import auth
    auth.bind_user_to_firm(user["id"], firm_id, role=role)
    return auth.get_user_by_id(user["id"])


def analyze(client) -> dict:
    r = client.post("/analyze", json={"client_story": STORY})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


# ─── C3: secrets fail closed; dev mode is explicit ──────────────────────────
class TestSecretsFailClosed:
    def test_production_without_secret_refuses(self, monkeypatch):
        import envmode
        monkeypatch.delenv("LEX_ENV", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("AUDIT_HASH_SALT", raising=False)
        with pytest.raises(envmode.ConfigError):
            envmode.secret_key()
        with pytest.raises(envmode.ConfigError):
            envmode.audit_salt()

    def test_short_secret_rejected(self, monkeypatch):
        import envmode
        monkeypatch.delenv("LEX_ENV", raising=False)
        monkeypatch.setenv("SECRET_KEY", "short")
        monkeypatch.delenv("AUDIT_HASH_SALT", raising=False)
        with pytest.raises(envmode.ConfigError):
            envmode.secret_key()

    def test_dev_uses_random_persisted_key(self, monkeypatch):
        import envmode
        monkeypatch.setenv("LEX_ENV", "development")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("AUDIT_HASH_SALT", raising=False)
        k1, k2 = envmode.secret_key(), envmode.secret_key()
        assert k1 == k2 and len(k1) >= 32
        assert "do-not-deploy" not in k1

    def test_secret_key_independent_of_audit_salt(self, monkeypatch):
        """Rotating AUDIT_HASH_SALT (DPDP erasure) must not log users out."""
        import auth
        monkeypatch.setenv("SECRET_KEY", "s" * 32)
        monkeypatch.setenv("AUDIT_HASH_SALT", "a" * 32)
        tok = auth.make_session_token("usr_x")
        monkeypatch.setenv("AUDIT_HASH_SALT", "b" * 32)
        assert auth.verify_session_token(tok) == "usr_x"

    def test_no_dev_code_in_production(self, client, monkeypatch):
        monkeypatch.delenv("LEX_ENV", raising=False)
        r = client.post("/auth/code", json={"email": "prod-mode@example.com"})
        assert r.status_code == 200
        assert "dev_code" not in r.get_json()

    def test_dev_code_only_when_explicit(self, client, monkeypatch):
        monkeypatch.setenv("LEX_ENV", "development")
        r = client.post("/auth/code", json={"email": "dev-mode@example.com"})
        assert "dev_code" in r.get_json()


# ─── C1: case files belong to their owner (or firm) ─────────────────────────
class TestCaseFileAccess:
    def test_history_requires_login(self, client):
        assert client.get("/history").status_code == 401

    def test_load_requires_login(self, client):
        assert client.get("/load/case_analysis_20260101_000000.txt").status_code == 401

    def test_anonymous_run_downloads_with_its_token_only(self, client):
        d = analyze(client)
        pdf, tok = d["pdf_filename"], d["download_token"]
        assert client.get(f"/download/{pdf}?approved=1").status_code == 401
        assert client.get(f"/download/{pdf}?approved=1&t={tok}").status_code == 200
        assert client.get(f"/download/{pdf}?approved=1&t=1.deadbeef").status_code == 401

    def test_token_is_bound_to_one_file(self, client):
        a, b = analyze(client), analyze(client)
        assert a["pdf_filename"] != b["pdf_filename"]
        r = client.get(f"/download/{b['pdf_filename']}?approved=1&t={a['download_token']}")
        assert r.status_code == 401

    def test_expired_token_rejected(self):
        import case_access
        tok = case_access.make_download_token("CaseBrief_x.pdf", ttl=-1)
        assert not case_access.verify_download_token("CaseBrief_x.pdf", tok)

    def test_owner_sees_case_other_firm_does_not(self, app):
        owner, other = app.test_client(), app.test_client()
        put_in_firm(login(owner, "owner@firm-a.in"), "firm_a")
        put_in_firm(login(other, "spy@firm-b.in"), "firm_b")
        d = analyze(owner)
        txt = "case_analysis_" + d["pdf_filename"][len("CaseBrief_"):-4] + ".txt"

        mine = owner.get("/history").get_json()
        assert [c["txt_file"] for c in mine] == [txt]
        assert owner.get(f"/load/{txt}").status_code == 200
        assert owner.get(f"/download/{d['pdf_filename']}?approved=1").status_code == 200

        assert other.get("/history").get_json() == []
        assert other.get(f"/load/{txt}").status_code == 404
        assert other.get(f"/download/{d['pdf_filename']}?approved=1").status_code == 404

    def test_same_firm_colleague_can_open(self, app):
        a, b = app.test_client(), app.test_client()
        put_in_firm(login(a, "a@firm-c.in"), "firm_c")
        put_in_firm(login(b, "b@firm-c.in"), "firm_c")
        d = analyze(a)
        assert b.get(f"/download/{d['pdf_filename']}?approved=1").status_code == 200

    def test_unowned_legacy_file_hidden(self, client, isolate_outputs):
        login(client, "legacy@example.com")
        (isolate_outputs / "outputs" / "case_analysis_20260101_000000.txt").write_text(
            "Generated: 01 January 2026\n", encoding="utf-8")
        assert client.get("/load/case_analysis_20260101_000000.txt").status_code == 404

    def test_same_second_runs_get_distinct_files(self, client):
        names = {analyze(client)["pdf_filename"] for _ in range(3)}
        assert len(names) == 3


# ─── C2: matters are scoped to the caller's firm; joining needs an invite ───
def make_firm(client, email: str, name: str) -> dict:
    """Sign in as `email`, create firm `name` (caller becomes partner)."""
    login(client, email)
    r = client.post("/matters/api/firms", json={"name": name})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["firm"]


class TestTenantScoping:
    @pytest.mark.parametrize("method,path", [
        ("get", "/matters/api/firms"), ("get", "/matters/api/lawyers"),
        ("get", "/matters/api/matters"), ("post", "/matters/api/conflict-check"),
        ("get", "/matters/api/ABC/2026/0001/files"),
        ("get", "/matters/api/ABC/2026/0001/history"),
        ("patch", "/matters/api/ABC/2026/0001/status"),
    ])
    def test_anonymous_gets_401(self, client, method, path):
        r = getattr(client, method)(path, json={})
        assert r.status_code == 401

    def test_unbound_user_gets_403_and_no_firms(self, client):
        login(client, "loner@example.com")
        assert client.get("/matters/api/firms").get_json()["firms"] == []
        assert client.get("/matters/api/matters").status_code == 403

    def test_firms_cannot_see_each_other(self, app):
        a, b = app.test_client(), app.test_client()
        fa = make_firm(a, "p@alpha.in", "Alpha Chambers")
        make_firm(b, "p@beta.in", "Beta Chambers")
        lwy = a.post("/matters/api/lawyers", json={"full_name": "Adv. A"}).get_json()["lawyer"]
        m = a.post("/matters/api/matters", json={
            "lawyer_id": lwy["id"], "client_name": "Secret Client"}).get_json()["matter"]

        assert [f["id"] for f in b.get("/matters/api/firms").get_json()["firms"]] != [fa["id"]]
        assert b.get("/matters/api/matters").get_json()["matters"] == []
        assert b.get("/matters/api/lawyers").get_json()["lawyers"] == []
        assert b.get(f"/matters/api/{m['id']}/history").status_code == 404
        assert b.patch(f"/matters/api/{m['id']}/status",
                       json={"status": "closed"}).status_code == 404
        hits = b.post("/matters/api/conflict-check",
                      json={"client_name": "Secret Client", "firm_id": fa["id"]}).get_json()
        assert hits["conflicts"] == []   # body firm_id is ignored

    def test_body_firm_id_ignored_on_create(self, app):
        a, b = app.test_client(), app.test_client()
        fa = make_firm(a, "p@gamma.in", "Gamma Chambers")
        make_firm(b, "p@delta.in", "Delta Chambers")
        r = b.post("/matters/api/lawyers", json={"full_name": "Mole", "firm_id": fa["id"]})
        assert r.get_json()["lawyer"]["firm_id"] != fa["id"]

    def test_second_firm_refused(self, client):
        make_firm(client, "p@epsilon.in", "Epsilon Chambers")
        r = client.post("/matters/api/firms", json={"name": "Epsilon Two"})
        assert r.status_code == 409


class TestFirmInvites:
    def test_bind_without_invite_refused(self, client):
        login(client, "joiner@example.com")
        r = client.post("/auth/bind-firm", json={"firm_id": "firm_anything", "role": "partner"})
        assert r.status_code == 400

    def test_invite_flow_role_comes_from_invite(self, app):
        partner, joiner = app.test_client(), app.test_client()
        firm = make_firm(partner, "p@zeta.in", "Zeta Chambers")
        inv = partner.post("/auth/invites", json={"role": "paralegal"}).get_json()
        login(joiner, "new@zeta.in")
        r = joiner.post("/auth/bind-firm", json={"invite_code": inv["invite_code"],
                                                 "role": "partner"})
        assert r.status_code == 200 and r.get_json()["firm_id"] == firm["id"]
        me = joiner.get("/auth/me").get_json()["user"]
        assert me["firm_id"] == firm["id"] and me["role"] == "paralegal"

    def test_invite_is_single_use(self, app):
        partner, first, second = app.test_client(), app.test_client(), app.test_client()
        make_firm(partner, "p@eta.in", "Eta Chambers")
        code = partner.post("/auth/invites", json={}).get_json()["invite_code"]
        login(first, "one@eta.in"); login(second, "two@eta.in")
        assert first.post("/auth/bind-firm", json={"invite_code": code}).status_code == 200
        assert second.post("/auth/bind-firm", json={"invite_code": code}).status_code == 400

    def test_only_partner_can_invite(self, app):
        partner, assoc = app.test_client(), app.test_client()
        make_firm(partner, "p@theta.in", "Theta Chambers")
        code = partner.post("/auth/invites", json={"role": "associate"}).get_json()["invite_code"]
        login(assoc, "assoc@theta.in")
        assoc.post("/auth/bind-firm", json={"invite_code": code})
        assert assoc.post("/auth/invites", json={"role": "partner"}).status_code == 403

    def test_unknown_role_rejected(self, client):
        make_firm(client, "p@iota.in", "Iota Chambers")
        assert client.post("/auth/invites", json={"role": "superadmin"}).status_code == 400


class TestMatterIdsUnique:
    def test_same_abbreviation_different_firms(self, app):
        a, b = app.test_client(), app.test_client()
        make_firm(a, "p@mehta1.in", "Mehta Associates")
        make_firm(b, "p@mehta2.in", "Mehta Associates LLP")
        ids = []
        for c in (a, b):
            lwy = c.post("/matters/api/lawyers", json={"full_name": "Adv. M"}).get_json()["lawyer"]
            ids.append(c.post("/matters/api/matters", json={
                "lawyer_id": lwy["id"], "client_name": "X"}).get_json()["matter"]["id"])
        assert ids[0].split("/")[0] == ids[1].split("/")[0]   # same abbreviation…
        assert ids[0] != ids[1]                              # …but distinct ids


class TestMatterStatusRoute:
    def test_owner_can_update_status(self, client):
        """Real matter ids contain slashes; the route must accept them."""
        make_firm(client, "p@kappa.in", "Kappa Chambers")
        lwy = client.post("/matters/api/lawyers", json={"full_name": "Adv. K"}).get_json()["lawyer"]
        m = client.post("/matters/api/matters", json={
            "lawyer_id": lwy["id"], "client_name": "Y"}).get_json()["matter"]
        r = client.patch(f"/matters/api/{m['id']}/status", json={"status": "closed"})
        assert r.status_code == 200, r.get_json()


# ─── C4: webhooks — tenant-owned, https-only, public targets only ───────────
class TestWebhookAccess:
    @pytest.mark.parametrize("method,path", [
        ("get", "/webhooks/api/subscriptions"), ("post", "/webhooks/api/subscriptions"),
        ("delete", "/webhooks/api/subscriptions/wh_abc123"), ("get", "/webhooks/api/deliveries"),
    ])
    def test_anonymous_gets_401(self, client, method, path):
        assert getattr(client, method)(path, json={}).status_code == 401

    def test_firms_isolated_and_secret_shown_once(self, app, fake_dns):
        a, b = app.test_client(), app.test_client()
        make_firm(a, "p@hooks-a.in", "Hooks A")
        make_firm(b, "p@hooks-b.in", "Hooks B")
        created = a.post("/webhooks/api/subscriptions", json={
            "url": "https://receiver.example/hook", "events": ["matter.created"]}).get_json()
        sub = created["subscription"]
        assert sub["secret"].startswith("whsec_")
        listed = a.get("/webhooks/api/subscriptions").get_json()["subscriptions"]
        assert [s["id"] for s in listed] == [sub["id"]] and "secret" not in listed[0]
        assert b.get("/webhooks/api/subscriptions").get_json()["subscriptions"] == []
        assert b.delete(f"/webhooks/api/subscriptions/{sub['id']}").status_code == 404

    def test_admin_token_sees_all(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "adm-token-xyz")
        r = client.get("/webhooks/api/subscriptions", headers={"X-Admin-Token": "adm-token-xyz"})
        assert r.status_code == 200


class TestWebhookTargets:
    @pytest.mark.parametrize("addr", [
        "127.0.0.1", "10.1.2.3", "172.16.0.9", "192.168.1.1", "169.254.169.254",
        "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "fe80::1", "fd00::1",
        "::ffff:127.0.0.1",
    ])
    def test_private_and_special_addresses_refused(self, fake_dns, addr):
        import webhooks
        fake_dns["evil.example"] = [addr]
        with pytest.raises(ValueError, match="public"):
            webhooks.validate_target("https://evil.example/hook")

    def test_any_private_answer_refuses(self, fake_dns):
        """A host returning one public and one private address is refused."""
        import webhooks
        fake_dns["split.example"] = ["93.184.215.14", "10.0.0.1"]
        with pytest.raises(ValueError):
            webhooks.validate_target("https://split.example/")

    @pytest.mark.parametrize("url,why", [
        ("http://receiver.example/hook", "https"),
        ("ftp://receiver.example/", "https"),
        ("https://user:pw@receiver.example/", "password"),
        ("https:///nohost", "host"),
    ])
    def test_bad_urls_refused(self, fake_dns, url, why):
        import webhooks
        with pytest.raises(ValueError, match=why):
            webhooks.validate_target(url)

    def test_public_https_accepted(self, fake_dns):
        import webhooks
        assert webhooks.validate_target(" https://receiver.example/hook ") == "https://receiver.example/hook"

    def test_delivery_rechecks_dns(self, fake_dns, monkeypatch):
        """DNS rebinding: the host was public at subscribe time, private now."""
        import webhooks
        sub = webhooks.Subscription(id="wh_x", url="https://rebind.example/", events=[])
        fake_dns["rebind.example"] = ["127.0.0.1"]
        opened = []
        monkeypatch.setattr(webhooks._OPENER, "open", lambda *a, **k: opened.append(a))
        ok, status, err = webhooks._attempt_http(sub, b"{}", "sig", "evt_1")
        assert not ok and err.startswith("blocked") and opened == []

    def test_redirects_not_followed(self, monkeypatch):
        """A public receiver answering 302 → internal URL must not be chased."""
        import http.server, threading, webhooks
        hits = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                hits.append(self.path)
                self.send_response(302)
                self.send_header("Location", "/internal")
                self.end_headers()
            do_GET = do_POST
            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            monkeypatch.setenv("LEX_ENV", "development")   # allow loopback http here
            sub = webhooks.Subscription(
                id="wh_r", url=f"http://127.0.0.1:{srv.server_port}/hook", events=[])
            ok, status, _ = webhooks._attempt_http(sub, b"{}", "sig", "evt_2")
        finally:
            srv.shutdown()
        assert not ok and status == 302 and hits == ["/hook"]


class TestWebhookEventScope:
    def _sub(self, sid, firm):
        import webhooks
        return webhooks.Subscription(id=sid, url="https://r.example/", events=["matter.created"],
                                     firm_id=firm, secret="whsec_" + sid)

    def test_events_reach_own_firm_and_operator_only(self, monkeypatch):
        import webhooks
        subs = [self._sub("wh_a", "firm_a"), self._sub("wh_b", "firm_b"),
                self._sub("wh_op", "*"), self._sub("wh_legacy", "")]
        monkeypatch.setattr(webhooks, "_all_subs", lambda: subs)
        got = {s.id for s in webhooks._load_active_for_event("matter.created", "firm_a")}
        assert got == {"wh_a", "wh_op"}
        anon = {s.id for s in webhooks._load_active_for_event("matter.created", None)}
        assert anon == {"wh_op"}

    def test_signature_uses_subscription_secret(self):
        import hashlib, hmac, webhooks
        sub = self._sub("wh_s", "firm_a")
        body = b'{"event":"matter.created"}'
        sig = hmac.new(webhooks._signing_key(sub), body, hashlib.sha256).hexdigest()
        ts = str(int(time.time()))
        assert webhooks.verify_signature(body, sig, ts, secret=sub.secret)
        assert not webhooks.verify_signature(body, sig, ts, secret="whsec_other")


# ─── C5: erasure confirmation email is actually sent ────────────────────────
class TestErasureEmail:
    def test_deletion_request_sends_confirmation(self, client, isolate_outputs, monkeypatch):
        monkeypatch.delenv("MAIL_PROVIDER", raising=False)   # stdout provider → sent.log
        login(client, "leaving@example.com")
        r = client.post("/profile/delete", json={"reason": "test"})
        assert r.status_code == 200, r.get_json()
        log = (isolate_outputs / "outputs" / "mail" / "sent.log").read_text(encoding="utf-8")
        assert "account deletion scheduled" in log and "leaving@example.com" in log


# ─── Login brute force + code flooding ──────────────────────────────────────
class TestLoginLimits:
    def test_five_wrong_guesses_burn_the_code(self):
        import auth
        code = auth.issue_code("guess@example.com")
        wrong = f"{(int(code) + 1) % 1_000_000:06d}"
        for _ in range(5):
            assert auth.verify_code("guess@example.com", wrong) is None
        assert auth.verify_code("guess@example.com", code) is None   # burned

    def test_right_code_after_a_few_typos_still_works(self):
        import auth
        code = auth.issue_code("typo@example.com")
        wrong = f"{(int(code) + 1) % 1_000_000:06d}"
        for _ in range(4):
            auth.verify_code("typo@example.com", wrong)
        assert auth.verify_code("typo@example.com", code)

    def test_new_code_revokes_old(self):
        import auth
        old = auth.issue_code("twice@example.com")
        new = auth.issue_code("twice@example.com")
        if old != new:
            assert auth.verify_code("twice@example.com", old) is None
        assert auth.verify_code("twice@example.com", new)

    def test_codes_per_email_capped(self, client):
        import auth
        for _ in range(5):
            auth.issue_code("flood@example.com")
        with pytest.raises(auth.RateLimited):
            auth.issue_code("flood@example.com")
        r = client.post("/auth/code", json={"email": "flood@example.com"})
        assert r.status_code == 429

    def test_codes_per_ip_capped(self, client):
        env = {"REMOTE_ADDR": "203.0.113.7"}
        codes = [client.post("/auth/code", json={"email": f"ip{i}@example.com"},
                             environ_base=env).status_code for i in range(11)]
        assert codes[:10] == [200] * 10 and codes[10] == 429


class TestClientIp:
    def test_spoofed_forwarded_for_ignored(self, app):
        import app as app_module
        with app.test_request_context(headers={"X-Forwarded-For": "1.2.3.4"},
                                      environ_base={"REMOTE_ADDR": "10.9.8.7"}):
            assert app_module._client_ip() == "10.9.8.7"

    def test_proxyfix_uses_one_trusted_hop(self):
        from flask import Flask, request
        from werkzeug.middleware.proxy_fix import ProxyFix
        probe = Flask("probe")
        probe.add_url_rule("/", "ip", lambda: f"{request.remote_addr} {request.scheme}")
        probe.wsgi_app = ProxyFix(probe.wsgi_app, x_for=1, x_proto=1)
        body = probe.test_client().get("/", headers={
            "X-Forwarded-For": "6.6.6.6, 198.51.100.4", "X-Forwarded-Proto": "https"},
            environ_base={"REMOTE_ADDR": "10.0.0.2"}).get_data(as_text=True)
        assert body == "198.51.100.4 https"   # the hop the proxy added, not the spoof


# ─── Precedent monitors, NALSA export, API keys ─────────────────────────────
class TestMonitorScoping:
    def test_anonymous_gets_401(self, client):
        for path in ("/monitors/api/matters", "/monitors/api/digest", "/monitors/digest.txt"):
            assert client.get(path).status_code == 401, path

    def test_watchlists_are_private(self, app):
        a, b = app.test_client(), app.test_client()
        make_firm(a, "p@watch-a.in", "Watch A")
        login(b, "solo@watch-b.in")
        m = a.post("/monitors/api/matters", json={
            "label": "Sharma v. State bail", "sections": ["BNS 85"]}).get_json()["matter"]
        assert b.get("/monitors/api/matters").get_json()["matters"] == []
        assert b.get("/monitors/api/digest").get_json()["totals"]["matters_count"] == 0
        assert b.delete(f"/monitors/api/matters/{m['id']}").status_code == 404
        assert a.delete(f"/monitors/api/matters/{m['id']}").status_code == 200

    def test_same_second_ids_distinct(self):
        import monitors
        ids = {monitors.add_matter(f"m{i}", ["x"], [], owner="o")["id"] for i in range(5)}
        assert len(ids) == 5


class TestNalsaExport:
    def test_closed_by_default(self, client, monkeypatch):
        monkeypatch.delenv("NALSA_EXPORT_TOKEN", raising=False)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        assert client.get("/nalsa/api/export.csv").status_code in (401, 503)

    def test_export_token_or_admin(self, client, monkeypatch):
        monkeypatch.setenv("NALSA_EXPORT_TOKEN", "slsa-export-123")
        monkeypatch.setenv("ADMIN_TOKEN", "adm-456")
        assert client.get("/nalsa/api/export.csv").status_code == 401
        assert client.get("/nalsa/api/export.csv",
                          headers={"X-Export-Token": "wrong"}).status_code == 401
        assert client.get("/nalsa/api/export.csv",
                          headers={"X-Export-Token": "slsa-export-123"}).status_code == 200
        assert client.get("/nalsa/api/export.csv",
                          headers={"X-Admin-Token": "adm-456"}).status_code == 200


class TestApiKeyOwnership:
    def _mint(self, client, **body):
        r = client.post("/admin/api-keys", json=body)
        assert r.status_code == 200, r.get_json()
        return r.get_json()["key"]

    def test_cannot_revoke_someone_elses_key(self, app):
        a, b = app.test_client(), app.test_client()
        login(a, "keys-a@example.com"); login(b, "keys-b@example.com")
        key = self._mint(a, label="mine")
        assert b.delete(f"/admin/api-keys/{key['key_id']}").status_code == 404
        assert a.delete(f"/admin/api-keys/{key['key_id']}?immediate=1").status_code == 200

    def test_self_service_rate_is_capped(self, client):
        login(client, "greedy@example.com")
        key = self._mint(client, rate_per_min=1_000_000)
        import api_keys
        rec = api_keys.verify_key(key["full_key"])
        assert rec["rate_per_min"] <= 60

    def test_firmless_key_lists_no_matters(self, app):
        firm, loner = app.test_client(), app.test_client()
        make_firm(firm, "p@apikeys.in", "Api Keys Chambers")
        lwy = firm.post("/matters/api/lawyers", json={"full_name": "Adv. Q"}).get_json()["lawyer"]
        firm.post("/matters/api/matters", json={"lawyer_id": lwy["id"], "client_name": "Hidden"})
        login(loner, "loner-key@example.com")
        key = self._mint(loner)
        r = loner.get("/api/v1/matters", headers={"X-Api-Key": key["full_key"]})
        assert r.status_code == 200 and r.get_json()["matters"] == []


# ─── WhatsApp inbound, stub billing, converted files, request ids ───────────
def _twilio_sig(token: str, url: str, form: dict) -> str:
    import base64, hashlib, hmac
    signed = url + "".join(k + v for k, v in sorted(form.items()))
    return base64.b64encode(hmac.new(token.encode(), signed.encode(), hashlib.sha1).digest()).decode()


class TestWhatsAppInbound:
    FORM = {"From": "whatsapp:+919800000001", "Body": "hello"}

    def test_closed_without_provider_credentials(self, client, monkeypatch):
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("WA_INBOUND_TOKEN", raising=False)
        assert client.post("/wa/inbound", data=self.FORM).status_code == 403

    def test_twilio_signature_checked(self, client, monkeypatch):
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-test-token")
        url = "http://localhost/wa/inbound"
        bad = client.post("/wa/inbound", data=self.FORM,
                          headers={"X-Twilio-Signature": "AAAA"})
        assert bad.status_code == 403
        good = client.post("/wa/inbound", data=self.FORM, headers={
            "X-Twilio-Signature": _twilio_sig("twilio-test-token", url, self.FORM)})
        assert good.status_code == 200 and b"<Response>" in good.data

    def test_shared_token_for_json_providers(self, client, monkeypatch):
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("WA_INBOUND_TOKEN", "msg91-shared-token")
        body = {"mobile": "919800000002", "message": "hi"}
        assert client.post("/wa/inbound", json=body).status_code == 403
        assert client.post("/wa/inbound", json=body,
                           headers={"X-Lex-Inbound-Token": "msg91-shared-token"}).status_code == 200


class TestStubBilling:
    def test_stub_confirm_refused_in_production(self, client, monkeypatch):
        monkeypatch.delenv("STRIPE_MODE", raising=False)
        login(client, "freeloader@example.com")
        r = client.get("/billing/stub-confirm?tier=firm&user=usr_victim")
        assert r.status_code == 403

    def test_checkout_needs_sign_in_and_real_billing(self, client, monkeypatch):
        monkeypatch.delenv("STRIPE_MODE", raising=False)
        assert client.post("/billing/checkout", json={"tier": "firm"}).status_code == 401
        login(client, "buyer@example.com")
        assert client.post("/billing/checkout", json={"tier": "firm"}).status_code == 503

    def test_dev_stub_activates_only_the_caller(self, client, monkeypatch):
        monkeypatch.setenv("LEX_ENV", "development")
        monkeypatch.delenv("STRIPE_MODE", raising=False)
        me = login(client, "dev-buyer@example.com")
        r = client.get("/billing/stub-confirm?tier=firm&user=usr_someone_else")
        assert r.status_code == 200
        import billing
        subs = billing.all_subscriptions()
        owners = {s.get("user_id") for s in (subs if isinstance(subs, list) else subs.values())}
        assert me["id"] in owners and "usr_someone_else" not in owners


class TestMisc:
    def test_converted_file_names_unguessable(self, client):
        import io
        from docx import Document
        doc = Document(); doc.add_paragraph("Accused charged u/s 302 IPC.")
        buf = io.BytesIO(); doc.save(buf); buf.seek(0)
        r = client.post("/convert/upload", data={"file": (buf, "plea.docx")},
                        content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        import re
        assert re.fullmatch(r"plea_\d{8}_\d{6}_[0-9a-f]{16}\.bns\.docx", r.get_json()["filename"])
        assert client.get("/convert/download/plea_20260101_000000.bns.docx").status_code == 400

    @pytest.mark.parametrize("rid,kept", [("abc-123_X.9", True),
                                          ("bad id <script>", False), ("x" * 65, False)])
    def test_request_id_sanitised(self, client, rid, kept):
        r = client.get("/i18n/strings.json", headers={"X-Request-Id": rid})
        assert (r.headers["X-Request-Id"] == rid) is kept


# ─── Medium 3: model output is escaped before it becomes HTML ───────────────
class TestOutputEscaping:
    PAYLOAD = '<img src=x onerror="alert(1)">'

    def test_section_html_escapes_then_bolds(self, app):
        import app as app_module
        out = app_module._section_html(f"**Bail** {self.PAYLOAD}")
        assert out.startswith("<strong>Bail</strong> ")
        assert "<img" not in out and "&lt;img" in out

    def test_loaded_case_is_escaped(self, client, isolate_outputs):
        import case_access
        user = login(client, "xss@example.com")
        name = "case_analysis_20260101_000000_abcdef12.txt"
        (isolate_outputs / "outputs" / name).write_text(
            "Generated: 01 January 2026\n\nCLIENT'S STATEMENT:\nstory\n\n" + "=" * 70 + "\n\n"
            f"SECTION 1: IMMEDIATE CLIENT ADVISORY\nAdvice {self.PAYLOAD}\n\n"
            "SECTION 2: LEGAL ANALYSIS UNDER BNS 2023\nx\n", encoding="utf-8")
        case_access.record(name, None, user_id=user["id"], firm_id=None)
        d = client.get(f"/load/{name}").get_json()
        assert "<img" not in d["sections"]["section_1"]
        assert "&lt;img" in d["sections"]["section_1"]


# ─── High 1: local embeddings + honest "fully local" reporting ──────────────
import main as _main_module
# The app fixture swaps main._get_embedding_with_cache for a mock for the whole
# session; keep the real one (captured at collection) for these tests.
_real_embed = _main_module._get_embedding_with_cache


class TestEmbeddingsProvider:
    def test_ollama_embeddings_stay_local(self, monkeypatch):
        import io, json, main
        seen = []

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout=0):
            seen.append(req.full_url)
            return Resp(json.dumps({"embeddings": [[0.1, 0.2, 0.3]]}).encode())

        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
        monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(main.genai, "embed_content",
                            lambda **k: pytest.fail("Gemini must not be called"))
        cache = {}
        assert _real_embed("story", "retrieval_query", cache) == [0.1, 0.2, 0.3]
        assert seen == ["http://localhost:11434/api/embed"]

    def test_provider_namespaces_cache(self, monkeypatch):
        import main
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "ollama")
        cache = {}
        monkeypatch.setattr(main, "_embed_ollama", lambda t, k: [1.0])
        _real_embed("same text", "retrieval_document", cache)
        import hashlib
        gemini_key = hashlib.md5(b"retrieval_document:same text").hexdigest()
        assert gemini_key not in cache   # never served to a Gemini-built index

    def test_fully_local_needs_both(self, monkeypatch):
        import llm_provider
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.delenv("EMBEDDINGS_PROVIDER", raising=False)
        monkeypatch.setattr(llm_provider, "is_ollama_reachable", lambda *a, **k: True)
        assert llm_provider.status()["fully_local"] is False
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "ollama")
        assert llm_provider.status()["fully_local"] is True


# ─── Medium 8: CORS allowlist, bounded retries ──────────────────────────────
class TestCors:
    def test_no_wildcard_by_default(self, client, monkeypatch):
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
        for path in ("/addin/taskpane", "/addin/manifest.xml"):
            r = client.get(path, headers={"Origin": "https://evil.example"})
            assert "Access-Control-Allow-Origin" not in r.headers, path

    def test_allowlisted_origin_reflected(self, client, monkeypatch):
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://word.firm.in, https://other.in")
        ok = client.options("/convert/text", headers={"Origin": "https://word.firm.in"})
        assert ok.headers["Access-Control-Allow-Origin"] == "https://word.firm.in"
        bad = client.options("/convert/text", headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in bad.headers


class TestProviderRateLimit:
    def test_rate_limited_llm_returns_503_quickly(self, client, app, monkeypatch):
        import app as app_module
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setattr(app_module.time, "sleep", lambda s: None)
        calls = []

        def busy(**kwargs):
            calls.append(1)
            raise RuntimeError("Error code: 429 - rate_limit_exceeded")
        monkeypatch.setattr(app_module.groq_client.chat.completions, "create", busy)
        r = client.post("/analyze", json={"client_story": STORY})
        assert r.status_code == 503 and "request_id" in r.get_json()
        assert len(calls) == 3


class TestFeedParsing:
    def test_dtd_and_entities_refused(self):
        import sc_scraper
        bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
                b'<!ENTITY lol2 "&lol;&lol;&lol;">]><rss>&lol2;</rss>')
        with pytest.raises(RuntimeError, match="DTD"):
            sc_scraper._check_feed(bomb)

    def test_oversized_feed_refused(self):
        import sc_scraper
        with pytest.raises(RuntimeError, match="5 MB"):
            sc_scraper._check_feed(b"<rss>" + b"x" * (5 * 1024 * 1024) + b"</rss>")

    def test_plain_rss_accepted(self):
        import sc_scraper
        sc_scraper._check_feed(b'<?xml version="1.0"?><rss><channel><item/></channel></rss>')


class TestPublicLlmLimits:
    def test_chat_limited_per_ip(self, client):
        env = {"REMOTE_ADDR": "198.51.100.9"}
        codes = [client.post("/chat", json={"message": "What is BNS 85?"},
                             environ_base=env).status_code for _ in range(21)]
        assert 429 not in codes[:20] and codes[20] == 429


# ─── Round 2: headers, size cap, cross-site writes, logout revocation ───────
class TestHardeningRound2:
    def test_security_headers(self, client):
        r = client.get("/app")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
        assert "microphone=(self)" in r.headers["Permissions-Policy"]

    def test_addin_may_be_framed_by_office_only(self, client):
        r = client.get("/addin/taskpane")
        assert "X-Frame-Options" not in r.headers
        assert "https://*.officeapps.live.com" in r.headers["Content-Security-Policy"]

    def test_hsts_only_over_https(self, client):
        assert "Strict-Transport-Security" not in client.get("/app").headers
        r = client.get("/app", base_url="https://localhost")
        assert "max-age=31536000" in r.headers["Strict-Transport-Security"]

    def test_oversized_request_refused(self, client, app):
        big = b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1)
        r = client.post("/analyze", data=big, content_type="application/json")
        assert r.status_code == 413

    def test_cross_site_post_refused(self, client):
        r = client.post("/auth/logout", headers={"Origin": "https://evil.example"})
        assert r.status_code == 403
        assert client.post("/auth/logout", headers={"Origin": "http://localhost"}).status_code == 200
        assert client.post("/auth/logout").status_code == 200   # non-browser caller

    def test_service_webhooks_exempt(self, client, monkeypatch):
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("WA_INBOUND_TOKEN", raising=False)
        r = client.post("/wa/inbound", json={}, headers={"Origin": "https://evil.example"})
        assert r.status_code == 403 and "Unauthorised inbound" in r.get_json()["error"]

    def test_logout_kills_copied_token(self, client, app):
        login(client, "leaver@example.com")
        stolen = client.get_cookie("lex_session").value
        assert client.get("/auth/me").status_code == 200
        client.post("/auth/logout")
        thief = app.test_client()
        thief.set_cookie("lex_session", stolen)
        assert thief.get("/auth/me").status_code == 401

    def test_new_login_after_logout_works(self, client):
        login(client, "returner@example.com")
        client.post("/auth/logout")
        login(client, "returner@example.com")
        assert client.get("/auth/me").status_code == 200
