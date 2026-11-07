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
        assert "BNS 999 is not in the law" in text

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
