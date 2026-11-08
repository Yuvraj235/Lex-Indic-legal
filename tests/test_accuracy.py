"""
Accuracy guard-rails — the deterministic layer that keeps a model's mistakes
out of a lawyer's draft: citation extraction in every written form, the
IPC→BNS concordance check, tolerant section parsing, output normalisation,
and the one-shot self-correction loop.
"""

from __future__ import annotations

import pytest

GOOD_DRAFT = "\n".join(
    f"SECTION {n}: {title}\n" + "Body text long enough to count as a real section. " * 2
    for n, title in [(1, "IMMEDIATE CLIENT ADVISORY"), (2, "LEGAL ANALYSIS UNDER BNS 2023"),
                     (3, "CASE STRATEGY & STRENGTH ASSESSMENT"),
                     (4, "DRAFT FIRST INFORMATION REPORT (FIR)"),
                     (5, "DRAFT LEGAL NOTICE"), (6, "POLICE HELP REPORT")]
) + "\nBNS 103 (old IPC 302) applies."


class TestCitationExtraction:
    @pytest.mark.parametrize("text,expected", [
        ("BNS 103", {"103"}),
        ("BNS Section 85(1)", {"85(1)"}),
        ("Section 302 of the Bharatiya Nyaya Sanhita, 2023", {"302"}),
        ("Sections 85, 86 and 80 of the Bharatiya Nyaya Sanhita", {"80", "85", "86"}),
        ("Bharatiya Nyaya Sanhita, 2023, Section 318(4)", {"318(4)"}),
        ("S. 309 BNS", {"309"}),
        ("BNS 2023", set()),
        ("under the BNS, 2023 the offence", set()),
        ("BNSS 173", set()),
        ("BNS §85 (replaces IPC §498A)", {"85"}),           # gpt-oss writes the section sign
        ("BNS §§ 85 and 86", {"85", "86"}),
        ("§85 of the BNS", {"85"}),
        ("BNS 103, 105 and 109(1) apply", {"103", "105", "109(1)"}),
        ("BNS 318(4), 20 witnesses saw it", {"318(4)"}),     # 20 is not a section
    ])
    def test_bns_forms(self, text, expected):
        import verifier
        assert verifier.cited_sections(text) == expected

    def test_bnss_spelled_out(self):
        import verifier
        assert verifier.cited_sections("Section 35 of the BNSS", "BNSS") == {"35"}


class TestMappingMismatch:
    @pytest.mark.parametrize("text,flag", [
        ("Section 302 of the Bharatiya Nyaya Sanhita replaces IPC 302.", ("302", "302")),
        ("IPC 420 is now BNS 316.", ("420", "316")),
        ("IPC §420 is now BNS §316.", ("420", "316")),
    ])
    def test_wrong_pairs_flagged(self, text, flag):
        import verifier
        found = verifier.mapping_mismatches(text)
        assert [(m["ipc"], m["cited_bns"]) for m in found] == [flag]

    @pytest.mark.parametrize("text", [
        "BNS 103 (Murder; old IPC 302) and BNS 85 (old IPC 498A)",
        "Section 498A IPC is now BNS 85.",
        "IPC 323 → BNS 115; IPC 379 → BNS 303",
        "IPC 420 (cheating) is now BNS 318(4).",
        "S. 309 BNS (old IPC 392) applies.",
        "IPC 302 applied before July 2024.",          # no BNS nearby: nothing to pair
    ])
    def test_correct_or_unpaired_text_not_flagged(self, text):
        import verifier
        assert verifier.mapping_mismatches(text) == []

    def test_pairing_stays_in_its_sentence(self):
        import verifier
        found = verifier.mapping_mismatches(
            "Section 302 of the BNS replaces IPC 302. Also see BNS 103.")
        assert [(m["ipc"], m["cited_bns"]) for m in found] == [("302", "302")]

    def test_mismatch_fails_verification(self):
        import verifier
        v = verifier.verify_analysis({"section_2": "IPC 420 is now BNS 316 (cheating)."})
        assert v["mapping_mismatches"] and not v["all_verified"]
        assert "IPC 420 is BNS 318" in verifier.verification_stamp(v)


class TestSectionParsing:
    def test_markdown_and_dash_headings(self):
        from pdf_generator import parse_sections
        text = ("**Section 1 — Immediate Client Advisory**\nx1\n## SECTION 2: Legal Analysis under BNS, 2023\n"
                "x2\n### Section 3. Case Strategy\nx3\n**SECTION 4 – Draft FIR**\nx4\n"
                "Section 5: Legal Notice\nx5\n**Section 6: Police Help Report**\nx6")
        r = parse_sections(text)
        assert [r[f"section_{i}"] for i in range(1, 7)] == ["x1", "x2", "x3", "x4", "x5", "x6"]

    def test_body_line_is_not_a_heading(self):
        from pdf_generator import parse_sections
        r = parse_sections("SECTION 1: IMMEDIATE CLIENT ADVISORY\nSection 3 of the Act applies.\n")
        assert r["section_1"] == "Section 3 of the Act applies."
        assert r["section_3"].startswith("[SECTION 3")


class TestModelOutputCleaning:
    def test_unicode_spaces_and_think_tags(self):
        import llm_provider
        raw = "<think>hidden</think>Section 103 of BNS 2023‑onwards"
        assert llm_provider.clean_model_text(raw) == "Section 103 of BNS 2023-onwards"

    def test_cleaned_citation_now_verifies(self):
        import llm_provider, verifier
        assert verifier.cited_sections(llm_provider.clean_model_text("BNS 103")) == {"103"}

    @pytest.mark.parametrize("model,expect", [
        ("openai/gpt-oss-120b", {"reasoning_effort": "medium"}),
        ("qwen/qwen3.8-27b", {"reasoning_format": "hidden"}),
    ])
    def test_groq_family_params(self, monkeypatch, model, expect):
        import llm_provider
        from unittest.mock import MagicMock
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="BNS 103"))]
        monkeypatch.setenv("GROQ_MODEL", model)
        out = llm_provider.groq_complete(client, [{"role": "user", "content": "q"}], max_tokens=100)
        kwargs = client.chat.completions.create.call_args.kwargs
        assert out == "BNS 103" and kwargs["model"] == model
        assert expect.items() <= kwargs.items()
        assert kwargs["max_completion_tokens"] > 100   # room for hidden reasoning

    def test_audit_records_active_model(self, monkeypatch, isolate_outputs):
        import audit, json
        monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        audit.log_request(endpoint="/t", client_ip="", user_agent="", story="s")
        logs = list((isolate_outputs / "outputs" / "audit").glob("*.log"))
        rec = json.loads(logs[0].read_text().splitlines()[-1])
        assert rec["model"] == "openai/gpt-oss-120b"


class TestSelfCorrection:
    def test_feedback_names_each_problem(self):
        import verifier
        s = {"section_1": "x" * 50,
             "section_2": "Section 302 of the Bharatiya Nyaya Sanhita replaces IPC 302. Also BNS 999."}
        fb = verifier.repair_feedback(s, verifier.verify_analysis(s))
        text = "\n".join(fb)
        assert "SECTION 3" in text and "IPC 302 corresponds to BNS 103, not BNS 302" in text
        assert "BNS 999 does not exist in the Act" in text
        assert "BNS 999 is not in the law provided" not in text      # reported once, precisely

    def test_clean_draft_needs_no_pass(self, app):
        import app as app_module
        calls = []
        out, info = app_module._check_and_repair(GOOD_DRAFT, "p", lambda m: calls.append(m) or "")
        assert out == GOOD_DRAFT and info["attempted"] is False and calls == []

    def test_better_rewrite_accepted(self, app):
        import app as app_module
        bad = GOOD_DRAFT.replace("BNS 103 (old IPC 302)", "BNS 302 (old IPC 302)")
        seen = []
        out, info = app_module._check_and_repair(bad, "PROMPT", lambda m: seen.append(m) or GOOD_DRAFT)
        assert out == GOOD_DRAFT and info["accepted"] is True and info["issues_after"] == 0
        assert "IPC 302 corresponds to BNS 103, not BNS 302" in seen[0] and seen[0].startswith("PROMPT")

    def test_worse_rewrite_rejected(self, app):
        import app as app_module
        bad = GOOD_DRAFT.replace("BNS 103 (old IPC 302)", "BNS 302 (old IPC 302)")
        out, info = app_module._check_and_repair(bad, "p", lambda m: "SECTION 1: IMMEDIATE\nshort")
        assert out == bad and info["accepted"] is False

    def test_failed_pass_keeps_draft(self, app):
        import app as app_module
        bad = GOOD_DRAFT.replace("BNS 103 (old IPC 302)", "BNS 302 (old IPC 302)")

        def boom(_):
            raise RuntimeError("provider down")
        out, info = app_module._check_and_repair(bad, "p", boom)
        assert out == bad and info["error"] == "RuntimeError"


class TestPrecedentVerification:
    TEXT = ("Rely on Arnesh Kumar v. State of Bihar (2014) 8 SCC 273. Also Shafhi Mohammad "
            "v. State of Himachal Pradesh (2018) 2 SCC 801. See Sharma v. Union of India "
            "(2019) 4 SCC 99. Arnesh Kumar v. State of Bihar, (2014) 9 SCC 100. "
            "Ramesh v. Suresh (2023) is the client's dispute.")

    def test_classifies_each_case(self):
        import verifier
        r = verifier.precedent_check(self.TEXT)
        assert {c["case"] for c in r["cited"]} == {"Arnesh Kumar v. State of Bihar",
                                                  "Shafhi Mohammad v. State of Himachal Pradesh"}
        assert r["unverified"] == ["Sharma v. Union of India (2019) 4 SCC 99"]
        assert [b["case"] for b in r["bad_law"]] == ["Shafhi Mohammad v. State of Himachal Pradesh"]
        assert r["wrong_citation"] == [{"case": "Arnesh Kumar v. State of Bihar",
                                        "cited": "(2014) 9 SCC 100", "correct": "(2014) 8 SCC 273"}]

    def test_private_party_dispute_not_flagged(self):
        import verifier
        assert verifier.precedent_check("Ramesh v. Suresh (2023) was settled.")["unverified"] == []

    def test_fake_precedent_fails_verification_and_drives_repair(self):
        import verifier
        sections = {"section_2": "Per Sharma v. Union of India (2019) 4 SCC 99, bail follows."}
        v = verifier.verify_analysis(sections)
        assert not v["all_verified"] and "UNVERIFIED case law" in verifier.verification_stamp(v)
        assert any("Sharma v. Union of India" in line
                   for line in verifier.repair_feedback(sections, v))

    def test_good_precedent_passes(self):
        import verifier
        v = verifier.verify_analysis({"section_2": "Arnesh Kumar v. State of Bihar (2014) 8 SCC 273 "
                                                   "bars automatic arrest; see BNS 85 (old IPC 498A)."})
        assert v["all_verified"] and v["precedents"]["cited"][0]["status"] == "good_law"


class TestStatuteLookup:
    @pytest.mark.parametrize("q,needle", [
        ("What is the BNS equivalent of IPC 323?", "is now BNS 115"),
        ("Which BNS section replaced Section 420 of the IPC?", "is now BNS 318(4)"),
        ("IPC 377 in BNS?", "no direct BNS equivalent"),
        ("Is BNS 70 bailable?", "Bail status: Non-bailable"),
        ("What is the punishment under BNS 85?", "Punishment: Up to 3 years"),
    ])
    def test_table_answers(self, q, needle):
        import statute_lookup
        assert needle in statute_lookup.answer(q)["answer"]

    @pytest.mark.parametrize("q", [
        "Tell me about dowry harassment",            # no section, no table answer
        "Is IPC 302 bailable?",                      # facts are kept for BNS sections
        "What is IPC 999 in BNS?",                   # not in the concordance
    ])
    def test_falls_back_to_model(self, q):
        import statute_lookup
        assert statute_lookup.answer(q) is None

    def test_chat_answers_from_table_without_llm(self, client, app, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module.llm_provider_module, "groq_complete",
                            lambda *a, **k: pytest.fail("model must not be called"))
        d = client.post("/chat", json={"message": "BNS equivalent of IPC 498A?"}).get_json()
        assert d["deterministic"] is True and "BNS 85" in d["reply"]
        assert "Government IPC→BNS concordance" in d["reply"]


class TestStressGrader:
    """tools/eval_stress.py grades against the official Gazette section titles."""

    @pytest.fixture(scope="class")
    def es(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import eval_stress
        return eval_stress

    def test_official_tables_complete(self, es):
        t = es.load_titles()
        assert len(t["BNS"]) == 358 and len(t["BNSS"]) == 531 and len(t["BSA"]) == 170
        assert t["BNS"]["103"] == "Punishment for murder."
        assert t["BNSS"]["482"].startswith("Direction for grant of bail to person apprehending arrest")

    def test_real_number_wrong_offence_flagged(self, es):
        t = es.load_titles()
        assert es.mislabels("Charge under BNS 302 (murder).", t)
        assert es.mislabels("Anticipatory bail under BNSS 438 (anticipatory bail).", t)
        assert not es.mislabels("Charge under BNS 103(1) – murder.", t)
        assert not es.mislabels("Apply under BNSS 482 (anticipatory bail).", t)

    def test_nonexistent_sections(self, es):
        assert es.nonexistent("BNS 420 and BNSS 600 and BNS 318(4)") == ["BNS 420", "BNSS 600"]

    def test_forbidden_only_when_not_ruled_out_in_same_sentence(self, es):
        text = "This is not robbery under BNS 309 because no force was used. Charge: BNS 304 (snatching)."
        assert es.forbidden_hits(text, ["309"]) == []
        assert es.forbidden_hits(text, ["304"])

    def test_grade_needs_every_group_and_concept(self, es):
        t, known = es.load_titles(), es.known_bns_sections()
        sc = {"id": "x", "tier": "easy", "require": [["304"]], "require_bnss": [["482"]],
              "mention": [["snatching"]]}
        body = "Charge: BNS 304 (snatching). Seek anticipatory bail under BNSS 482. " * 2
        g = es.grade({f"section_{i}": body for i in range(1, 7)}, sc, t, known)
        assert g["pass"] and not g["missing"]
        g = es.grade({f"section_{i}": body.replace("482", "483") for i in range(1, 7)}, sc, t, known)
        assert not g["pass"] and g["missing"] == ["BNSS 482"]

    def test_gold_sections_exist_in_official_text(self, es):
        import json
        t = es.load_titles()
        data = json.loads(es.SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
        assert len(data) == 67
        for s in data:
            for g in s.get("require", []) + [[f] for f in s.get("forbid", [])]:
                assert all(n in t["BNS"] for n in g), s["id"]
            for g in s.get("require_bnss", []):
                assert all(n in t["BNSS"] for n in g), s["id"]


class TestOfficialTextChecks:
    """Fake sections, wrong number↔offence labels and not-in-force provisions,
    checked against the official Gazette text (all 358 BNS / 531 BNSS sections)."""

    def test_nonexistent_sections(self):
        import verifier
        assert verifier.nonexistent_sections("BNS 420, BNS 498A, BNS 318(4), BNSS 600, BSA 63") == \
            ["BNS 420", "BNS 498A", "BNSS 600"]

    @pytest.mark.parametrize("text,cited,suggest", [
        ("Charge under BNS 302 (murder).", "BNS 302", "BNS 103"),
        ("BNS 354 – outraging modesty of a woman", "BNS 354", "BNS 74"),
        ("Anticipatory bail under BNSS 438 (anticipatory bail).", "BNSS 438", "BNSS 482"),
    ])
    def test_wrong_label_caught_with_correct_suggestion(self, text, cited, suggest):
        import verifier
        (m,) = verifier.label_mismatches(text)
        assert m["cited"] == cited and suggest in m["suggest"]

    @pytest.mark.parametrize("text", [
        "BNS 103(1) – Murder.", "BNS 3(5) (common intention)", "BNS 304 (Snatching) and theft.",
        "BNS 114. The injury is simple, not grievous.", "Seek bail under BNSS 482 (anticipatory bail).",
        "BNS 331 (house-breaking by night)", "BNS 125(b) (rash driving causing grievous hurt)",
        "BNS 115 – ruled out because the injury is grievous (fracture)",
    ])
    def test_right_labels_and_prose_pass(self, text):
        import verifier
        assert verifier.label_mismatches(text) == []

    def test_hit_and_run_clause_not_in_force(self):
        import verifier
        assert verifier.not_in_force("The driver is liable under BNS 106(2) for fleeing.") == ["BNS 106(2)"]
        assert verifier.not_in_force("Charge BNS 106(1); BNS 106(2) has not been brought into force.") == []

    def test_problems_block_verification_and_drive_repair(self):
        import verifier
        s = {k: "Charge under BNS 302 (murder) and BNS 420. " * 3 for k in verifier.SECTION_KEYS}
        v = verifier.verify_analysis(s)
        assert not v["all_verified"] and v["nonexistent"] == ["BNS 420"]
        fb = "\n".join(verifier.repair_feedback(s, v))
        assert "BNS 420 does not exist" in fb and "BNS 302 is 'Uttering words" in fb
        assert verifier.issue_score(s, v) >= 6
        assert "DO NOT EXIST" in verifier.verification_stamp(v)


class TestLookAlikeGuidance:
    def test_notes_follow_retrieved_families(self):
        import main
        notes = main.distinction_notes({"303", "304"})
        assert notes and "pickpocketing" in notes[0]
        assert any("RASH or NEGLIGENT" in n for n in main.distinction_notes({"115", "125"}))
        assert main.distinction_notes({"999"}) == []
        assert len(main.distinction_notes({"303", "316", "101", "115", "80", "329"})) == 3

    def test_note_sections_exist(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "data" / "legal_corpus"
        titles = json.loads((root / "statutes" / "bns_section_titles.json").read_text())["sections"]
        groups = json.loads((root / "distinctions.json").read_text())["groups"]
        assert all(s in titles for g in groups for s in g["sections"])


class TestOfficialStatuteIndex:
    """statutes.py — every section of the three Acts, from the Gazette text."""

    @pytest.fixture(scope="class")
    def index(self):
        import statutes
        docs, metas, ids = statutes.official_documents(["BNS Section 304 | x\nKEYWORDS: chain snatching"])
        return dict(zip(ids, docs)), dict(zip(ids, metas))

    def test_every_section_present_once(self, index):
        docs, _ = index
        assert sum(k.startswith("bns_") for k in docs) == 358
        assert sum(k.startswith("bnss_") for k in docs) == 531
        assert sum(k.startswith("bsa_") for k in docs) == 170

    def test_document_carries_text_classification_and_old_section(self, index):
        docs, metas = index
        d = docs["bns_304"]
        assert d.startswith("BNS Section 304 — Snatching")
        assert "suddenly or quickly or forcibly seizes" in d
        assert "Cognizable; Non-bailable" in d and "KEYWORDS: chain snatching" in d
        assert "Previously: IPC 302" in docs["bns_103"]
        assert "Previously: CrPC 438" in docs["bnss_482"]
        assert metas["bns_304"]["type"] == "bns_section"

    def test_documents_fit_prompt_budget(self, index):
        import statutes
        docs, _ = index
        assert max(len(d) for d in docs.values()) < statutes.MAX_TEXT + 1200

    def test_real_sections_outside_curated_kb_are_known(self):
        import verifier
        assert "357" in verifier.known_sections()["BNS"]          # not in the curated 89
        s = {k: "Breach of contract to supply a helpless person: BNS 357. " * 3 for k in verifier.SECTION_KEYS}
        assert verifier.verify_analysis(s)["ungrounded"] == []


class TestHybridRouting:
    """LLM_PROVIDER=hybrid — local model first, Groq only for rejected drafts."""

    BAD = GOOD_DRAFT + "\nAlso charge BNS 420 (cheating)."

    def test_clean_local_draft_never_calls_groq(self, app):
        import app as app_module
        remote = []
        text, route, info = app_module._hybrid_generate(
            "p", lambda m: GOOD_DRAFT, lambda m: remote.append(m) or "")
        assert route == "local" and text == GOOD_DRAFT and remote == [] and not info["attempted"]

    def test_rejected_draft_fixed_by_groq_with_findings(self, app):
        import app as app_module
        seen = []
        text, route, info = app_module._hybrid_generate(
            "p", lambda m: self.BAD, lambda m: seen.append(m) or GOOD_DRAFT)
        assert route == "local draft → groq fix" and text == GOOD_DRAFT and info["accepted"]
        assert "BNS 420 does not exist" in seen[0]

    def test_local_fixes_when_groq_busy(self, app):
        import app as app_module
        calls = iter([self.BAD, GOOD_DRAFT])

        def busy(m):
            raise app_module._ProviderBusy("rate limited")
        text, route, _ = app_module._hybrid_generate("p", lambda m: next(calls), busy)
        assert route == "local draft → local fix" and text == GOOD_DRAFT

    def test_groq_drafts_when_local_model_down(self, app):
        import app as app_module

        def down(m):
            raise RuntimeError("Ollama call failed")
        text, route, _ = app_module._hybrid_generate("p", down, lambda m: GOOD_DRAFT)
        assert route == "groq (local model unavailable)" and text == GOOD_DRAFT

    def test_chat_escalates_invented_section(self, app, monkeypatch):
        import app as app_module
        monkeypatch.setenv("LLM_PROVIDER", "hybrid")
        monkeypatch.setattr(app_module.llm_provider_module, "groq_complete", lambda *a, **k: "Groq answer.")
        monkeypatch.setattr(app_module.llm_provider_module, "complete_local",
                            lambda **k: {"text": "File under BNS 420."})
        assert app_module._chat_reply("ctx", "q") == ("Groq answer.", "groq")
        monkeypatch.setattr(app_module.llm_provider_module, "complete_local",
                            lambda **k: {"text": "File under BNS 318 (cheating)."})
        assert app_module._chat_reply("ctx", "q") == ("File under BNS 318 (cheating).", "local")

    def test_ollama_request_sets_context_window(self, monkeypatch):
        import io
        import json
        import llm_provider
        sent = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout):
            sent.update(json.loads(req.data))
            return Resp(json.dumps({"message": {"content": "ok"}}).encode())
        monkeypatch.setattr(llm_provider.urllib.request, "urlopen", fake_urlopen)
        llm_provider.complete_local(system_messages=["s"], user_message="u",
                                    temperature=0.2, max_tokens=10, timeout_s=5)
        assert sent["options"]["num_ctx"] >= 16384     # default 2–4K would cut the prompt


class TestSectionSelector:
    """charge_selector — the model picks from the official BNS title list."""

    @pytest.mark.parametrize("reply,expected", [
        ('{"sections": ["303", "305", "303"]}', ["303", "305"]),
        ('{"sections": ["BNS 304", "999", "309(4)"]}', ["304", "309"]),       # fake 999 dropped
        ("I think 318 and 319 apply.", ["318", "319"]),
        ("<think>…</think>\n{\"sections\": []}", []),
    ])
    def test_only_real_sections_survive(self, reply, expected):
        import charge_selector
        assert charge_selector.parse_selection(reply, limit=5) == expected

    def test_title_list_is_the_whole_act(self):
        import charge_selector
        lines = charge_selector.title_list().splitlines()
        assert len(lines) == 358 and lines[302] == "303: Theft."

    def test_opt_in_only(self, monkeypatch):
        # qwen3:8b selection cut recall 68% → 41% on the stress set: off unless asked for.
        import charge_selector
        monkeypatch.delenv("SECTION_SELECTOR", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "hybrid")
        assert not charge_selector.enabled()
        monkeypatch.setenv("SECTION_SELECTOR", "local")
        assert charge_selector.enabled()

    def test_selected_sections_lead_and_search_fills(self):
        import main

        class FakeCollection:
            def get(self, ids, include):
                return {"ids": ids, "documents": [f"doc {i}" for i in ids],
                        "metadatas": [{"type": "bns_section"} for _ in ids],
                        "embeddings": [[1.0, 0.0] for _ in ids]}

            def query(self, query_embeddings, n_results, where, include):
                pool = "curated" if "$and" in where else str(abs(hash(str(where))))[:6]
                ids = [f"{pool}_{i}" for i in range(n_results)]
                if pool == "curated":
                    ids = ["bns_303"] + ids                       # duplicate of a selected one
                return {"ids": [ids], "documents": [[f"doc {i}" for i in ids]],
                        "metadatas": [[{"type": pool} for _ in ids]], "distances": [[0.5] * len(ids)]}

        r = main._query_pools(FakeCollection(), [1.0, 0.0], 9, selected=["303", "305"])
        ids = r["ids"][0]
        assert ids[:2] == ["bns_303", "bns_305"] and ids.count("bns_303") == 1
        assert len(ids) == 9 and r["distances"][0][0] == pytest.approx(0.0)
        assert main._pool_sizes(9) == {"offences": 6, "other_offences": 1, "procedure": 1, "authorities": 1}


class TestSupremeCourtRecord:
    """verifier.sc_record_check — citations checked against the official SC record."""

    def test_real_citation_for_right_case_passes(self):
        import verifier
        assert verifier.sc_record_check("Arnesh Kumar v. State of Bihar, 2014 INSC 463.") == []
        assert verifier.sc_record_check("Lalita Kumari v. Govt. of U.P., [2013] 14 S.C.R. 713.") == []

    def test_citation_of_another_case_caught(self):
        import verifier
        (r,) = verifier.sc_record_check("Mohammad Arif v. State of Uttar Pradesh, 2024 INSC 891.")
        assert r["problem"].startswith("belongs to Rajneesh Kumar")

    def test_nonexistent_citation_caught(self):
        import verifier
        (r,) = verifier.sc_record_check("Rohit Sharma v. State of Maharashtra (2025 INSC 298)")
        assert r["problem"] == "not in the Supreme Court record"

    def test_blocks_verification_and_drives_repair(self):
        import verifier
        s = {k: "See Rohit Sharma v. State of Maharashtra, 2025 INSC 298. " * 3 for k in verifier.SECTION_KEYS}
        v = verifier.verify_analysis(s)
        assert not v["all_verified"] and v["sc_record"]
        assert "2025 INSC 298" in "\n".join(verifier.repair_feedback(s, v))
        assert "official record" in verifier.verification_stamp(v)


class TestRealJudgmentsVerified:
    def test_official_record_case_counts_as_verified(self):
        import verifier
        p = verifier.precedent_check("See Vijay Singh @ Vijay Kr. Sharma v. The State of Bihar, 2024 INSC 735.")
        assert p["unverified"] == [] and p["cited"][0]["status"] == "official_record"

    def test_wrong_parties_on_real_citation_still_flagged(self):
        import verifier
        t = "See Ramesh Kumar v. State of Punjab, 2024 INSC 735."
        assert verifier.precedent_check(t)["unverified"]
        assert verifier.sc_record_check(t)[0]["problem"].startswith("belongs to Vijay Singh")

    def test_judgment_documents_carry_official_citation(self, tmp_path):
        import gzip
        import sqlite3
        import sc_judgments
        db = tmp_path / "j.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE judgments (insc TEXT PRIMARY KEY, title TEXT, decided TEXT, scr TEXT,"
                    " sections TEXT, excerpt TEXT, text_gz BLOB)")
        con.execute("INSERT INTO judgments VALUES (?,?,?,?,?,?,?)",
                    ("2024 INSC 735", "VIJAY SINGH versus THE STATE OF BIHAR", "25-09-2024",
                     "[2024] 10 S.C.R. 108", "IPC 302, IPC 34", "Issue for Consideration …", gzip.compress(b"x")))
        con.commit()
        docs, metas, ids = sc_judgments.documents(db)
        assert ids == ["scj_2024_INSC_735"] and metas[0]["type"] == "sc_judgment"
        assert "Vijay Singh v. The State Of Bihar — 2024 INSC 735, [2024] 10 S.C.R. 108" in docs[0]


class TestSearchQuery:
    def test_issue_summary_only_with_a_local_model(self, monkeypatch):
        import main
        monkeypatch.setattr(main.llm_provider, "complete_local", lambda **k: {"text": "Cheating by an online seller."})
        monkeypatch.delenv("QUERY_REWRITE", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        assert main._issue_summary("story") == ""
        monkeypatch.setenv("LLM_PROVIDER", "hybrid")
        assert main._issue_summary("story") == "Cheating by an online seller."
        monkeypatch.setenv("QUERY_REWRITE", "off")
        assert main._issue_summary("story") == ""

    def test_issue_summary_failure_falls_back(self, monkeypatch):
        import main

        def down(**k):
            raise RuntimeError("ollama down")
        monkeypatch.setattr(main.llm_provider, "complete_local", down)
        monkeypatch.setenv("QUERY_REWRITE", "local")
        assert main._issue_summary("story") == ""

    def test_definition_brings_its_punishing_section(self):
        import main

        class C:
            def get(self, ids, include):
                return {"ids": ids, "documents": [f"doc {i}" for i in ids], "metadatas": [{} for _ in ids]}
        merged = {"ids": [["bns_101", "bns_116", "bns_117"]], "documents": [["a", "b", "c"]],
                  "metadatas": [[{}, {}, {}]], "distances": [[0.1, 0.2, 0.3]]}
        main._add_punishing_sections(C(), merged)
        assert merged["ids"][0] == ["bns_101", "bns_116", "bns_117", "bns_103"]   # 117 already there
        assert merged["distances"][0][-1] == 0.1


class TestEmbeddingCacheFiles:
    """Gemini vectors are committed (warm deploys); local-model vectors are
    ~15× larger and stay in a gitignored file — GitHub rejects files > 100 MB."""

    def _isolate(self, monkeypatch, tmp_path):
        import main
        monkeypatch.setattr(main, "EMBEDDING_CACHE_FILE", tmp_path / "embedding_cache.json")
        monkeypatch.setattr(main, "LOCAL_EMBEDDING_CACHE_FILE", tmp_path / "embedding_cache.local.json")
        monkeypatch.setattr(main, "_CACHES", {})
        return main

    def test_each_provider_has_its_own_file(self, monkeypatch, tmp_path):
        main = self._isolate(monkeypatch, tmp_path)
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
        assert main._embedding_cache_file() == tmp_path / "embedding_cache.json"
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "ollama")
        assert main._embedding_cache_file() == tmp_path / "embedding_cache.local.json"

    def test_local_vectors_never_land_in_the_committed_file(self, monkeypatch, tmp_path):
        main = self._isolate(monkeypatch, tmp_path)
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "ollama")
        cache = main._load_embedding_cache()
        cache["k"] = [0.5] * 4
        main._save_embedding_cache(cache)
        assert not (tmp_path / "embedding_cache.json").exists()
        assert '"k"' in (tmp_path / "embedding_cache.local.json").read_text()
        assert not list(tmp_path.glob("*.tmp"))          # written via rename

    def test_cache_is_read_from_disk_once(self, monkeypatch, tmp_path):
        main = self._isolate(monkeypatch, tmp_path)
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
        (tmp_path / "embedding_cache.json").write_text('{"a": [1.0]}')
        first = main._load_embedding_cache()
        (tmp_path / "embedding_cache.json").write_text("not json")   # would fail if re-read
        assert main._load_embedding_cache() is first

    def test_prewarm_embeds_what_the_index_embeds(self):
        import main
        docs = ["full text A", "full text B"]
        metas = [{"search_key": "key A"}, {}]
        assert main.embedding_texts(docs, metas) == ["key A", "full text B"]
