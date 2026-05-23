"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — i18n (Day 4 of Legora teardown)                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS DOES
──────────────
Two-part Hindi support:
  (1) Static UI strings translated to Hindi (Devanagari) — toggle on the
      front-end persists in localStorage; the language= query param also works.
  (2) A `?lang=hi` flag on /analyze that adds a system instruction asking
      Groq Llama-3.3-70B to generate the six legal sections in Hindi
      (mixed Devanagari + English legal citations, which is how Indian
      bilingual pleadings are actually written).

WHY THIS MATTERS COMMERCIALLY
─────────────────────────────
- Bombay HC, MP HC, UP HC etc. routinely accept Hindi pleadings under
  Article 348(2) of the Constitution.
- Legora speaks no Indian languages.  This is a moat they will take 12+
  months to attempt.
- For a Tier-2 / Tier-3 city solo practitioner, Hindi-first output is the
  difference between "AI tool" and "useful AI tool".

DESIGN
──────
- Frontend uses data-i18n attributes; a tiny client-side translator swaps
  text content based on the current lang.
- This module ALSO exposes get_strings(lang) for any server-rendered
  template path (currently unused — all i18n is client-side).
- Hindi instruction for Groq is in HINDI_SYSTEM_INSTRUCTION below; it is
  injected as an extra system message when lang='hi' on /analyze.
"""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    # ── Landing page (basics only — the marketing landing keeps English to
    #     match the brand voice, but the app pages are fully translated.
    "nav.landing":     {"en": "Landing",          "hi": "मुख्य पृष्ठ"},
    "nav.analyze":     {"en": "Analyze a case",   "hi": "केस विश्लेषण"},
    "nav.convert":     {"en": "Convert IPC → BNS","hi": "IPC → BNS रूपांतरण"},
    "nav.monitor":     {"en": "Monitor",          "hi": "मॉनिटर"},
    "nav.matters":     {"en": "Matters",          "hi": "केस फ़ाइलें"},
    "nav.tabular":     {"en": "Tabular",          "hi": "तुलना तालिका"},
    "nav.ecourts":     {"en": "e-Courts",         "hi": "ई-कोर्ट"},
    "nav.trust":       {"en": "Trust",            "hi": "विश्वास"},
    "nav.status":      {"en": "Status",           "hi": "स्थिति"},
    "nav.nalsa":       {"en": "For NALSA",        "hi": "NALSA पैनल"},
    "nav.login":       {"en": "Sign in",          "hi": "साइन इन"},
    "nav.try":         {"en": "Try the engine",   "hi": "इंजन का उपयोग करें"},
    "common.lang.toggle.en": {"en": "EN", "hi": "EN"},
    "common.lang.toggle.hi": {"en": "हिन्दी", "hi": "हिन्दी"},

    # ── App page (intake form)
    "app.header.title":     {"en": "BNS Transition Engine",
                              "hi": "BNS संक्रमण इंजन"},
    "app.header.sub":       {"en": "AI-Powered Junior Associate",
                              "hi": "AI-संचालित जूनियर एडवोकेट"},
    "app.new_case":         {"en": "New Case", "hi": "नया केस"},
    "app.case_history":     {"en": "Case History", "hi": "केस का इतिहास"},
    "app.intake.title":     {"en": "Client Intake", "hi": "क्लाइंट विवरण"},
    "app.intake.help":      {
        "en": "Type or paste the client's statement below. Include: who was harmed, what happened, when, where, names of accused, and any evidence available.",
        "hi": "नीचे क्लाइंट का बयान लिखें या पेस्ट करें। शामिल करें: कौन प्रभावित हुआ, क्या हुआ, कब, कहाँ, आरोपी के नाम, और उपलब्ध साक्ष्य।"
    },
    "app.intake.statement": {"en": "Client's Statement", "hi": "क्लाइंट का बयान"},
    "app.intake.placeholder": {
        "en": "Example: Client is a 28-year-old married woman. Since the first month of marriage, her husband and his mother have been demanding a car as additional dowry…",
        "hi": "उदाहरण: क्लाइंट एक 28 वर्षीय विवाहित महिला हैं। शादी के पहले महीने से, उनके पति और सास अतिरिक्त दहेज के रूप में कार की माँग कर रहे हैं…"
    },
    "app.intake.speak":     {"en": "Speak", "hi": "बोलकर बताएँ"},
    "app.intake.attach":    {"en": "Attach Evidence", "hi": "साक्ष्य संलग्न करें"},
    "app.intake.attach.help": {"en": "(optional — PDF, JPG, PNG)", "hi": "(वैकल्पिक — PDF, JPG, PNG)"},
    "app.intake.run":       {"en": "Run Legal Analysis", "hi": "केस विश्लेषण चलाएँ"},
    "app.intake.lang_label":{"en": "Output language", "hi": "आउटपुट भाषा"},
    "app.intake.lang.en":   {"en": "English", "hi": "अंग्रेज़ी"},
    "app.intake.lang.hi":   {"en": "Hindi (हिन्दी)", "hi": "हिन्दी"},

    # ── Quick-test buttons
    "app.quick.dv":         {"en": "Domestic Violence", "hi": "घरेलू हिंसा"},
    "app.quick.cyber":      {"en": "Cyber Threat & Defamation", "hi": "साइबर धमकी और मानहानि"},
    "app.quick.stalking":   {"en": "Stalking & Voyeurism", "hi": "पीछा करना और ताक-झाँक"},

    # ── Results panel
    "app.results.complete": {"en": "Case Analysis Complete", "hi": "केस विश्लेषण पूर्ण"},
    "app.results.new":      {"en": "New Analysis", "hi": "नया विश्लेषण"},
    "app.results.edit":     {"en": "Edit & Supplement", "hi": "संपादन और संशोधन"},
    "app.results.download": {"en": "Download PDF Case Brief", "hi": "PDF केस ब्रीफ डाउनलोड करें"},

    # ── Sources panel
    "sources.title":        {"en": "Verified Sources", "hi": "सत्यापित स्रोत"},
    "sources.help":         {
        "en": "every section cited below was retrieved from this curated knowledge base. Click any card to view the verified text.",
        "hi": "नीचे उद्धृत प्रत्येक अनुभाग इस सत्यापित ज्ञानकोश से लिया गया है। पूर्ण पाठ देखने के लिए किसी भी कार्ड पर क्लिक करें।"
    },

    # ── Section headings (the 6 analysis sections)
    "section.1":            {"en": "Section 1  —  Immediate Client Advisory", "hi": "खंड 1 — तत्काल क्लाइंट सलाह"},
    "section.2":            {"en": "Section 2  —  BNS Legal Analysis",        "hi": "खंड 2 — BNS विधिक विश्लेषण"},
    "section.3":            {"en": "Section 3  —  Case Strategy & Strength Assessment", "hi": "खंड 3 — केस रणनीति एवं सशक्तता आकलन"},
    "section.4":            {"en": "Section 4  —  Draft First Information Report (FIR)", "hi": "खंड 4 — प्राथमिकी (FIR) का प्रारूप"},
    "section.5":            {"en": "Section 5  —  Draft Legal Notice",        "hi": "खंड 5 — विधिक नोटिस का प्रारूप"},
    "section.6":            {"en": "Section 6  —  Police Help Report",        "hi": "खंड 6 — पुलिस सहायता रिपोर्ट"},
    "section.action":       {"en": "ACTION REQUIRED", "hi": "तुरंत कार्रवाई"},

    # ── Find Help Near You
    "findhelp.title":       {"en": "Find Help Near You", "hi": "निकटस्थ सहायता खोजें"},
    "findhelp.police":      {"en": "Nearest Police Station", "hi": "निकटतम पुलिस स्टेशन"},
    "findhelp.lawyer":      {"en": "Find a Lawyer", "hi": "एडवोकेट खोजें"},

    # ── Disclaimer
    "disclaimer":           {
        "en": "Important: This report was generated by AI and must be reviewed by a licensed Advocate before filing. All placeholder fields in CAPS must be filled in. Lex-Indic is not a law firm and this does not constitute legal advice.",
        "hi": "महत्वपूर्ण: यह रिपोर्ट AI द्वारा निर्मित है और इसे दाखिल करने से पहले लाइसेंस प्राप्त एडवोकेट द्वारा समीक्षा अवश्य की जानी चाहिए। सभी BIG-CAPS में दर्शित प्लेसहोल्डर भरने होंगे। Lex-Indic एक लॉ-फर्म नहीं है और यह विधिक सलाह नहीं है।"
    },

    # ── LEXI chat
    "chat.title":           {"en": "Ask LEXI", "hi": "LEXI से पूछें"},
    "chat.placeholder":     {"en": "Ask about a BNS section…", "hi": "किसी BNS अनुभाग के बारे में पूछें…"},
}


HINDI_SYSTEM_INSTRUCTION = """
LANGUAGE INSTRUCTION — मुख्य भाषा निर्देश:

Output ALL six sections in Hindi (हिन्दी / Devanagari script).  Follow these
rules precisely:

1. The narrative, advisory, strategy, and explanatory text — all in HINDI.
2. BNS section numbers and citations — keep as-is in English / numerals
   (e.g. "BNS धारा 304", "Section 103").  Mixing Devanagari with English
   citation numbers is the standard for Indian bilingual pleadings.
3. Names of parties / addresses / dates — keep in the script the client
   used in their statement (do not transliterate names from English to
   Devanagari unless the client wrote them in Devanagari).
4. Headers must use the exact section titles shown below — DO NOT
   translate the heading delimiters.  Example:

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SECTION 1: IMMEDIATE CLIENT ADVISORY
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5. Placeholder fields stay in BLOCK CAPS English (e.g. [COMPLAINANT NAME],
   [पुलिस स्टेशन NAME]) — the lawyer needs to find and fill these.
6. Punishment, bailable status, and cognizable info — keep technical
   terms in English (e.g. "Non-bailable" not "गैर-जमानती") because
   that is the form the Indian police and courts use in actual records.

Remember: This is the OUTPUT language only.  Your section structure,
headings, and grounding rules from the main system prompt remain unchanged.
""".strip()


def get_strings(lang: str = "en") -> dict[str, str]:
    """Return a flat dict of i18n_key -> translated_string for the given lang."""
    if lang not in ("en", "hi"):
        lang = "en"
    return {k: v.get(lang, v["en"]) for k, v in STRINGS.items()}


def get_all() -> dict:
    """Return the full nested dict — useful for shipping i18n JSON to the frontend."""
    return STRINGS
