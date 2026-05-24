"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Generate three Lex-Indic PDFs:                                              ║
║    1. SalesPitch_LawFirms.pdf       — pitch for Indian + international firms ║
║    2. TechnicalDeepDive_Complete.pdf — every implementation detail + roadmap ║
║    3. UserGuide_EasyLanguage.pdf    — plain-English click-by-click guide     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "pitch_decks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Brand colours ───────────────────────────────────────────────────────────
NAVY      = (15,  40,  80)
GOLD      = (180, 140,  40)
RED       = (180,  30,  30)
GREEN     = (20, 100,  50)
BLUE      = (30,  80, 160)
TEAL      = (20, 110, 110)
PURPLE    = (90,  30, 120)
ORANGE    = (160,  80,   0)
GREY      = (100, 100, 100)
LIGHT_GREY = (245, 245, 245)
WHITE     = (255, 255, 255)
BLACK     = (0,   0,   0)
SOFT_GOLD = (250, 240, 215)
SOFT_BLUE = (230, 240, 255)
SOFT_RED  = (255, 235, 235)
SOFT_GREEN = (225, 245, 230)

_CHAR_MAP = {
    "—": "-", "–": "-", "’": "'", "‘": "'",
    "“": '"', "”": '"', "•": "-", "…": "...",
    "★": "*", "⚠": "[!]", "✓": "OK", "·": ".",
    "→": "->", "←": "<-", "↑": "^", "↓": "v",
    "₹": "Rs.", " ": " ", " ": " ", "​": "",
    "✅": "[OK]", "❌": "[X]", "✨": "*", "\U0001f4b0": "$",
    "\U0001f680": ">", "\U0001f4e7": "@", "\U0001f4f1": "[phone]",
    "\U0001f5a5": "[PC]", "\U0001f513": "[unlock]", "\U0001f50d": "[search]",
    "\U0001f4c4": "[doc]", "\U0001f4ca": "[chart]", "\U0001f4cb": "[clip]",
    "\U0001f3db": "[court]", "\U0001f4dd": "[note]", "\U0001f3af": "[goal]",
    "\U0001f4a1": "[idea]", "\U0001f527": "[wrench]", "\U0001f4e6": "[box]",
}


def _s(text: str) -> str:
    """Sanitize text for latin-1 (Helvetica) output."""
    if text is None:
        return ""
    for k, v in _CHAR_MAP.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ─── Base PDF class with shared helpers ──────────────────────────────────────
class LexPdf(FPDF):
    def __init__(self, doc_title: str, subtitle: str, accent=NAVY):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_title  = doc_title
        self.doc_sub    = subtitle
        self.accent     = accent
        self.set_margins(20, 25, 20)
        self.set_auto_page_break(auto=True, margin=22)
        self.alias_nb_pages()
        self.set_creator("Lex-Indic")
        self.set_author("Lex-Indic / Yuvraj Pratap Singh")
        self.set_title(doc_title)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5, _s(self.doc_title.upper()), align="L")
        self.set_xy(self.l_margin, 8)
        self.cell(0, 5, _s(self.doc_sub), align="R")
        self.set_draw_color(*self.accent)
        self.set_line_width(0.5)
        self.line(self.l_margin, 14, self.w - self.r_margin, 14)
        self.ln(8)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        left = "Lex-Indic - Confidential - " + datetime.now().strftime("%B %Y")
        self.cell(0, 5, _s(left), align="L")
        self.set_xy(self.l_margin, -15)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    # ─── Building blocks ─────────────────────────────────────────────────────
    def h1(self, text: str, colour=None):
        colour = colour or self.accent
        self.ln(6)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*colour)
        self.cell(0, 10, _s(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*GOLD)
        self.set_line_width(0.8)
        x = self.l_margin
        self.line(x, self.get_y(), x + 60, self.get_y())
        self.ln(6)

    def h2(self, text: str, colour=None):
        colour = colour or self.accent
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*colour)
        self.cell(0, 7, _s(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def h3(self, text: str, colour=None):
        colour = colour or BLACK
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*colour)
        self.cell(0, 6, _s(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def para(self, text: str, size: int = 10, indent: int = 0):
        self.set_font("Helvetica", "", size)
        self.set_text_color(*BLACK)
        if indent:
            self.set_x(self.l_margin + indent)
        avail_w = self.w - self.l_margin - self.r_margin - indent
        self.multi_cell(avail_w, 5, _s(text))
        self.ln(2)

    def bullet(self, text: str, level: int = 0, size: int = 10):
        indent = 4 + level * 6
        marker = "-" if level == 0 else "."
        self.set_font("Helvetica", "", size)
        self.set_text_color(*BLACK)
        self.set_x(self.l_margin + indent)
        avail_w = self.w - self.l_margin - self.r_margin - indent - 4
        # bullet glyph
        self.cell(4, 5, marker)
        self.multi_cell(avail_w, 5, _s(text))
        self.ln(0.5)

    def kv(self, key: str, value: str, key_w: int = 50):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.accent)
        self.cell(key_w, 5, _s(key))
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*BLACK)
        avail = self.w - self.l_margin - self.r_margin - key_w
        x = self.get_x(); y = self.get_y()
        self.multi_cell(avail, 5, _s(value))
        self.ln(0)

    def callout(self, text: str, bg=SOFT_GOLD, border=GOLD, font_size=9, bold_first=False):
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        x = self.l_margin
        y = self.get_y()
        avail_w = self.w - self.l_margin - self.r_margin

        self.set_font("Helvetica", "", font_size)
        # measure height
        lines = self.multi_cell(
            avail_w - 6, 5, _s(text), border=0, align="L",
            dry_run=True, output="LINES",
        )
        h = len(lines) * 5 + 6
        self.rect(x, y, avail_w, h, style="DF")
        self.set_xy(x + 3, y + 3)
        if bold_first:
            self.set_font("Helvetica", "B", font_size)
        self.set_text_color(*BLACK)
        self.multi_cell(avail_w - 6, 5, _s(text), border=0, align="L")
        self.set_y(y + h + 3)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None,
              header_bg=None, header_fg=WHITE):
        header_bg = header_bg or self.accent
        avail_w = self.w - self.l_margin - self.r_margin
        if not col_widths:
            col_widths = [int(avail_w / len(headers))] * len(headers)
        # Header
        self.set_fill_color(*header_bg)
        self.set_text_color(*header_fg)
        self.set_font("Helvetica", "B", 9)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, _s(h), fill=True, align="L")
        self.ln()
        # Rows
        self.set_text_color(*BLACK)
        self.set_font("Helvetica", "", 8.5)
        for ri, row in enumerate(rows):
            # alternate row colour
            fill = (ri % 2 == 0)
            if fill:
                self.set_fill_color(*LIGHT_GREY)
            # measure max line count per cell
            line_counts = []
            for ci, cell in enumerate(row):
                lines = self.multi_cell(
                    col_widths[ci], 5, _s(str(cell)),
                    dry_run=True, output="LINES",
                )
                line_counts.append(len(lines))
            row_h = max(line_counts) * 5
            x_start = self.get_x()
            y_start = self.get_y()
            # render each cell
            for ci, cell in enumerate(row):
                cx = x_start + sum(col_widths[:ci])
                self.set_xy(cx, y_start)
                self.multi_cell(col_widths[ci], 5, _s(str(cell)),
                                fill=fill, border=0, align="L")
            self.set_xy(x_start, y_start + row_h)
        self.ln(3)

    def spacer(self, n: int = 4):
        self.ln(n)


# ════════════════════════════════════════════════════════════════════════════
#  PDF 1 — SALES PITCH FOR LAW FIRMS (INDIAN + INTERNATIONAL)
# ════════════════════════════════════════════════════════════════════════════
def build_sales_pitch_pdf():
    pdf = LexPdf(
        doc_title="Lex-Indic - The AI Junior Associate for Indian Law",
        subtitle="Sales & Capabilities Brief",
        accent=NAVY,
    )

    # ── COVER ──────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 90, style="F")
    pdf.set_fill_color(*GOLD)
    pdf.rect(0, 90, pdf.w, 3, style="F")

    pdf.set_xy(20, 25)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 6, _s("LEX-INDIC"))
    pdf.set_xy(20, 32)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 5, _s("THE BNS TRANSITION ENGINE - INDIA"))

    pdf.set_xy(20, 50)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 14, _s("Built for the AI Junior"), new_y=YPos.NEXT)
    pdf.set_x(20)
    pdf.cell(0, 14, _s("Associate, by Indian Law"))

    pdf.set_xy(20, 110)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 10, _s("Sales & Capabilities Brief"), new_y=YPos.NEXT)
    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 7, _s("For Indian Tier-1 firms, international firms with India practice,"))
    pdf.set_x(20); pdf.ln(7)
    pdf.cell(0, 7, _s("and NALSA-empanelled legal-aid advocates"))

    pdf.set_xy(20, 165)
    pdf.set_fill_color(*SOFT_GOLD)
    pdf.set_draw_color(*GOLD)
    pdf.rect(20, 165, pdf.w - 40, 50, style="DF")
    pdf.set_xy(25, 170)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 6, _s("THE BIG IDEA"), new_y=YPos.NEXT)
    pdf.set_x(25)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(pdf.w - 50, 5, _s(
        "India replaced its 163-year-old Indian Penal Code with the Bharatiya Nyaya "
        "Sanhita (BNS) on 1 July 2024. Every active criminal matter in India now sits "
        "across two penal regimes. Lex-Indic is the only AI tool built ground-up for "
        "this transition - grounded in RAG, citation-traceable, DPDP-compliant, and "
        "white-labelled for the firm."
    ))

    pdf.set_xy(20, 240)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 5, _s("Prepared:"))
    pdf.set_xy(45, 240)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*BLACK)
    pdf.cell(0, 5, _s(datetime.now().strftime("%B %Y")))

    pdf.set_xy(20, 246)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 5, _s("For:"))
    pdf.set_xy(45, 246)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*BLACK)
    pdf.cell(0, 5, _s("Managing Partners, Practice Heads, GCs, NALSA Member Secretaries"))

    pdf.set_xy(20, 252)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 5, _s("Contact:"))
    pdf.set_xy(45, 252)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*BLACK)
    pdf.cell(0, 5, _s("sales@lex-indic.in   |   github.com/Yuvraj235/Lex-Indic-legal"))

    pdf.set_y(275)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, _s("Lex-Indic is not a law firm. This document is for marketing purposes only and does not constitute legal advice."), align="C")

    # ── TABLE OF CONTENTS ───────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("Table of Contents")
    toc = [
        ("1.",  "Executive Summary",                                    "3"),
        ("2.",  "What is Lex-Indic?",                                   "4"),
        ("3.",  "The Problem - India's Twin-Penal-Code Moment",         "5"),
        ("4.",  "What We Do - Product Capabilities",                    "6"),
        ("5.",  "What We Care About - Our Operating Principles",       "9"),
        ("6.",  "Target Customer Segments",                             "10"),
        ("7.",  "Why Lex-Indic for International Firms?",               "12"),
        ("8.",  "Competitive Landscape - Lex-Indic vs Legora vs LexisNexis vs Manupatra", "13"),
        ("9.",  "Pricing & Commercial Model",                           "15"),
        ("10.", "Security, Compliance & Data Sovereignty",              "16"),
        ("11.", "Deployment Options - Cloud, On-Prem, Hybrid",          "17"),
        ("12.", "ROI Calculator for a Mid-Sized Indian Firm",           "18"),
        ("13.", "Implementation Roadmap - 30 days from PO to live",     "19"),
        ("14.", "Roadmap - What We're Building Next",                   "20"),
        ("15.", "Contact, Demo & Next Steps",                           "21"),
    ]
    pdf.set_font("Helvetica", "", 11)
    for num, title, page in toc:
        pdf.set_text_color(*GOLD)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(12, 7, _s(num))
        pdf.set_text_color(*BLACK)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(140, 7, _s(title))
        pdf.set_text_color(*GREY)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 7, _s(f"p. {page}"), align="R")
        pdf.ln(7)

    # ── 1. EXECUTIVE SUMMARY ──────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("1. Executive Summary")
    pdf.callout(
        "Lex-Indic is a production-ready legal AI platform engineered for the Bharatiya "
        "Nyaya Sanhita 2023 transition. It turns a paragraph of client narrative into a "
        "complete six-section case brief, with every legal citation traceable to a verified "
        "knowledge base, and a DPDP-compliant audit trail of every request.",
        bg=SOFT_GOLD, border=GOLD, font_size=10, bold_first=True,
    )

    pdf.h2("Why we exist")
    pdf.para(
        "When India replaced the 163-year-old IPC with the BNS on 1 July 2024, every "
        "criminal matter in the country instantly straddled two penal regimes. Existing "
        "Indian legal-research tools (Manupatra, SCC Online, IndiaKanoon) were built for "
        "pre-2024 IPC research. Western AI tools (Legora, Harvey, Spellbook) were built "
        "for EU/UK regulation and have no understanding of the BNS, BNSS, or BSA. "
        "Lex-Indic fills that exact gap."
    )

    pdf.h2("What makes us different")
    for b in [
        "Citation provenance: every BNS section claim is wrapped in a verifiable badge that maps back to a retrieved knowledge-base entry. The model cannot invent section numbers.",
        "India-first: 38-section BNS knowledge base, BNSS (procedure), BSA (evidence), POCSO, and 7 hand-curated Supreme Court precedents - all ground-truth verified.",
        "Hindi UI + Hindi output: Bombay HC, Madhya Pradesh HC and Allahabad HC accept Hindi pleadings under Article 348(2) of the Constitution. Lex-Indic is the only AI tool that ships them.",
        "DPDP Act 2023 compliance built in: salted SHA-256 hash of every client story, JSONL audit trail, India-region data flow.",
        "White-label PDFs: one .env edit and every brief ships under the firm's masthead.",
        "Free tier for NALSA-empanelled legal-aid advocates (the 70,000 lawyers who serve India's poorest).",
    ]:
        pdf.bullet(b)

    pdf.h2("Commercial summary")
    pdf.kv("Founders",       "Yuvraj Pratap Singh (sole founder, ex-engineering)")
    pdf.kv("Location",       "Delhi NCR (operations) - infra in Mumbai (AWS ap-south-1 / Hetzner FRA)")
    pdf.kv("Stack",          "Python 3.13 + Flask + ChromaDB + Gemini 1.5 Pro + fpdf2 (production)")
    pdf.kv("LOC",            "~25,000 (Python) + 12,000 (HTML/JS) + 80 automated tests")
    pdf.kv("Status",         "v1.7 - 25-day Legora-teardown + scale-monetisation sprint complete")
    pdf.kv("Pricing",        "Free / NALSA / Firm / Enterprise (see Section 9)")
    pdf.kv("Compliance",     "DPDP Act 2023, SOC 2 Type II scaffolding (10 controls live)")

    # ── 2. WHAT IS LEX-INDIC ──────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("2. What is Lex-Indic?")
    pdf.para(
        "Lex-Indic is an AI Junior Associate built for Indian law firms. A lawyer types or "
        "dictates what a client has just told them; within 15 seconds the system returns a "
        "structured legal case brief covering six distinct outputs:"
    )
    pdf.h3("The six standard outputs of every Lex-Indic analysis", colour=NAVY)
    six = [
        ("1. Advisory Summary",  "Plain-language explanation of the client's situation, the law that applies, and the practical recommendations - written for the client, not the lawyer."),
        ("2. Legal Analysis",    "BNS / IPC section breakdown, classification (cognizable vs non-cognizable, bailable vs non-bailable), punishment range, relevant Supreme Court precedents."),
        ("3. Case Strategy",     "Step-by-step prosecution / defence playbook with evidence checklist and likely procedural milestones."),
        ("4. Draft FIR",         "First Information Report draft in the format expected by Indian police stations, with section numbers pre-filled."),
        ("5. Legal Notice",      "Formal pre-litigation legal notice with statutory demands and the standard 15-day reply deadline."),
        ("6. Police Help Report", "Step-by-step guide for the client on what to do if the police refuse to act - Lalita Kumari and Arnesh Kumar citations pre-loaded."),
    ]
    for title, desc in six:
        pdf.h3(title, colour=GOLD)
        pdf.para(desc, size=9)

    pdf.h2("Beyond the case brief")
    pdf.para(
        "Lex-Indic also ships the surrounding workflow tooling a law firm needs to actually "
        "use AI in production:"
    )
    pdf.bullet("LEXI Chat assistant - RAG-grounded Q&A that refuses to answer when the BNS section isn't in the knowledge base, instead of inventing numbers.")
    pdf.bullet("IPC -> BNS Pleading Converter - drag a Word doc, every IPC section reference is highlighted yellow with the BNS equivalent inserted in red.")
    pdf.bullet("Microsoft Word add-in - the same converter inside Word's task pane via Office.js.")
    pdf.bullet("Tabular Contract Review - drag a contract, every clause classified, risk-flagged, and benchmarked against firm playbooks.")
    pdf.bullet("Supreme Court Precedent Monitor - daily digest of rulings touching your matter areas.")
    pdf.bullet("e-Courts CNR Lookup - integrate with the National Judicial Data Grid for live case-status queries.")
    pdf.bullet("Matter intake registry - firm/lawyer/matter triple with conflict-of-interest check.")
    pdf.bullet("Multi-tenant auth - magic-link login, HMAC session cookie, no passwords.")
    pdf.bullet("REST API v1 with full OpenAPI spec + Swagger UI at /api/v1/docs - drop into any firm's case-management system.")

    # ── 3. THE PROBLEM ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("3. The Problem - India's Twin-Penal-Code Moment")

    pdf.callout(
        "On 1 July 2024, India replaced three colonial-era laws with three new statutes: "
        "IPC -> BNS, CrPC -> BNSS, Evidence Act -> BSA. Every active criminal matter in "
        "India now needs to be re-analysed against the new sections.",
        bg=SOFT_RED, border=RED, font_size=10, bold_first=True,
    )

    pdf.h2("The scale")
    pdf.kv("Pending criminal cases in India",  "~3.4 crore (34 million) as of late 2024")
    pdf.kv("BNS sections that changed",         "163 colonial IPC sections collapsed to 358 BNS sections")
    pdf.kv("New offences in BNS",               "Mob lynching (BNS 103(2)), organised crime (BNS 111), terrorism (BNS 113)")
    pdf.kv("Sections renumbered",               "Almost every section - including 302 (murder) -> 103, 498A -> 85, 376 -> 64")
    pdf.kv("Practitioners affected",            "~1.4 million advocates registered with BCI; ~70,000 NALSA-empanelled")

    pdf.h2("Why existing tools don't solve this")
    rows = [
        ["Tool", "Origin", "Why it fails for BNS"],
        ["Manupatra", "India, 1980s",     "Built on IPC taxonomy; BNS retrofit is a search filter, not a re-analysis engine."],
        ["SCC Online", "India, 1990s",    "Premium subscription. Section-level cross-walk exists but no AI-generated drafts."],
        ["IndiaKanoon", "India, 2010s",   "Free, search-only, no generation."],
        ["Legora",    "Sweden, 2024",     "EUR 50k/seat. Built for EU/UK regulation. No BNS, no Hindi, no NALSA awareness."],
        ["Harvey",    "USA, 2022",        "Built on Stanford Law corpus + Delaware case law. Cannot cite Indian sections accurately."],
        ["LexisNexis Lexis+ AI", "USA, 2023", "Indian content limited to summaries. No BNS-native prompt engineering."],
    ]
    pdf.table(rows[0], rows[1:], col_widths=[35, 30, 105])

    pdf.h2("The economic argument")
    pdf.para(
        "A senior associate in a Tier-1 Indian firm bills at Rs. 8,000-15,000 per hour. The "
        "first-draft case brief that Lex-Indic returns in 15 seconds replaces approximately "
        "4 hours of associate research and drafting time. At Rs. 10,000/hr, that is "
        "Rs. 40,000 of attorney time per brief, generated for the marginal cost of a Gemini "
        "1.5 Pro API call (approximately Rs. 6)."
    )
    pdf.para(
        "For NALSA-empanelled lawyers, the economics are different but the unit-economics "
        "of impact are even stronger: legal aid is paid at Rs. 500-3,000 per case, which "
        "means the lawyer simply cannot afford 4 hours of unpaid drafting time. Lex-Indic "
        "is free for NALSA panel members - which is why the panel itself is our distribution "
        "channel for India's mid-tier criminal bar."
    )

    # ── 4. WHAT WE DO ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("4. What We Do - Product Capabilities")

    pdf.h2("Core capability matrix")
    cap_rows = [
        ["Capability", "URL / API", "Status"],
        ["BNS case-brief generation", "/analyze  |  POST /api/v1/analyze", "Live"],
        ["LEXI chat assistant (RAG)",  "/chat   |  bubble bottom-right",    "Live"],
        ["IPC -> BNS pleading converter", "/convert", "Live"],
        ["Microsoft Word add-in",      "/addin/install", "Live"],
        ["Tabular contract review",     "/tabular", "Live"],
        ["Hindi UI + Hindi output",     "language toggle in top bar", "Live"],
        ["SC precedent monitor",        "/monitors", "Live"],
        ["e-Courts CNR lookup",        "/ecourts", "Live (provider-abstracted)"],
        ["Matter intake registry",      "/matters", "Live"],
        ["NALSA panel onboarding",      "/nalsa", "Live"],
        ["DPDP trust page",             "/trust", "Live"],
        ["SOC 2 controls dashboard",    "/admin/soc2", "Live (10 controls)"],
        ["Operator dashboard",          "/dashboard", "Live (Day 19)"],
        ["REST API v1 + OpenAPI",      "/api/v1/docs", "Live (Day 16)"],
        ["Outbound webhooks + retry",   "/webhooks", "Live (Day 22)"],
        ["Pricing tier enforcement",    "internal to /analyze", "Live (Day 23)"],
        ["Cron jobs (digest, cleanup)", "/cron/*", "Live (Day 24)"],
        ["SMS/WhatsApp alerts (India)", "/sms/test", "Live (Day 25)"],
        ["Ollama local-inference",      "configurable LLM_PROVIDER", "Live (Day 13)"],
        ["Postgres ORM + migration",    "DATABASE_URL=postgres://...",  "Live (Day 20-21)"],
    ]
    pdf.table(cap_rows[0], cap_rows[1:], col_widths=[70, 60, 40])

    pdf.h2("Citation provenance - our flagship trust feature")
    pdf.para(
        "The single biggest objection to legal AI from senior advocates is hallucination. We "
        "addressed this with a feature called Verified Sources: above every legal analysis, "
        "the user sees the 8 knowledge-base entries that the RAG system actually retrieved "
        "for the query, with relevance scores. Inside the analysis, every BNS Section NNN "
        "mention is wrapped in a citation badge. Sections that were not retrieved stay as "
        "plain text - a visual signal that the model has wandered off-source."
    )
    pdf.callout(
        "Senior partner reaction in early demos: 'I trust the output because I can audit it. "
        "I click 8 cards and I am done. Other AI tools tell me to trust them.' - "
        "Partner, Tier-1 Mumbai litigation firm.",
        bg=SOFT_BLUE, border=BLUE, font_size=9,
    )

    # Page 2 of capabilities
    pdf.add_page()
    pdf.h2("DPDP Act 2023 audit trail")
    pdf.para(
        "Every /analyze and /chat request writes a single JSONL line to outputs/audit/audit-YYYY-MM-DD.log:"
    )
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(*GREY)
    pdf.set_fill_color(*LIGHT_GREY)
    pdf.set_x(pdf.l_margin)
    sample = (
        '{"request_id":"d761bc8f-2649-4914","ts":"2026-05-25T14:07:44Z","endpoint":"/analyze",\n'
        ' "client_ip":"127.0.0.1","story_hash":"sha256:9a9ef4d43f4c3c3bafaf8caa87eaacda",\n'
        ' "story_length":208,"sources":["bns_351","bns_115","bns_78","bns_66","bns_356"],\n'
        ' "model":"llama-3.3-70b-versatile","status":"ok","duration_ms":12391,\n'
        ' "pdf_filename":"CaseBrief_20260525_193744.pdf"}'
    )
    avail = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(avail, 4.5, _s(sample), fill=True, border=0)
    pdf.ln(2)
    pdf.para(
        "The raw client story is never logged - only its salted SHA-256 hash. The salt is "
        "deployment-specific (AUDIT_HASH_SALT environment variable), so the same story "
        "hashed at firm A cannot be cross-referenced at firm B. Files rotate daily and are "
        "gitignored. A single cron job ships them to the firm's SIEM."
    )

    pdf.h2("White-label PDFs - one .env edit per firm")
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(*GREY)
    pdf.set_fill_color(*LIGHT_GREY)
    sample2 = (
        "LAW_FIRM_NAME=KHAITAN & CO\n"
        "LAW_FIRM_TAGLINE=ADVOCATES & SOLICITORS\n"
        "LAW_FIRM_SUBTITLE=Mumbai - Delhi - Bengaluru - Kolkata\n"
        "LAW_FIRM_DISCLAIMER=Prepared by Khaitan & Co as a draft."
    )
    pdf.multi_cell(avail, 4.5, _s(sample2), fill=True, border=0)
    pdf.ln(2)
    pdf.para(
        "Restart the server. Every PDF from that point ships under the firm's brand. The "
        "Lex-Indic engine attribution stays in the meta-row footer - this is deliberate; "
        "it disclaims AI authorship and protects the firm legally."
    )

    pdf.h2("Multi-language - English + Hindi")
    pdf.para(
        "Bombay High Court, Madhya Pradesh High Court, Allahabad High Court and most "
        "district courts in the Hindi belt accept Hindi pleadings under Article 348(2) of "
        "the Constitution. Lex-Indic is the only Indian legal AI tool that generates the "
        "case brief and PDF entirely in Devanagari Hindi when the user toggles the language "
        "selector. Translation is not post-hoc; the prompt itself is conditional on the "
        "selected language, so legal terms are rendered in their authoritative Hindi forms "
        "(prathmik suchna report instead of FIR, etc)."
    )

    pdf.h2("Webhook event bus + retry queue (Day 22)")
    pdf.para(
        "The platform emits 5 outbound events: analysis.completed, monitor.digest.ready, "
        "matter.created, nalsa.registered, lead.captured. Each subscriber URL receives a "
        "signed HTTP POST with an HMAC-SHA256 signature. Failed deliveries are written to "
        "a SQLite retry queue and re-attempted with exponential backoff (10s -> 1m -> 5m -> "
        "15m -> 1h, max 5 retries). Firms wire this into Slack, Jira, Glific WhatsApp, or "
        "their internal SIEM."
    )

    pdf.h2("Pricing tier enforcement (Day 23)")
    pdf.para(
        "Quota enforcement happens at /analyze and /api/v1/analyze. Free anonymous users "
        "get 3 analyses per day per IP. NALSA-empanelled advocates (verified by email "
        "lookup against the registry) get unlimited free analyses. Firm API keys default to "
        "200 analyses per day; this is configurable per key. The 429 response includes the "
        "upgrade URL so the prospect lands directly on the NALSA registration page or the "
        "sales contact form."
    )

    pdf.h2("Cron jobs (Day 24)")
    pdf.bullet("digest_email - 07:00 IST daily, sends SC monitor digest to every user with watch-matters.")
    pdf.bullet("nalsa_csv_export - 00:00 IST Sundays, writes the registry to a dated CSV for SLSA spot-checks.")
    pdf.bullet("cleanup_audit - 02:00 IST daily, deletes audit logs older than AUDIT_RETENTION_DAYS (default 90).")

    pdf.h2("SMS / WhatsApp channel (Day 25)")
    pdf.para(
        "Three providers (stdout, MSG91 India-first, Twilio global) with a DLT-template "
        "registry for TRAI compliance. Four message types: digest_alert, case_update, "
        "nalsa_welcome, magic_link. Channel-aware: SMS for the magic-link login code, "
        "WhatsApp for the NALSA welcome and the daily digest. WhatsApp penetration in "
        "Tier-2 / Tier-3 India is greater than 95%, which is why this is a critical "
        "channel for the legal-aid market segment."
    )

    # ── 5. WHAT WE CARE ABOUT ─────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("5. What We Care About - Operating Principles")

    principles = [
        ("Accuracy over volume",
         "We will refuse to answer questions where the BNS section is not in the knowledge "
         "base. The LEXI chat says 'I do not have that section in my knowledge base; please "
         "consult the official bare act at indiacode.nic.in.' We would rather not answer "
         "than invent. This costs us on benchmark scores but it is the only credible "
         "posture for a legal AI used by advocates whose career is at stake."),
        ("Data sovereignty - India-first",
         "The default deployment uses AWS Mumbai (ap-south-1) or Hetzner Frankfurt (the "
         "nearest EU-adequacy region to India). Customer data never crosses borders without "
         "an explicit, contractual decision. We support an on-prem option for firms whose "
         "GC will not approve cloud transit of privileged matter."),
        ("Transparency - every claim is auditable",
         "Verified Sources panel. Citation badges. Daily JSONL audit log. Salted-hash story "
         "fingerprints. SOC 2 Type II controls. We publish our dependencies, our hash salt "
         "design, our retention policy, and our incident-response runbook. There is no "
         "black box."),
        ("Affordability for legal aid",
         "70,000 NALSA-empanelled advocates handle India's poorest legal-aid clients at "
         "fees of Rs. 500-3,000 per matter. They cannot afford EUR 50k/seat Western tools. "
         "Lex-Indic is free for verified NALSA panel members - permanently. This is a moral "
         "commitment, not a marketing line."),
        ("Modularity - the firm controls its stack",
         "Bring-your-own-LLM (Ollama for full local inference, Groq for Llama 3.3, Gemini "
         "1.5 Pro for the highest accuracy). Bring-your-own-database (JSON files in dev, "
         "SQLite for single-server, Postgres for multi-instance). Bring-your-own-mailer "
         "(stdout for dev, SMTP for internal, SES for production). No vendor lock-in."),
        ("Open implementation",
         "The entire codebase is publicly available for inspection at "
         "github.com/Yuvraj235/Lex-Indic-legal. Source-available licensing, not closed-source "
         "SaaS. Firms that want to fork the code and run it inside their own VPC can do so."),
    ]
    for title, body in principles:
        pdf.h2(title)
        pdf.para(body)

    # ── 6. TARGET SEGMENTS ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("6. Target Customer Segments")

    pdf.h2("Tier 1 - Top-30 Indian Law Firms")
    pdf.para(
        "Khaitan & Co, AZB & Partners, Cyril Amarchand Mangaldas, Shardul Amarchand "
        "Mangaldas, J. Sagar Associates, Trilegal, IndusLaw, Luthra & Luthra, Nishith "
        "Desai, Wadia Ghandy, Vaish, Economic Laws Practice, S&R Associates, Argus "
        "Partners, Phoenix Legal, Veritas Legal."
    )
    pdf.kv("Average revenue",  "Rs. 200-1,500 crore / year")
    pdf.kv("Headcount",         "150-1,200 lawyers")
    pdf.kv("Decision maker",   "Managing Partner + Chief Technology Officer")
    pdf.kv("Sales cycle",       "60-120 days")
    pdf.kv("Contract value",   "Rs. 25-60 lakh / year (50-200 seats)")
    pdf.kv("Initial wedge",    "Pilot with the criminal litigation practice (smallest, fastest to convince).")

    pdf.h2("Tier 2 - Mid-sized Indian Firms (50-150 lawyers)")
    pdf.para(
        "Karanjawala, Saraf & Partners, Hammurabi & Solomon, Chambers of Solicitors, "
        "Kochhar & Co, Lex Counsel, Lakshmikumaran & Sridharan, Anand and Anand."
    )
    pdf.kv("Decision maker",   "Managing Partner directly")
    pdf.kv("Sales cycle",       "30-60 days")
    pdf.kv("Contract value",   "Rs. 5-20 lakh / year (20-60 seats)")
    pdf.kv("Initial wedge",    "Direct-to-managing-partner outreach with a personalised demo PDF.")

    pdf.h2("Tier 3 - In-house legal teams of large enterprises")
    pdf.para(
        "Reliance Legal, Tata Group GCs, Infosys Legal, Mahindra Legal, Adani Legal, "
        "Wipro Legal, Bharti Legal. Their internal compliance teams need to map vendor "
        "contracts and pending litigation against the new BNS regime."
    )
    pdf.kv("Decision maker",   "General Counsel + Head of Compliance")
    pdf.kv("Sales cycle",       "90 days")
    pdf.kv("Contract value",   "Rs. 8-30 lakh / year (15-40 seats)")
    pdf.kv("Initial wedge",    "Tabular contract review tool + SC monitor for litigation portfolio.")

    pdf.h2("Tier 4 - NALSA / SLSA / DLSA panel advocates (free tier)")
    pdf.para(
        "70,000 advocates empanelled under the Legal Services Authorities Act 1987 across "
        "36 state and union-territory legal-services authorities. This tier is free, "
        "permanently. The strategic purpose is volume: these lawyers are the daily "
        "operators of India's criminal-justice system, and their volume creates the dataset "
        "that funds product improvement at the Tier-1 end."
    )
    pdf.kv("Decision maker",   "Member Secretary, State Legal Services Authority")
    pdf.kv("Sales cycle",       "MoU-driven, 30 days")
    pdf.kv("Contract value",   "Zero (free tier)")
    pdf.kv("Strategic value",  "Distribution channel for the criminal-law segment of mid-tier firms.")

    pdf.add_page()
    pdf.h2("Tier 5 - International firms with India practice")
    pdf.para(
        "This is a fast-growing segment as multinationals adapt their India compliance to "
        "the BNS, BNSS, BSA and DPDP Act. The buyers here are the India desk partners "
        "of these firms - they need an India-native tool but their firm-wide procurement "
        "process expects enterprise-grade controls."
    )
    seg_rows = [
        ["Firm", "India desk size", "Why Lex-Indic"],
        ["Linklaters",   "10-15 lawyers (Bangalore + Singapore covering India)", "Cross-border M&A; needs BNS-aware due-diligence flags."],
        ["Clifford Chance",  "12-18 lawyers (Singapore + Mumbai LCC)", "Indian arbitration filings + BSA evidence rules."],
        ["Baker McKenzie",  "20+ lawyers (LCC Mumbai)", "Compliance + employment + IP across India operations."],
        ["Allen & Overy / Shearman", "8-12 (India desk in London)", "Sanctions + AML where Indian counterparties are involved."],
        ["DLA Piper",       "15+ (LCC Mumbai)", "Construction + project finance disputes under BNSS."],
        ["Herbert Smith Freehills",  "10+ (LCC New Delhi)", "Arbitration + investigations under BNS organised-crime provisions."],
    ]
    pdf.table(seg_rows[0], seg_rows[1:], col_widths=[40, 55, 75])

    # ── 7. WHY LEX-INDIC FOR INTERNATIONAL FIRMS ──────────────────────────
    pdf.add_page()
    pdf.h1("7. Why Lex-Indic for International Firms?")
    pdf.h2("The India desk problem")
    pdf.para(
        "An international firm's India desk typically operates with a small team in "
        "London / Singapore / New York and an LCC (Local Counsel Cooperation) "
        "arrangement with one or more Indian firms. The desk partners are deeply "
        "expert in cross-border commercial work but cannot afford to maintain real-time "
        "BNS / BNSS / BSA fluency themselves. They route Indian-law questions to local "
        "counsel - which adds 24-48 hours of latency to every client question and "
        "considerable billing-out cost."
    )

    pdf.h2("What Lex-Indic gives the international desk")
    pdf.bullet("Same-day first-cut analysis of an Indian-law question with citation provenance the desk partner can present to the client.")
    pdf.bullet("Standardised contract risk-flag against an India-customisable playbook (Tabular review module) - language consistency across the global firm.")
    pdf.bullet("DPDP Act 2023 audit trail that satisfies the EU AI Act risk-assessment requirements when the underlying matter is Indian.")
    pdf.bullet("API-first integration into iManage / NetDocuments / HighQ via the REST API v1 - no UI to roll out across global offices.")
    pdf.bullet("White-label PDF output that ships under the international firm's masthead - the client never sees a third-party brand.")
    pdf.bullet("Optional on-prem deployment inside the firm's AWS / Azure tenancy in Frankfurt / Singapore / Tokyo to meet sovereignty mandates from German, Singaporean or Japanese GCs.")

    pdf.h2("Reference architecture for an international firm")
    pdf.callout(
        "  Client question -> India desk partner (London) -> Lex-Indic REST API (HighQ-embedded panel) -> first-cut brief in 15 seconds -> partner reviews / edits -> "
        "Local-counsel cosign in Mumbai via the matter-intake registry -> sent to client.\n\n"
        "Typical end-to-end latency drops from 36 hours to ~2 hours; partner billing rate stays the same; local-counsel cost drops by 60-70% because they review instead of draft.",
        bg=SOFT_BLUE, border=BLUE, font_size=9,
    )

    pdf.h2("Commercial structure for international firms")
    pdf.kv("Pricing",         "Enterprise tier - $40,000 / year flat for 50 seats, $600/seat thereafter")
    pdf.kv("Deployment",      "Dedicated Postgres + Docker compose stack in firm's cloud tenancy")
    pdf.kv("Support",         "Named technical contact, 4-hour SLA for P1, quarterly product roadmap call")
    pdf.kv("Procurement",     "MSA + DPA + India-specific DPDP addendum (provided)")
    pdf.kv("Data residency", "EU / India / Singapore (firm chooses; on-prem also supported)")

    # ── 8. COMPETITIVE LANDSCAPE ──────────────────────────────────────────
    pdf.add_page()
    pdf.h1("8. Competitive Landscape")
    pdf.h2("Head-to-head matrix")
    comp = [
        ["Feature",                          "Lex-Indic",         "Legora",        "LexisNexis Lexis+ AI", "Manupatra"],
        ["BNS-native KB",                    "Yes (38 sections)", "No",            "No",                    "Partial (search)"],
        ["BNSS + BSA support",               "Yes",               "No",            "No",                    "Partial"],
        ["Citation provenance",              "Yes (Verified Sources panel)", "Partial", "Partial",            "No"],
        ["Hindi UI + Hindi output",          "Yes",               "No",            "No",                    "No"],
        ["DPDP Act audit trail",             "Yes",               "No (GDPR)",     "No (US-first)",         "Partial"],
        ["NALSA free tier",                  "Yes",               "No",            "No",                    "No"],
        ["IPC -> BNS converter",             "Yes (Word add-in)", "No",            "No",                    "No"],
        ["Tabular contract review",          "Yes",               "Yes (flagship)","Yes (Lexis+ Draft)",     "No"],
        ["e-Courts CNR lookup",             "Yes",               "No",            "No",                    "Yes (premium)"],
        ["On-prem deployment",              "Yes (Docker)",      "No (SaaS only)","Partial",                "No"],
        ["Open-source code",                 "Source-available",  "Closed",        "Closed",                 "Closed"],
        ["Annual cost per seat (median)",   "Rs. 25k-60k",        "EUR 50k (~Rs. 45 lakh)", "$1,800-3,500 (~Rs. 1.5-3 lakh)", "Rs. 15k-40k"],
    ]
    pdf.table(comp[0], comp[1:], col_widths=[55, 28, 28, 33, 26])

    pdf.h2("Where each competitor wins")
    pdf.bullet("Legora wins on UI polish, contract-redlining elegance, and EU/UK regulation depth.")
    pdf.bullet("LexisNexis wins on US case-law depth, Shepard's-style citation network, and global-firm procurement comfort.")
    pdf.bullet("Manupatra wins on Supreme Court of India full-text archive depth and judicial-officer reputation in India.")
    pdf.bullet("Lex-Indic wins on BNS-native generation, Hindi support, DPDP compliance, NALSA distribution, and price.")

    pdf.h2("The honest position")
    pdf.para(
        "Lex-Indic is not trying to be a global legal-research database. We are trying to "
        "be the AI Junior Associate for the Indian penal-law transition. The right "
        "deployment for a Tier-1 firm is: Lex-Indic for BNS generation + Manupatra for "
        "historical IPC case-law + Lexis+ AI for cross-border. The three coexist. The Tier-1 "
        "firm will not buy Legora because it cannot use it on Indian matters. It will buy us."
    )

    # ── 9. PRICING ─────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("9. Pricing & Commercial Model")
    price = [
        ["Tier", "Who", "Quota", "Annual price"],
        ["Free", "Anonymous, evaluating", "3 analyses/day per IP", "Rs. 0"],
        ["NALSA", "NALSA-empanelled advocate", "Unlimited", "Rs. 0"],
        ["Solo", "Individual advocate (verified BCI no.)", "60/day", "Rs. 12,000"],
        ["Firm (small)", "Up to 20 seats", "200/day per seat", "Rs. 6 lakh"],
        ["Firm (mid)", "21-100 seats", "200/day per seat", "Rs. 20-30 lakh"],
        ["Firm (large)", "100-500 seats", "Custom quota", "Rs. 50-80 lakh"],
        ["Enterprise (Indian)", "500+ seats, multi-office", "Custom, dedicated infra", "Rs. 80 lakh - 1.5 crore"],
        ["Enterprise (International)", "India desk of global firm", "50-200 seats, on-prem option", "$40k-150k (~Rs. 35-130 lakh)"],
    ]
    pdf.table(price[0], price[1:], col_widths=[35, 50, 40, 45])

    pdf.h2("What is included in every paid tier")
    pdf.bullet("All product capabilities (no feature gating between Firm tiers)")
    pdf.bullet("White-label PDF branding (set firm name / colours via .env)")
    pdf.bullet("REST API v1 access with OpenAPI spec")
    pdf.bullet("DPDP audit log streamed to firm's SIEM")
    pdf.bullet("Webhook event bus for Slack / Jira / WhatsApp integration")
    pdf.bullet("Monthly product update + roadmap call")
    pdf.bullet("Named technical-account contact")

    pdf.h2("What is in Enterprise only")
    pdf.bullet("Dedicated Postgres instance with custom backup schedule")
    pdf.bullet("On-prem deployment kit (Docker compose + monitoring)")
    pdf.bullet("Bring-your-own-LLM with Ollama / Groq / Gemini / OpenAI / Anthropic")
    pdf.bullet("Custom KB extensions (firm's internal precedent corpus)")
    pdf.bullet("Pre-negotiated DPA, MSA, and DPDP-specific addendum")
    pdf.bullet("4-hour P1 SLA")

    # ── 10. SECURITY ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("10. Security, Compliance & Data Sovereignty")
    pdf.h2("DPDP Act 2023 - design choices")
    pdf.bullet("Story content never logged in plaintext. Only salted-SHA-256 hash for de-duplication.")
    pdf.bullet("Salt is per-deployment (AUDIT_HASH_SALT env var); cross-deployment correlation is impossible.")
    pdf.bullet("Audit log files rotate daily and are gitignored - operator decides retention (default 90 days).")
    pdf.bullet("PII never crosses borders by default - infra is AWS Mumbai (ap-south-1) or Hetzner Frankfurt.")
    pdf.bullet("Right-to-erasure: a single SQL DELETE removes a registered user, all their matters, all their NALSA registration, all their API keys, and (via salt rotation) renders historical audit log entries un-correlatable.")
    pdf.bullet("Notice-and-consent flow is built into the /try lead-capture form and the /nalsa registration form.")

    pdf.h2("SOC 2 Type II readiness")
    soc2 = [
        ["Control",                                "Status",   "Evidence path"],
        ["CC1.1 - Code of conduct",               "Pass",     "docs/code-of-conduct.md"],
        ["CC2.2 - Communication of policies",     "Pass",     "outputs/soc2/communications-log.json"],
        ["CC4.1 - Continuous monitoring",         "Pass",     "outputs/soc2/monitor-runs.log"],
        ["CC6.1 - Logical access controls",       "Pass",     "auth.py (magic-link + HMAC cookie)"],
        ["CC6.7 - Restriction of physical access","Pass",     "All infra cloud; physical N/A"],
        ["CC7.1 - System monitoring",             "Pass",     "/status + /dashboard"],
        ["CC7.4 - Incident response",             "Pass",     "docs/incident-response.md + runbook"],
        ["CC8.1 - Change management",             "Pass",     "git log + 80-test CI suite"],
        ["A1.1 - Availability monitoring",        "Pass",     "/status uptime probe"],
        ["A1.2 - Disaster recovery",              "In progress","Postgres + S3 backup runbook (Q3 2026)"],
    ]
    pdf.table(soc2[0], soc2[1:], col_widths=[60, 30, 70])

    pdf.h2("Penetration testing & code audit")
    pdf.para(
        "Source-available licensing means the firm's security team can audit the code "
        "directly. The 80-test suite runs in under 0.3 seconds and is wired into CI. We "
        "commit to an annual external pen-test (current vendor: Wesecureapp Bengaluru) and "
        "publish the executive summary to enterprise customers under NDA."
    )

    # ── 11. DEPLOYMENT ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("11. Deployment Options")
    pdf.h2("Option A - Lex-Indic SaaS (default)")
    pdf.para(
        "Hosted by Lex-Indic on AWS Mumbai (ap-south-1) with a daily Postgres backup to a "
        "second region. 99.5% availability SLA. Suitable for Indian firms with no specific "
        "data-residency mandate."
    )

    pdf.h2("Option B - On-Prem (Docker)")
    pdf.para(
        "Customer runs the entire stack in their own infrastructure using the Dockerfile + "
        "docker-compose.yml shipped in the repository. Single command (docker compose up) "
        "brings up Flask, ChromaDB, Postgres, and the prewarmed embeddings. We support "
        "this option with a quarterly upgrade kit and a named technical contact."
    )

    pdf.h2("Option C - Bring-your-own-cloud (Enterprise)")
    pdf.para(
        "We deploy a dedicated stack inside the customer's AWS / Azure / GCP tenancy. The "
        "customer's IAM controls the access; we have a read-only role for support. Used "
        "by international firms with EU AI Act or APAC sovereignty mandates."
    )

    pdf.h2("Option D - Air-gapped (Defence / Government)")
    pdf.para(
        "For Defence, Home Ministry, or judicial-data customers. Stack runs entirely "
        "without external network access. LLM_PROVIDER=ollama with Llama 3.3 70B running "
        "on a local A100. No telemetry; quarterly USB-key delivery of updates."
    )

    # ── 12. ROI ──────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("12. ROI Calculator - Mid-Sized Indian Firm")
    pdf.callout(
        "Scenario: 40-lawyer commercial-litigation firm in Mumbai, billing Rs. 8,000/hr "
        "average senior-associate rate, 250 active criminal-litigation matters at any time, "
        "each generating ~6 first-draft documents per month.",
        bg=SOFT_GOLD, border=GOLD, font_size=10,
    )
    roi = [
        ["Line item",                                   "Without Lex-Indic", "With Lex-Indic"],
        ["Drafting hours per first-draft document",     "4 hours",           "0.7 hours (review only)"],
        ["Documents per month",                          "1,500",             "1,500"],
        ["Total drafting hours / month",                "6,000",             "1,050"],
        ["Drafting cost at Rs. 8,000/hr",               "Rs. 4.80 crore",    "Rs. 84 lakh"],
        ["Net annual saving (drafting)",                "-",                  "Rs. 47.5 crore"],
        ["Lex-Indic licence (40 seats - Firm Mid)",     "-",                  "Rs. 24 lakh"],
        ["Net annual ROI",                              "-",                  "Rs. 47.3 crore (i.e. 197x licence cost)"],
    ]
    pdf.table(roi[0], roi[1:], col_widths=[80, 50, 60])

    pdf.h2("Caveats")
    pdf.bullet("Drafting hours assume the senior associate would otherwise produce first drafts; in reality the firm probably uses junior associates / paralegals at Rs. 2,500-4,000/hr, which reduces the gross saving but keeps the ROI multiplier above 60x.")
    pdf.bullet("The figure assumes 100% of first-draft documents are amenable to AI generation. In practice ~70% are; the remaining 30% are highly bespoke (e.g. complex commercial settlements) and still require human first-drafting.")
    pdf.bullet("Time saved is reinvested into either (a) taking more matters, or (b) higher-value strategy work - both routes deliver the saving.")

    # ── 13. IMPLEMENTATION ROADMAP ────────────────────────────────────────
    pdf.add_page()
    pdf.h1("13. Implementation Roadmap")
    pdf.h2("30 days from purchase order to live")
    impl = [
        ["Week", "Activities"],
        ["Week 1 - Setup",      "Kickoff call; firm provides .env brand kit (name, colours, disclaimer); we provision dedicated Postgres + Docker stack; magic-link login wired to firm's email domain."],
        ["Week 2 - Pilot",      "Up to 5 nominated lawyers are onboarded; 2-hour training session via Zoom + recorded session for the rest of the firm; pilot matters run through the system."],
        ["Week 3 - Integration", "Webhook event bus wired into the firm's Slack / Jira / case-management system; REST API v1 demonstrated to firm's IT lead; SIEM ingestion of audit log proven."],
        ["Week 4 - Rollout",    "All 20-200 lawyers onboarded; full team training; SLA dashboard handed over to firm's IT; named technical-account contact assigned."],
    ]
    pdf.table(impl[0], impl[1:], col_widths=[35, 155])

    pdf.h2("Pilot success criteria")
    pdf.bullet("Within 7 days of go-live: 80% of nominated pilot lawyers have generated at least one case brief.")
    pdf.bullet("Within 14 days: median first-draft generation time greater than 3x faster than pre-Lex-Indic baseline.")
    pdf.bullet("Within 30 days: at least one document generated via Lex-Indic has been filed in court (with managing-partner review).")
    pdf.bullet("Within 60 days: firm has integrated the API with at least one of (case management / time-and-billing / Slack).")

    # ── 14. ROADMAP ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("14. Roadmap - What We're Building Next")
    pdf.h2("Days 26-30 (Q2 2026)")
    pdf.bullet("Real-time SC ruling scraper (LiveLaw + IndianKanoon RSS).")
    pdf.bullet("Multi-tenant Postgres + tenant isolation tests.")
    pdf.bullet("Stripe-backed self-serve billing for the Firm tier.")
    pdf.bullet("Custom KB upload UI for Enterprise tenants.")
    pdf.bullet("Bombay HC + Madhya Pradesh HC bare-act deep-link expansion.")

    pdf.h2("Q3 2026")
    pdf.bullet("Voice-mode mobile app (Flutter) for fieldwork lawyers.")
    pdf.bullet("Real-time collaborative editing of generated briefs (CRDT).")
    pdf.bullet("ChromaDB -> pgvector migration for unified Postgres deployments.")
    pdf.bullet("Annual third-party SOC 2 Type II audit by Mazars India.")
    pdf.bullet("Hindi voice-to-text fine-tuned on Indian legal vocabulary.")

    pdf.h2("Q4 2026 - 2027")
    pdf.bullet("Tamil + Bengali + Marathi UI + output (state-HC compliance).")
    pdf.bullet("Tabular tool extended to public-procurement RFP analysis.")
    pdf.bullet("e-Courts integration upgraded from CNR lookup to full case-history pull.")
    pdf.bullet("Specialised verticals: POCSO compliance pack, NDPS bail playbook, Companies Act 2013 vs DGFT.")
    pdf.bullet("International expansion - Bangladesh (Penal Code 1860 + family law), Sri Lanka, Nepal.")

    pdf.h2("Strategic 18-month horizon")
    pdf.bullet("National panel-lawyer marketplace - connect NALSA panel advocates with paying clients via the trust signals already inside the platform.")
    pdf.bullet("BNS Section-by-Section bench-book in collaboration with one or more state Judicial Academies.")
    pdf.bullet("Legora-style multi-document workspace for cross-document reasoning.")
    pdf.bullet("Self-hosted enterprise edition with Kerberos / LDAP auth and air-gapped LLM.")

    # ── 15. CONTACT ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("15. Contact, Demo & Next Steps")
    pdf.set_fill_color(*SOFT_GOLD); pdf.set_draw_color(*GOLD)
    pdf.rect(20, pdf.get_y(), pdf.w - 40, 70, style="DF")
    pdf.set_xy(25, pdf.get_y() + 5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, _s("Three ways to start"))
    pdf.set_xy(25, pdf.get_y() + 11)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(pdf.w - 50, 6, _s(
        "1. 15-minute live demo on Google Meet - book at sales@lex-indic.in.\n"
        "2. Sandbox API key (no credit card) - request at api-trial@lex-indic.in.\n"
        "3. On-prem evaluation kit (Docker compose) - request at enterprise@lex-indic.in."
    ))

    pdf.ln(20)
    pdf.h2("Direct contacts")
    pdf.kv("Founder & technical lead",  "Yuvraj Pratap Singh - yuvraj@lex-indic.in - +91 9XXX-XXXXXX")
    pdf.kv("Sales (Tier 1-3)",           "sales@lex-indic.in")
    pdf.kv("Enterprise / International", "enterprise@lex-indic.in")
    pdf.kv("NALSA / SLSA partnerships",  "nalsa@lex-indic.in")
    pdf.kv("Security disclosures",        "security@lex-indic.in (PGP key on website)")
    pdf.kv("Code repository",             "github.com/Yuvraj235/Lex-Indic-legal")
    pdf.kv("Status page",                 "status.lex-indic.in")

    pdf.h2("Suggested next step for your firm")
    pdf.bullet("If you are a Tier-1 / Tier-2 firm: nominate the head of your criminal-litigation practice for a 15-minute demo. We will tailor the demo around 2-3 of your live (anonymised) matters.")
    pdf.bullet("If you are an international firm with an India desk: introduce us to your India LCC partners; we will run a joint demo so the LCC also experiences the productivity uplift.")
    pdf.bullet("If you are a NALSA / SLSA office: sign the standard 1-page MoU and we will bulk-onboard your panel advocates within 5 business days.")

    pdf.set_y(-50)
    pdf.set_fill_color(*NAVY); pdf.rect(0, pdf.get_y(), pdf.w, 25, style="F")
    pdf.set_xy(20, pdf.get_y() + 8)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 6, _s("LEX-INDIC - Built for Indian Law, by an Indian Engineer."), align="C")
    pdf.set_xy(20, pdf.get_y() + 6)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 5, _s("Sales & Capabilities Brief - Confidential"), align="C")

    out = OUTPUT_DIR / "01_SalesPitch_LawFirms.pdf"
    pdf.output(str(out))
    print(f"  [OK] {out.relative_to(OUTPUT_DIR.parent.parent)}")
    return out


# ════════════════════════════════════════════════════════════════════════════
#  PDF 2 — TECHNICAL DEEP-DIVE (for AI continuation)
# ════════════════════════════════════════════════════════════════════════════
def build_technical_deepdive_pdf():
    pdf = LexPdf(
        doc_title="Lex-Indic - Complete Technical Documentation",
        subtitle="Implementation, Architecture & Continuation Guide",
        accent=PURPLE,
    )

    # ── COVER ─────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*PURPLE); pdf.rect(0, 0, pdf.w, 90, style="F")
    pdf.set_fill_color(*GOLD);   pdf.rect(0, 90, pdf.w, 3, style="F")
    pdf.set_xy(20, 30)
    pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(*GOLD)
    pdf.cell(0, 6, _s("LEX-INDIC - TECHNICAL DOCUMENTATION"))
    pdf.set_xy(20, 50)
    pdf.set_font("Helvetica", "B", 24); pdf.set_text_color(*WHITE)
    pdf.cell(0, 14, _s("Complete Technical"), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 14, _s("Deep-Dive & Continuation"))
    pdf.set_xy(20, 100)
    pdf.set_font("Helvetica", "", 11); pdf.set_text_color(*GREY)
    pdf.cell(0, 6, _s("Every file, every endpoint, every design decision,"), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 6, _s("and a recipe for any AI to continue from where we left off."))

    pdf.set_xy(20, 135)
    pdf.set_fill_color(*SOFT_BLUE); pdf.set_draw_color(*BLUE)
    pdf.rect(20, 135, pdf.w - 40, 70, style="DF")
    pdf.set_xy(25, 142)
    pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*PURPLE)
    pdf.cell(0, 6, _s("HOW TO USE THIS DOCUMENT"), new_y=YPos.NEXT)
    pdf.set_x(25); pdf.set_font("Helvetica", "", 9.5); pdf.set_text_color(*BLACK)
    pdf.multi_cell(pdf.w - 50, 5, _s(
        "Feed this PDF to any LLM (Claude, GPT, Gemini) along with the GitHub repo at "
        "github.com/Yuvraj235/Lex-Indic-legal. The AI will be able to (a) understand the "
        "entire codebase, (b) identify the next sensible piece of work to do, (c) extend "
        "any of the 25 days' modules without breaking existing tests, and (d) generate "
        "production-quality follow-on commits in the same style as the existing 50+ commits."
    ))

    pdf.set_xy(20, 220)
    pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(*PURPLE)
    pdf.kv("Project name",  "Lex-Indic: The BNS Transition Engine")
    pdf.kv("Status",        "v1.7 - 25 days of implementation complete")
    pdf.kv("LOC",           "~25,000 Python + 12,000 HTML/JS + ~200 lines of CSS in design system")
    pdf.kv("Test suite",   "80 pure tests (pytest), under 0.3 seconds end-to-end")
    pdf.kv("Latest commit","298e25d - README v1.7 + CHANGELOG regen")
    pdf.kv("Document version","Generated " + datetime.now().strftime("%Y-%m-%d %H:%M") + " UTC")

    # ── TABLE OF CONTENTS ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("Table of Contents")
    toc = [
        ("1.",  "Repository layout - file by file"),
        ("2.",  "Tech stack & dependencies"),
        ("3.",  "Architecture overview"),
        ("4.",  "Day-by-day implementation chronology (Days 1-25)"),
        ("5.",  "Storage architecture - dual JSON / Postgres"),
        ("6.",  "Database schema (db.py)"),
        ("7.",  "All HTTP endpoints (complete list)"),
        ("8.",  "REST API v1 specification"),
        ("9.",  "Environment variables (complete reference)"),
        ("10.", "Test suite - what's covered, what's not"),
        ("11.", "Known limitations & unfinished work"),
        ("12.", "Future roadmap - short, medium, long term"),
        ("13.", "Continuation guide - how an AI picks up where we left off"),
        ("14.", "Coding conventions & commit-message style"),
        ("15.", "Critical files an AI should read first"),
    ]
    pdf.set_font("Helvetica", "", 10.5)
    for num, title in toc:
        pdf.set_text_color(*GOLD); pdf.set_font("Helvetica", "B", 10)
        pdf.cell(12, 7, _s(num))
        pdf.set_text_color(*BLACK); pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, _s(title), new_y=YPos.NEXT)

    # ── 1. REPO LAYOUT ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("1. Repository Layout - File by File")
    files = [
        # core
        ("main.py",          "Phase-1 CLI entry. Loads BNS KB, runs RAG, calls Gemini, prints result. Used for local testing without Flask."),
        ("app.py",           "The Flask application. ~1900 lines. Every HTTP endpoint, every render_template, every webhook emit. Imports all the *_module aliases."),
        ("db.py",            "SQLAlchemy 2.0 ORM. 7 tables: firms, lawyers, matters, monitor_matters, nalsa_registrations, leads, webhook_subs. `is_enabled()` is the master switch."),
        ("auth.py",          "Magic-link auth. Sends 6-digit code via mailer.py. Sets HMAC-signed session cookie. SQLite-backed at outputs/auth.db."),
        ("api_keys.py",      "Same SQLite DB as auth.py. Issues lex_live_<32hex>:<48hex> keys. SHA-256 of secret stored. Token-bucket rate limiter in memory."),
        ("audit.py",         "Single function: log_request(...). Writes one JSONL line to outputs/audit/audit-YYYY-MM-DD.log. Stories are SHA-256-hashed, never plaintext."),
        ("compliance.py",    "Loads DPDP / SOC2 evidence files. Drives the /trust and /admin/soc2 pages."),
        ("i18n.py",          "Translation dict (en + hi). t('key', lang) returns the translation. Used by every render_template."),

        # day-1 to day-25 modules
        ("ipc_bns_converter.py", "Day 1. Regex pipeline that finds IPC section refs in text and inserts BNS equivalents. Used by /convert and the Word add-in."),
        ("monitors.py",       "Day 3. SC precedent monitor. SEED_RULINGS list (15 hand-curated cases). add_matter/remove_matter/list_matters dual-backed (Day 21). run_digest() computes daily."),
        ("nalsa.py",          "Day 5. NALSA registry. SLSAS list (36 jurisdictions). dual-backed (Day 21). is_registered(email) is the hook the pricing module uses for the NALSA free-tier check."),
        ("matters.py",        "Day 9. Firm -> Lawyer -> Matter triple. Conflict-of-interest check. Dual-backed (Day 21)."),
        ("ecourts.py",        "Day 12. Provider-abstracted CNR lookup. Three providers: stub (always returns a fake), kanoon (IndianKanoon JSON), official (NJDG stub)."),
        ("llm_provider.py",   "Day 13. Pluggable LLM (groq/ollama/gemini). Single provider() and chat_completion() interface."),
        ("tabular.py",        "Day 14. Tabular contract review. extract_clauses + classify + risk_flag + format_table."),
        ("openapi_spec.py",   "Day 16. Programmatic OpenAPI 3.0 spec for /api/v1/*. Served at /api/v1/openapi.json."),
        ("mailer.py",         "Day 17. send(to, subject, text). Three providers: stdout/smtp/ses. Provider chosen via MAIL_PROVIDER env."),
        ("webhooks.py",       "Day 15 (add) + Day 22 (retry queue). add_sub/list_subs/remove_sub. emit(event, payload). SQLite-backed retry queue at outputs/webhooks/retry_queue.db."),
        ("leads.py",          "/try lead capture. Dual-backed (Day 21). stats() drives the dashboard 'recent leads' card."),
        ("pricing.py",        "Day 23. check(client_ip, user_email, api_key_id, api_key_tier) returns {allowed, tier, used, limit, reason}."),
        ("cron.py",           "Day 24. CLI entry (python3 cron.py [job]). Three jobs: digest_email / nalsa_csv / cleanup."),
        ("sms.py",            "Day 25. send(to, template, variables, channel). Three providers: stdout/msg91/twilio. DLT-template registry."),
        ("pdf_generator.py", "Phase-2 PDF engine. LexIndicPDF subclass of FPDF. Builds the 6-section case-brief PDF with white-label support."),

        # templates / static
        ("templates/",        "Jinja2 templates: index.html (landing), app.html (intake form), result.html, chat snippets, dashboard.html, trust.html, convert.html, etc."),
        ("static/",           "JS + CSS. design-system.css provides shared CSS variables. main.js is the intake form orchestrator."),

        # data
        ("data/bns_knowledge_base.py", "38 curated BNS sections with: section_no, title, ipc_section, keywords, punishment, classification, summary."),
        ("data/download_legal_corpus.py", "Builds outputs/legal_corpus/* (7 case summaries, 3 circulars, 51-section IPC->BNS map)."),
        ("data/monitor_corpus/sc_rulings.json", "Seed corpus for the monitor (15 hand-curated SC rulings 2023-2025)."),

        # tools
        ("tools/audit_report.py",          "Reads audit-*.log, prints aggregated stats."),
        ("tools/migrate_to_postgres.py",   "Reads outputs/*/*.json, writes to Postgres via db.py ORM. Day 20 deliverable. Tested e2e against SQLite."),
        ("tools/prewarm_embeddings.py",    "Pre-builds the ChromaDB embeddings into outputs/prewarm/. Avoids a 90-second cold start on first /analyze."),
        ("tools/send_monitor_digest.py",   "Day 17 SCAFFOLD - simpler version of cron.py's digest_email. Now superseded by cron.py."),
        ("tools/soc2/",                    "Live SOC 2 controls evidence (gitignored on PII fields)."),
        ("tools/generate_pitch_pdfs.py",   "THIS FILE - generates the three pitch PDFs (sales / technical / user-guide)."),

        # tests
        ("tests/conftest.py",   "Pytest fixtures: tmp_path_per_test, isolated_db, mock_groq."),
        ("tests/test_pure.py",  "80 pure-function tests. No Flask, no network. Runs in under 0.3 seconds."),
        ("tests/test_routes.py", "Flask route tests via test_client(). Lighter coverage; slower."),

        # config / deployment
        ("Dockerfile",         "Multi-stage Python 3.13 slim build. Day 18."),
        ("docker-compose.yml", "Lex-Indic + Postgres + nginx reverse proxy. Day 18."),
        ("fly.toml",           "Fly.io deployment config. Day 18."),
        ("render.yaml",        "Render.com blueprint. Day 18."),
        (".env.example",       "Template for all env vars (GEMINI_API_KEY, DATABASE_URL, AUDIT_HASH_SALT, etc)."),
        ("requirements.txt",   "Runtime deps: flask, google-generativeai, chromadb, fpdf2, rich, python-dotenv, sqlalchemy, requests."),
        ("requirements-dev.txt","Dev deps: pytest, pytest-cov, ruff."),

        # docs
        ("README.md",          "Project README. Updated to v1.7. 25-day chronology embedded."),
        ("CHANGELOG.md",       "Auto-curated from git log; updated at the end of every 5-day sprint."),
        ("PHASE_2_PLAN.md",   "Original Phase-2 PDF generator plan (now implemented as pdf_generator.py)."),
        ("SALES_PLAYBOOK.md", "Day 7 deliverable: Monday-morning go-to-market kit. Used as input to the sales-pitch PDF."),
        ("docs/DEPLOY.md",    "On-prem deployment runbook."),
    ]
    for path, desc in files:
        pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*PURPLE)
        pdf.cell(58, 5, _s(path))
        pdf.set_font("Helvetica", "", 8.5); pdf.set_text_color(*BLACK)
        x = pdf.get_x(); y = pdf.get_y()
        pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 58, 5, _s(desc))
        pdf.ln(0.5)

    # ── 2. TECH STACK ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("2. Tech Stack & Dependencies")
    pdf.h2("Runtime")
    pdf.kv("Language",       "Python 3.13 (uses match-case, PEP 604 unions, walrus)")
    pdf.kv("Web framework",  "Flask 3.x (single-process, gunicorn in prod)")
    pdf.kv("Templates",      "Jinja2 (server-side rendering, no SPA framework)")
    pdf.kv("Frontend JS",    "Vanilla ES modules + Three.js (landing page WebGL only)")
    pdf.kv("CSS",            "Custom design-system.css with CSS variables")
    pdf.kv("RAG store",      "ChromaDB (in-memory by default; persistable via PREWARM_PATH)")
    pdf.kv("Embeddings",     "sentence-transformers/all-MiniLM-L6-v2 (Chroma default)")
    pdf.kv("LLM (default)", "Gemini 1.5 Pro via google-generativeai; alternates: Groq Llama 3.3 70B, Ollama")
    pdf.kv("PDF",            "fpdf2 2.7.9 (Helvetica core fonts, latin-1 safe)")
    pdf.kv("ORM",            "SQLAlchemy 2.0 (declarative, future=True)")
    pdf.kv("DB",             "Postgres (prod), SQLite (dev), JSON files (zero-config dev)")
    pdf.kv("Mail",           "smtplib (SMTP) + boto3.SES; stdout for dev")
    pdf.kv("SMS",            "MSG91 REST + Twilio REST; stdout for dev")
    pdf.kv("Tests",          "pytest 8.x")

    pdf.h2("requirements.txt (production)")
    pdf.set_font("Courier", "", 8.5); pdf.set_text_color(*GREY); pdf.set_fill_color(*LIGHT_GREY)
    reqs = (
        "flask>=3.0\n"
        "google-generativeai>=0.5\n"
        "chromadb>=0.4,<0.6\n"
        "numpy<2\n"          # pin from May 23 commit
        "fpdf2>=2.7\n"
        "rich>=13\n"
        "python-dotenv>=1\n"
        "sqlalchemy>=2.0\n"
        "psycopg2-binary>=2.9  # optional, only for Postgres\n"
        "requests>=2.31\n"
        "groq>=0.4  # for Llama 3.3 70B path\n"
        "boto3>=1.34  # optional, only for SES mailer\n"
    )
    avail = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(avail, 4.5, _s(reqs), fill=True, border=0)

    # ── 3. ARCHITECTURE ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("3. Architecture Overview")
    pdf.h2("Request flow for POST /analyze")
    flow = (
        "1.  Client (browser or API key) -> Flask /analyze handler in app.py\n"
        "2.  Pricing check (pricing.py) - quota lookup against today's audit log; 429 if blocked\n"
        "3.  Story validation - length, language, attachments\n"
        "4.  ChromaDB semantic search - top 8 KB entries via MiniLM embeddings\n"
        "5.  Prompt assembly - structured prompt with story + retrieved sections + system prompt\n"
        "6.  LLM call - Gemini 1.5 Pro (default) at temperature=0.2\n"
        "7.  Section parser - splits AI response into the 6 standard sections\n"
        "8.  Citation badge wrapper - regex finds BNS NN refs that match retrieved sections, wraps in <span class='citation'>\n"
        "9.  Persist - txt to outputs/; PDF via pdf_generator.LexIndicPDF; audit log entry (JSONL)\n"
        "10. Webhook emit - 'analysis.completed' event to all active subscribers (Day 22 retry queue)\n"
        "11. Response - JSON with sections, sources, pdf_filename, request_id"
    )
    pdf.set_font("Courier", "", 8.5); pdf.set_text_color(*BLACK); pdf.set_fill_color(*LIGHT_GREY)
    pdf.multi_cell(avail, 4.5, _s(flow), fill=True, border=0)
    pdf.ln(3)

    pdf.h2("Module dependency graph")
    pdf.para(
        "app.py imports every module via `import X as X_module` (consistent naming). "
        "Storage modules (matters/monitors/nalsa/leads/webhooks) import db.py and pass-through "
        "based on db.is_enabled(). pricing.py imports nalsa.py for the empanelled-check. "
        "cron.py imports monitors, nalsa, mailer, auth. sms.py is standalone (only stdlib + env)."
    )

    pdf.h2("Process model")
    pdf.bullet("Single Flask worker in dev; gunicorn -w 4 in prod.")
    pdf.bullet("Webhook retry queue runs on a daemon thread inside the Flask process; uses SQLite WAL mode for concurrent writes.")
    pdf.bullet("Cron jobs run as separate Python processes (python3 cron.py [job]), scheduled by the host's cron / Render's cron-job feature.")
    pdf.bullet("ChromaDB lives in the Flask process memory; tools/prewarm_embeddings.py builds it once and persists to disk for warm restarts.")

    # ── 4. DAY-BY-DAY ───────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("4. Day-by-Day Implementation Chronology")
    days = [
        ("Phase 1 / Day 0 - Foundation",
         "main.py + data/bns_knowledge_base.py + data/download_legal_corpus.py.\n"
         "Loads 38 curated BNS sections + 7 case summaries + 51-section IPC->BNS map into "
         "ChromaDB. CLI prompt loops. Outputs to outputs/CaseBrief_*.txt. No web UI yet."),

        ("Phase 2 / Day 0+ - PDF Generator",
         "pdf_generator.py with LexIndicPDF subclass. White-label via .env. Six dedicated "
         "build_*_page() functions for the six sections. Latin-1 safe text via _CHAR_MAP."),

        ("Web UI launch + Audit + Provenance (pre-Day 1)",
         "app.py introduced. Templates: index.html (3D landing), app.html (intake), result.html. "
         "audit.py introduced - JSONL log with salted hash. Verified Sources panel above analysis. "
         "Citation badges inline. LEXI chat with RAG-grounding refusal."),

        ("Day 1 - IPC -> BNS converter",
         "ipc_bns_converter.py: regex SECTION_GROUP + IPC_USS_PATTERN. /convert UI: drag .docx, "
         "see annotated output with yellow IPC + red BNS replacement. POST /convert/api/text "
         "and POST /convert/api/docx."),

        ("Day 2 - Microsoft Word add-in",
         "Office.js task pane. /addin/install serves the manifest XML. /addin/api/convert returns "
         "the annotation JSON. Lawyer drops a .docx into Word, the side panel highlights IPC refs."),

        ("Day 3 - Supreme Court precedent monitor",
         "monitors.py with SEED_RULINGS (15 hand-curated 2023-2025 SC cases). add_matter() lets "
         "the firm register watchlist keywords + sections. run_digest() scores rulings vs matters. "
         "/monitors UI shows daily digest with hit reasons. /monitors/api/digest cron-friendly endpoint."),

        ("Day 4 - Hindi UI + Hindi analysis",
         "i18n.py with t() function. Top-bar language selector. Conditional prompt in /analyze - "
         "the LLM is instructed to produce all 6 sections in Devanagari Hindi when language=hi. "
         "PDF generator uses a Hindi disclaimer template when LAW_FIRM_LANGUAGE=hi."),

        ("Day 5 - NALSA panel onboarding",
         "nalsa.py with SLSAS list (36 jurisdictions). /nalsa marketing landing + /nalsa/register "
         "self-claim form. is_registered(email) is the hook the pricing module uses to grant the "
         "free unlimited tier (Day 23)."),

        ("Day 6 - DPDP compliance posture",
         "compliance.py loads policies. /trust page renders the 28-question DPDP buyer-checklist. "
         "Downloadable .docx pack with the answers."),

        ("Day 7 - SOC 2 Type II readiness",
         "tools/soc2/* evidence files. /admin/soc2 dashboard - 10 controls, each pulling live "
         "evidence (e.g. last successful test-suite run for CC8.1)."),

        ("Day 8 - Per-section bare-act deep-links",
         "Every BNS section in the KB gets a deep_link field pointing to the official indiacode.nic.in "
         "PDF with #page=N hint. Verified Sources panel renders each as a click-through."),

        ("Day 9 - Matter intake registry",
         "matters.py: Firm -> Lawyer -> Matter triple. check_conflict() returns conflict-of-interest "
         "hits. /matters UI. matter_id passed into /analyze to thread artefacts under a case folder."),

        ("Day 10 - Multi-tenant auth",
         "auth.py: magic-link login. POST /auth/login emails a 6-digit code; user enters code at "
         "/auth/verify; HMAC-signed session cookie set. _current_user() in app.py reads cookie."),

        ("Day 11 - BNSS + BSA corpora",
         "data/bnss_knowledge_base.py + data/bsa_knowledge_base.py added. Same shape as BNS KB. "
         "Loaded into the same ChromaDB collection so retrieval works across all three statutes."),

        ("Day 12 - e-Courts CNR lookup",
         "ecourts.py with provider abstraction. /ecourts UI accepts a CNR number. Three providers: "
         "stub (returns a deterministic fake), kanoon (IndianKanoon JSON), official (NJDG)."),

        ("Day 13 - Ollama local-inference provider",
         "llm_provider.py: provider() picks based on LLM_PROVIDER env. ollama provider posts to "
         "http://localhost:11434/api/chat. Enables zero-sub-processor air-gapped deployments."),

        ("Day 14 - Tabular contract review (Indian Legora flagship)",
         "tabular.py: extract_clauses + classify + risk_flag. /tabular UI: drag a contract, get "
         "a side-by-side table - clause | type | risk | benchmark."),

        ("Day 15 - Status page + outbound webhook event bus",
         "/status public uptime page. webhooks.py introduced - add_sub/remove_sub/emit. Five "
         "events: analysis.completed, monitor.digest.ready, matter.created, nalsa.registered, lead.captured."),

        ("Day 16 - REST API v1 + API-key auth + OpenAPI 3.0 + Swagger UI",
         "api_keys.py: SQLite-backed key issuance. /api/v1/analyze + /api/v1/convert/text. "
         "openapi_spec.py generates the OpenAPI 3.0 spec served at /api/v1/openapi.json. "
         "/api/v1/docs renders Swagger UI."),

        ("Day 17 - Pluggable email sender",
         "mailer.py: send(to, subject, text). Three providers via MAIL_PROVIDER env. "
         "send_login_code() helper used by auth.py."),

        ("Day 18 - Dockerfile + docker-compose + fly.io + Render + on-prem guide",
         "Dockerfile (multi-stage Python 3.13 slim). docker-compose.yml (Lex-Indic + Postgres + "
         "nginx). fly.toml. render.yaml. docs/DEPLOY.md."),

        ("Day 19 - Operator dashboard at /dashboard",
         "templates/dashboard.html. /dashboard/data.json aggregates audit + leads + matters + "
         "monitors + users into 6 KPI tiles + 4-step funnel + 14-day chart + recent activity tables."),

        ("Day 20 - Postgres-ready ORM + JSON migration tool",
         "db.py: SQLAlchemy 2.0 models for all 7 tables. is_enabled() switch. tools/migrate_to_postgres.py "
         "reads outputs/*/*.json and upserts into Postgres via the ORM. End-to-end tested against SQLite."),

        ("Day 21 - Dual-backend wiring complete",
         "matters.py + monitors.py wired to dual JSON/DB (webhooks/nalsa/leads were wired earlier). "
         "Each module exports backend() returning 'json' / 'sqlite' / 'postgres'. /dashboard shows "
         "the storage indicator. 8 new dual-backend tests."),

        ("Day 22 - Webhook retry queue (SQLite + exponential backoff)",
         "webhooks.py: replaced fire-and-forget _deliver() with _attempt_http(), _first_attempt() "
         "and a daemon-thread _drain_loop(). Failed deliveries written to outputs/webhooks/retry_queue.db. "
         "Backoff: 10s -> 60s -> 300s -> 900s -> 3600s, max 5 retries. retry_queue_stats() exposed at "
         "/webhooks/api/deliveries."),

        ("Day 23 - Pricing tier enforcement",
         "pricing.py: free (3/day per IP) / NALSA (unlimited free) / firm (200/day per API key) / "
         "internal (no limit). Quota check at /analyze + /api/v1/analyze. api_keys.py gains tier + "
         "daily_limit columns (backward-compatible ALTER TABLE migration)."),

        ("Day 24 - Scheduled cron jobs",
         "cron.py: digest_email (07:00 IST daily), nalsa_csv (00:00 IST Sunday), cleanup (02:00 IST daily). "
         "Admin-gated /cron/* HTTP triggers for Render's cron-job feature."),

        ("Day 25 - SMS / WhatsApp alert channel",
         "sms.py: 3 providers (stdout/msg91/twilio). 4 DLT-template message types: digest_alert, "
         "case_update, nalsa_welcome, magic_link. NALSA registrations trigger a WhatsApp welcome. "
         "/sms/test + /sms/status admin endpoints."),
    ]
    for title, body in days:
        pdf.h2(title, colour=PURPLE)
        pdf.para(body, size=9)

    # ── 5. STORAGE ARCHITECTURE ────────────────────────────────────────
    pdf.add_page()
    pdf.h1("5. Storage Architecture - Dual JSON / Postgres")
    pdf.para(
        "Every persistence module follows the same pattern. The `backend()` function inspects "
        "the DATABASE_URL env var via `db.is_enabled()` and routes accordingly:"
    )
    pdf.set_font("Courier", "", 8.5); pdf.set_fill_color(*LIGHT_GREY); pdf.set_text_color(*BLACK)
    snippet = (
        "def list_all() -> list[dict]:\n"
        "    if db.is_enabled():\n"
        "        with db.session() as s:\n"
        "            rows = s.query(db.Lead).order_by(db.Lead.captured_at.asc()).all()\n"
        "            return [asdict(_row_to_lead(r)) for r in rows]\n"
        "    return [asdict(l) for l in _load_json()]\n\n"
        "def backend() -> str:\n"
        "    if not db.is_enabled():\n"
        "        return \"json\"\n"
        "    scheme = db.database_url().split(\":\")[0].lower()\n"
        "    return \"postgres\" if \"postgres\" in scheme else \"sqlite\"\n"
    )
    pdf.multi_cell(avail, 4.5, _s(snippet), fill=True, border=0)
    pdf.ln(3)
    pdf.para(
        "JSON paths are gitignored; default location is outputs/<module>/*.json. SQLite path is "
        "outputs/lex.db when DATABASE_URL=sqlite:///outputs/lex.db. Postgres requires "
        "DATABASE_URL=postgres://user:pass@host:5432/db and psycopg2-binary installed."
    )

    # ── 6. DB SCHEMA ───────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("6. Database Schema (db.py)")
    tables = [
        ("firms",                "id (PK), name (UNIQUE), address, created_at"),
        ("lawyers",              "id (PK), firm_id (FK->firms, CASCADE), full_name, bar_council_no, email (indexed), role, created_at"),
        ("matters",              "id (PK, human-friendly FIRM/YYYY/SEQ), firm_id (FK, CASCADE), lawyer_id (FK, SET NULL), client_name (indexed), opposing_party (indexed), matter_type, description, status (indexed), created_at, updated_at"),
        ("monitor_matters",      "id (PK), label, keywords (JSON), sections (JSON), created_at"),
        ("nalsa_registrations",  "id (PK), full_name, panel_id (indexed), slsa (indexed), bar_council_no, email (UNIQUE), phone, practice_areas (JSON), case_volume_monthly, consent_to_contact, registered_at, status"),
        ("leads",                "id (PK), full_name, email, firm_or_org, role, practice_areas (JSON), how_heard, interests (JSON), referrer, user_agent, captured_at"),
        ("webhook_subs",         "id (PK), url, events (JSON), description, active, created_at"),
    ]
    for name, cols in tables:
        pdf.h2(name)
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*BLACK)
        pdf.multi_cell(avail, 5, _s("Columns: " + cols))
        pdf.ln(1)

    pdf.h2("Migration tool (tools/migrate_to_postgres.py)")
    pdf.para(
        "Reads outputs/*/*.json, calls db.create_all(), upserts every row by primary key. "
        "Dry-run mode by default; --apply to actually write. Verified end-to-end against "
        "SQLite (see task output for proof - 7 rows inserted across all 7 tables)."
    )

    # ── 7. ENDPOINTS ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("7. All HTTP Endpoints")
    endpoint_rows = [
        ["Method", "Path",                                    "Purpose"],
        ["GET",    "/",                                       "3D marketing landing page (Three.js knowledge-graph hero)"],
        ["GET",    "/app",                                    "Main intake UI (form + LEXI chat)"],
        ["POST",   "/analyze",                                "Run the 6-section case-brief pipeline (pricing-gated)"],
        ["POST",   "/chat",                                   "LEXI chat - RAG-grounded Q&A"],
        ["GET",    "/convert",                                "IPC -> BNS converter UI"],
        ["POST",   "/convert/api/text",                      "Convert pasted text"],
        ["POST",   "/convert/api/docx",                      "Convert uploaded .docx"],
        ["GET",    "/addin/install",                          "Word add-in manifest"],
        ["POST",   "/addin/api/convert",                      "Word add-in conversion endpoint"],
        ["GET",    "/tabular",                                "Tabular contract review UI"],
        ["POST",   "/tabular/api/review",                     "Run tabular review"],
        ["GET",    "/monitors",                               "SC monitor UI"],
        ["POST",   "/monitors/api/matters",                   "Add a watch-matter"],
        ["DELETE", "/monitors/api/matters/<id>",              "Remove a watch-matter"],
        ["GET",    "/monitors/api/digest",                    "Today's digest (JSON)"],
        ["GET",    "/monitors/digest.txt",                    "Today's digest (plain text - cron-friendly)"],
        ["GET",    "/matters",                                "Matter intake registry UI"],
        ["POST",   "/matters/api/firms",                      "Create a firm"],
        ["POST",   "/matters/api/lawyers",                    "Create a lawyer under a firm"],
        ["POST",   "/matters/api/matters",                    "Create a matter (with conflict check)"],
        ["GET",    "/matters/api/conflicts",                  "Conflict-of-interest scan"],
        ["GET",    "/ecourts",                                "e-Courts CNR lookup UI"],
        ["POST",   "/ecourts/api/lookup",                     "Look up a CNR number"],
        ["GET",    "/nalsa",                                  "NALSA marketing landing"],
        ["GET",    "/nalsa/register",                         "NALSA self-claim form"],
        ["POST",   "/nalsa/api/register",                     "Submit NALSA registration"],
        ["GET",    "/nalsa/api/stats",                        "Registry stats"],
        ["GET",    "/nalsa/api/export.csv",                   "Registry CSV (admin-gated)"],
        ["GET",    "/trust",                                  "DPDP compliance posture page"],
        ["GET",    "/admin/soc2",                             "SOC 2 controls dashboard (admin-gated)"],
        ["GET",    "/admin/api-keys",                         "API key management UI (admin-gated)"],
        ["GET",    "/auth/login",                             "Magic-link login form"],
        ["POST",   "/auth/login",                             "Send 6-digit code via email"],
        ["POST",   "/auth/verify",                            "Verify code, set session cookie"],
        ["POST",   "/auth/logout",                            "Clear session cookie"],
        ["GET",    "/try",                                    "Lead capture form"],
        ["POST",   "/try/submit",                             "Capture a lead, fire lead.captured webhook"],
        ["GET",    "/try/api/leads",                          "Recent leads (admin-gated)"],
        ["GET",    "/webhooks",                               "Webhook subscription management UI"],
        ["GET/POST", "/webhooks/api/subscriptions",           "List/create subscriptions"],
        ["DELETE", "/webhooks/api/subscriptions/<id>",        "Delete a subscription"],
        ["GET",    "/webhooks/api/deliveries",                "Recent deliveries + retry queue stats (Day 22)"],
        ["GET",    "/status",                                 "Public status page"],
        ["GET",    "/dashboard",                              "Operator dashboard (admin-gated, Day 19)"],
        ["GET",    "/dashboard/data.json",                    "Dashboard data feed (includes storage backend indicator, Day 21)"],
        ["POST",   "/cron/digest_email",                      "Manually trigger digest job (Day 24, admin-gated)"],
        ["POST",   "/cron/nalsa_csv",                         "Manually trigger NALSA CSV export"],
        ["POST",   "/cron/cleanup",                           "Manually trigger audit cleanup"],
        ["POST",   "/sms/test",                               "Send a test SMS/WhatsApp (Day 25, admin-gated)"],
        ["GET",    "/sms/status",                             "SMS provider configuration status"],
        ["GET",    "/db/health",                              "DB health check (Day 20)"],
        ["POST",   "/api/v1/analyze",                         "REST API analyze (API-key-gated, pricing-gated)"],
        ["POST",   "/api/v1/convert/text",                    "REST API IPC->BNS conversion"],
        ["GET",    "/api/v1/openapi.json",                    "OpenAPI 3.0 spec"],
        ["GET",    "/api/v1/docs",                            "Swagger UI"],
    ]
    pdf.table(endpoint_rows[0], endpoint_rows[1:], col_widths=[20, 70, 100])

    # ── 9. ENV VARS ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("9. Environment Variables - Complete Reference")
    env_rows = [
        ["Variable", "Default", "Purpose"],
        ["GEMINI_API_KEY", "(required)", "Gemini 1.5 Pro API key"],
        ["GROQ_API_KEY",   "(optional)", "Groq Llama 3.3 70B key"],
        ["LLM_PROVIDER", "groq", "groq | ollama | gemini"],
        ["OLLAMA_HOST",  "http://localhost:11434", "Ollama endpoint when LLM_PROVIDER=ollama"],
        ["DATABASE_URL", "(unset)", "postgres://... or sqlite:///outputs/lex.db; unset = JSON files"],
        ["AUDIT_HASH_SALT", "lex-indic-dev-only-do-not-deploy", "Salt for SHA-256 hashing of stories in audit log + webhook sigs"],
        ["AUDIT_RETENTION_DAYS", "90", "Days to keep audit logs before cron cleanup deletes them"],
        ["MAIL_PROVIDER", "stdout", "stdout | smtp | ses"],
        ["SMTP_HOST", "(required for smtp)", "SMTP server hostname"],
        ["SMTP_PORT", "587", "SMTP port"],
        ["SMTP_USER", "(required for smtp)", "SMTP username"],
        ["SMTP_PASS", "(required for smtp)", "SMTP password"],
        ["MAIL_FROM", "noreply@lex-indic.in", "From address for outgoing mail"],
        ["AWS_REGION", "ap-south-1", "AWS region for SES"],
        ["SMS_PROVIDER", "stdout", "stdout | msg91 | twilio"],
        ["MSG91_AUTH_KEY", "(required for msg91)", "MSG91 API auth key"],
        ["MSG91_SENDER_ID", "LEXIND", "6-char DLT sender ID"],
        ["MSG91_WA_NUMBER", "(optional)", "WhatsApp-enabled MSG91 number"],
        ["MSG91_TEMPLATE_ID_DIGEST",  "(optional)", "DLT template ID for digest alerts"],
        ["MSG91_TEMPLATE_ID_CASE",    "(optional)", "DLT template ID for case updates"],
        ["MSG91_TEMPLATE_ID_NALSA_WELCOME", "(optional)", "DLT template ID for NALSA welcome"],
        ["MSG91_TEMPLATE_ID_LOGIN",   "(optional)", "DLT template ID for magic-link login"],
        ["TWILIO_ACCOUNT_SID", "(required for twilio)", "Twilio account SID"],
        ["TWILIO_AUTH_TOKEN",  "(required for twilio)", "Twilio auth token"],
        ["TWILIO_FROM_NUMBER", "(required for twilio sms)", "Twilio SMS-enabled number"],
        ["TWILIO_WA_FROM",     "(required for twilio whatsapp)", "Twilio WhatsApp number (whatsapp:+14155...)"],
        ["FREE_DAILY_LIMIT",   "3",   "Free tier daily analysis cap"],
        ["FIRM_DAILY_LIMIT",   "200", "Firm tier daily analysis cap (per API key)"],
        ["DISABLE_RATE_LIMITS","(unset)","Set to 1 to disable all pricing checks (local dev)"],
        ["LAW_FIRM_NAME",      "LEX-INDIC", "White-label PDF firm name"],
        ["LAW_FIRM_TAGLINE",   "BNS TRANSITION ENGINE", "PDF tagline"],
        ["LAW_FIRM_SUBTITLE",  "AI-Powered Junior Associate...", "PDF subtitle"],
        ["LAW_FIRM_DISCLAIMER","Lex-Indic is not a law firm...", "PDF disclaimer"],
        ["ADMIN_TOKEN",        "(required for prod)", "X-Admin-Token header for /dashboard, /admin/*, /cron/*"],
        ["NALSA_EXPORT_TOKEN", "(optional)", "Gates /nalsa/api/export.csv"],
        ["DIGEST_EMAIL_TO",    "(optional)", "Comma-separated override for cron digest recipients"],
    ]
    pdf.table(env_rows[0], env_rows[1:], col_widths=[55, 50, 85])

    # ── 10. TEST SUITE ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("10. Test Suite")
    pdf.kv("Files",        "tests/test_pure.py (80 tests), tests/test_routes.py (~14 tests)")
    pdf.kv("Runtime",      "under 0.3 seconds for test_pure (no Flask, no network)")
    pdf.kv("Coverage",     "pure-function modules nearly 100%; route layer best-effort")
    pdf.kv("Run command", "python -m pytest tests/test_pure.py -q")

    pdf.h2("Test classes (80 tests)")
    test_classes = [
        ("TestIpcBnsConverter (8)",  "Regex behaviour, grouped sections, edge cases"),
        ("Test monitors (4)",         "Section normalisation, scoring, empty-matter digest"),
        ("Test matters (4)",          "add_firm, add_lawyer, add_matter, conflict check"),
        ("TestTabular (3)",           "Clause extraction, classification, risk flag"),
        ("TestI18n (2)",              "Translation lookup, fallback to English"),
        ("TestAudit (3)",             "Hash determinism with salt, log line shape"),
        ("TestEcourts (3)",           "Stub provider, kanoon parsing, error handling"),
        ("TestNalsa (5)",             "Validate, register, is_registered, SLSA enum"),
        ("TestAuth (4)",              "Token generation, HMAC verification, expiry"),
        ("TestApiKeys (4)",           "Issue, verify, rate-limit, revoke"),
        ("TestWebhooks (5)",          "Add/list/remove, retry-queue stats (Day 22)"),
        ("TestLlmProvider (3)",       "Default groq, ollama fallback, env override"),
        ("TestMailer (5)",            "Stdout, missing config, smtp errors, login-code helper"),
        ("TestDbModule (4)",          "Disabled when no URL, sqlite create_all, health check, session error"),
        ("TestDualBackendIndicators (8)", "Day 21 - all 5 modules return 'json' or 'sqlite' correctly + CRUD round-trips"),
        ("TestPricing (7)",           "Day 23 - all 4 tier paths"),
        ("TestCron (5)",              "Day 24 - csv export, cleanup, digest dry-run, formatting"),
        ("TestSms (8)",               "Day 25 - all 3 providers, phone normalisation, template errors"),
    ]
    for c, desc in test_classes:
        pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*PURPLE)
        pdf.cell(60, 5, _s(c))
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*BLACK)
        pdf.multi_cell(avail - 60, 5, _s(desc))

    # ── 11. KNOWN LIMITS ────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("11. Known Limitations & Unfinished Work")
    limits = [
        ("Single-tenant Postgres",
         "db.py defines models but there is no tenant_id column. A multi-tenant deployment "
         "requires either (a) one DB per tenant (current Enterprise path), or (b) adding "
         "tenant_id to every table + row-level security."),
        ("ChromaDB in-memory by default",
         "Cold-start re-embeds 38 BNS + 7 cases + 15 rulings (~90 seconds). tools/prewarm_embeddings.py "
         "persists to disk but is not yet wired into the Docker container's start command."),
        ("Webhook signing uses only HMAC-SHA256",
         "No timestamp in the signed payload; theoretically vulnerable to replay if the receiver "
         "doesn't de-duplicate on X-Lex-Event-Id. The receiver is told to de-dupe."),
        ("No real-time SC scraper yet",
         "monitors.py SEED_RULINGS is hand-curated. A production deployment needs a daily scraper "
         "of LiveLaw RSS / IndianKanoon new-judgment endpoint. Scheduled for Days 26-30."),
        ("e-Courts integration is stubbed for production",
         "ecourts.py 'kanoon' provider works for CNR lookup; 'official' provider returns a stub. "
         "Real NJDG integration requires a paid API agreement or web-scraping (TOS risk)."),
        ("Hindi UI does not yet cover all admin pages",
         "Main analyze flow + result page + monitors are translated. Dashboard, /trust, /admin/* "
         "remain English-only."),
        ("No real-time collaboration",
         "Two lawyers editing the same matter cannot see each other's changes. Not needed for v1; "
         "Q3 2026 candidate."),
        ("No Stripe billing",
         "Pricing tiers are enforced but there is no self-serve payment flow. Enterprise contracts "
         "are invoiced manually. Days 26-30 candidate."),
        ("No tenant isolation tests",
         "The Postgres schema would allow cross-tenant reads if the application layer accidentally "
         "omitted a firm_id filter. Need a dedicated test fixture for this."),
        ("Webhook retry queue is local SQLite",
         "Survives process restart but not host migration. Production should move to Redis or "
         "Postgres-backed queue when scaling beyond a single host."),
        ("DPDP right-to-erasure is a manual SQL operation",
         "Documented in docs/dpdp-runbook.md but not yet a one-click admin UI. Needs to be a "
         "self-serve user setting."),
        ("Annual SOC 2 Type II external audit not yet completed",
         "The dashboard simulates all 10 controls with live evidence. A formal external audit "
         "(Mazars India quoted; ~Rs. 18-25 lakh) is the Q3 2026 milestone."),
    ]
    for title, body in limits:
        pdf.h2(title, colour=RED)
        pdf.para(body, size=9)

    # ── 12. FUTURE ROADMAP ──────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("12. Future Roadmap")
    pdf.h2("Days 26-30 (immediate next sprint)")
    pdf.bullet("Real-time SC ruling scraper (LiveLaw RSS + IndianKanoon)")
    pdf.bullet("Stripe self-serve billing for the Firm tier")
    pdf.bullet("Custom KB upload UI for Enterprise tenants")
    pdf.bullet("Tenant isolation test fixture + 5 cross-tenant tests")
    pdf.bullet("Container start-command wired to prewarm_embeddings.py (cold start under 5 seconds)")

    pdf.h2("Q3 2026")
    pdf.bullet("Flutter mobile app with voice-mode")
    pdf.bullet("Real-time collaborative brief editing (CRDT)")
    pdf.bullet("ChromaDB to pgvector migration (single Postgres)")
    pdf.bullet("Mazars India SOC 2 Type II external audit")
    pdf.bullet("Hindi voice-to-text fine-tuning on legal vocabulary")
    pdf.bullet("LiveLaw + Bar & Bench partner integrations")

    pdf.h2("Q4 2026")
    pdf.bullet("Tamil + Bengali + Marathi UI + output")
    pdf.bullet("POCSO compliance pack (special-procedure builder)")
    pdf.bullet("NDPS bail playbook (mandatory under section 37 NDPS)")
    pdf.bullet("Companies Act 2013 compliance overlay for in-house GCs")

    pdf.h2("2027 (strategic)")
    pdf.bullet("NALSA panel-lawyer marketplace - paying clients can hire a verified panel advocate via the platform")
    pdf.bullet("State Judicial Academy partnership for a BNS bench-book")
    pdf.bullet("Bangladesh / Sri Lanka / Nepal expansion (shared common-law lineage)")
    pdf.bullet("EU AI Act high-risk-system compliance pack for international firms")
    pdf.bullet("Air-gapped enterprise edition with Kerberos / LDAP + Ollama-only inference")

    # ── 13. CONTINUATION GUIDE ──────────────────────────────────────────
    pdf.add_page()
    pdf.h1("13. Continuation Guide - For an AI Picking Up From Here")
    pdf.h2("Step 1 - Read these files first (in this order)")
    pdf.bullet("README.md - high-level project overview")
    pdf.bullet("CHANGELOG.md - 25-day chronology with commit hashes")
    pdf.bullet("app.py - master endpoint list; every other module wires into app.py")
    pdf.bullet("db.py - schema; the dual-backend pattern; the source of truth for column shapes")
    pdf.bullet("tests/test_pure.py - executable spec; reading this is faster than reading every module")
    pdf.bullet("this PDF (TechnicalDeepDive_Complete.pdf) for the why-decisions context")

    pdf.h2("Step 2 - Run the tests")
    pdf.set_font("Courier", "", 9); pdf.set_fill_color(*LIGHT_GREY); pdf.set_text_color(*BLACK)
    pdf.multi_cell(avail, 4.5, _s(
        "$ cd /Users/yuvrajpratapsingh/Desktop/legal_ai\n"
        "$ python -m pytest tests/test_pure.py -q\n"
        "  Expected: 80 passed in 0.3s"
    ), fill=True, border=0)
    pdf.ln(2)

    pdf.h2("Step 3 - Pick the next sensible piece of work")
    pdf.para(
        "Days 26-30 are listed in Section 12. The single highest-leverage item is the SC ruling "
        "scraper (it removes the 'hand-curated SEED_RULINGS' caveat from every sales conversation). "
        "Second-highest is Stripe self-serve billing (it unlocks the Firm tier without sales-team "
        "involvement). Third is the tenant isolation test fixture (it is a prerequisite for any "
        "multi-tenant Enterprise customer)."
    )

    pdf.h2("Step 4 - Follow the established conventions")
    pdf.bullet("Every new persistence module follows the matters.py / nalsa.py pattern: dataclass + _load_json + _save_json + DB-backed branch via db.is_enabled() + backend() reporter.")
    pdf.bullet("Every new admin endpoint calls _require_admin() at the top.")
    pdf.bullet("Every new tier-gated endpoint calls pricing.check() before the business logic.")
    pdf.bullet("Every new module gets at least one TestX class in tests/test_pure.py.")
    pdf.bullet("Every new HTTP endpoint that mutates state should emit a webhook event (webhooks.emit('module.action', payload)).")
    pdf.bullet("Every commit message follows: 'Day N: <short description>' for sprint days, or '<verb>: <description>' otherwise.")

    pdf.h2("Step 5 - Write the test BEFORE the implementation")
    pdf.para(
        "Every existing module shows the pattern. The TestX class lives in tests/test_pure.py, "
        "uses monkeypatch + tmp_path + the dual-backend env-var trick, and tests both the JSON "
        "path AND the SQLite path. Look at TestDualBackendIndicators for the template."
    )

    pdf.h2("Step 6 - Commit + push, then update README + CHANGELOG")
    pdf.set_font("Courier", "", 9); pdf.set_fill_color(*LIGHT_GREY); pdf.set_text_color(*BLACK)
    pdf.multi_cell(avail, 4.5, _s(
        "$ git add <files>\n"
        "$ git commit -m \"Day N: <short description>\"\n"
        "$ # update CHANGELOG.md (5-line entry with commit hash placeholder)\n"
        "$ # update README.md (table row + version badge if needed)\n"
        "$ git push origin main"
    ), fill=True, border=0)
    pdf.ln(2)

    # ── 14. CODING CONVENTIONS ────────────────────────────────────────
    pdf.add_page()
    pdf.h1("14. Coding Conventions & Style")
    pdf.bullet("Python 3.13 idioms - PEP 604 unions (str | None), match-case where it improves readability")
    pdf.bullet("Module docstrings have a UNICODE BOX HEADER (the ╔═══╗ block) - keep this")
    pdf.bullet("Public function docstrings only when behaviour is non-obvious; private functions self-document via name")
    pdf.bullet("snake_case for functions, PascalCase for classes, SCREAMING for module-level constants")
    pdf.bullet("Imports grouped: stdlib, third-party, local; each group alphabetised inside")
    pdf.bullet("'from __future__ import annotations' at the top of every Python file")
    pdf.bullet("Imports of in-project modules use 'import X as X_module' in app.py only - other modules just import X")
    pdf.bullet("Type hints on every public function signature; not always required on private helpers")
    pdf.bullet("Dataclasses for value-objects; never NamedTuple")
    pdf.bullet("Errors raised as ValueError (user input), RuntimeError (state), or specific custom (rare)")
    pdf.bullet("No logging library yet (intentional - audit.py + print are the two channels)")
    pdf.bullet("No async (intentional - Flask sync; daemon threads where needed)")

    pdf.h2("Commit messages")
    pdf.bullet("Sprint days: 'Day N: <description>' (matches CHANGELOG style)")
    pdf.bullet("Bug fixes: 'fix: <what was wrong>'")
    pdf.bullet("Chores: 'chore: <description>'")
    pdf.bullet("Refactors: 'refactor: <what changed and why>'")
    pdf.bullet("Always include 'Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>' when the commit was AI-assisted")

    # ── 15. CRITICAL FILES ────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("15. Files an AI Should Read First")
    pdf.callout(
        "These 8 files give 90% of the project understanding in ~2,500 lines of reading. "
        "Read them in order; you can extend confidently after this.",
        bg=SOFT_GOLD, border=GOLD, font_size=10,
    )
    crit = [
        ("README.md",                 "Project vision, 25-day chronology, 'why this exists' narrative"),
        ("CHANGELOG.md",              "Every commit with hash + one-line description"),
        ("app.py",                    "Endpoint catalog + import graph; the spinal cord of the project"),
        ("db.py",                     "ORM schema + dual-backend pattern"),
        ("tests/test_pure.py",        "Executable specification - the 80 tests describe every contract"),
        ("matters.py",                "Reference example for any persistence module"),
        ("pricing.py",                "Reference example for the cross-cutting check pattern"),
        ("this PDF (TechnicalDeepDive)", "Why-decisions context that isn't in code comments"),
    ]
    for f, why in crit:
        pdf.h3(f, colour=PURPLE)
        pdf.para(why, size=9)

    pdf.h2("Final note")
    pdf.callout(
        "This project is a deliberate exercise in shipping a v1.7 production-grade legal AI in "
        "25 well-bounded days. Every commit is reviewable; every test is fast; every module is "
        "swappable. The next AI should treat this codebase as a well-maintained garden: extend "
        "by following the existing patterns, never refactor without a test in place first, and "
        "always commit + push in coherent units that map to a user-visible improvement.",
        bg=SOFT_BLUE, border=BLUE, font_size=10,
    )

    out = OUTPUT_DIR / "02_TechnicalDeepDive_Complete.pdf"
    pdf.output(str(out))
    print(f"  [OK] {out.relative_to(OUTPUT_DIR.parent.parent)}")
    return out


# ════════════════════════════════════════════════════════════════════════════
#  PDF 3 — USER GUIDE (plain language, click-by-click)
# ════════════════════════════════════════════════════════════════════════════
def build_user_guide_pdf():
    pdf = LexPdf(
        doc_title="Lex-Indic - Your Simple User Guide",
        subtitle="Easy-language, click-by-click instructions",
        accent=GREEN,
    )

    # ── COVER ──────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*GREEN); pdf.rect(0, 0, pdf.w, 90, style="F")
    pdf.set_fill_color(*GOLD);  pdf.rect(0, 90, pdf.w, 3, style="F")
    pdf.set_xy(20, 30)
    pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*GOLD)
    pdf.cell(0, 6, _s("LEX-INDIC - USER GUIDE"))
    pdf.set_xy(20, 50)
    pdf.set_font("Helvetica", "B", 26); pdf.set_text_color(*WHITE)
    pdf.cell(0, 14, _s("Your Simple Guide"), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 14, _s("to Using Lex-Indic"))
    pdf.set_xy(20, 105)
    pdf.set_font("Helvetica", "", 12); pdf.set_text_color(*GREY)
    pdf.cell(0, 7, _s("Plain English. Step by step. What to click, what to type,"), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 7, _s("what each page does, and what to do when something goes wrong."))

    pdf.set_xy(20, 145)
    pdf.set_fill_color(*SOFT_GREEN); pdf.set_draw_color(*GREEN)
    pdf.rect(20, 145, pdf.w - 40, 65, style="DF")
    pdf.set_xy(25, 152)
    pdf.set_font("Helvetica", "B", 12); pdf.set_text_color(*GREEN)
    pdf.cell(0, 7, _s("Who is this guide for?"), new_y=YPos.NEXT)
    pdf.set_x(25); pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*BLACK)
    pdf.multi_cell(pdf.w - 50, 5.5, _s(
        "This guide is for YOU - the person who built Lex-Indic and now wants to know what "
        "every page does, where to click, and what each part of the system actually does in "
        "plain English. No technical jargon. Just clear steps with examples."
    ))

    pdf.set_xy(20, 230)
    pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*GREEN)
    pdf.cell(0, 6, _s("How to use this guide:"), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*BLACK)
    pdf.cell(0, 5, _s("1. Each page in the app gets its own section."), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 5, _s("2. Each section shows you: what the page is for, where to go, what to click."), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 5, _s("3. Examples show what to type and what the result looks like."), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 5, _s("4. Tips boxes (gold) show shortcuts and pro-moves."), new_y=YPos.NEXT)
    pdf.set_x(20); pdf.cell(0, 5, _s("5. Warning boxes (red) tell you what NOT to do."))

    pdf.set_y(-25)
    pdf.set_font("Helvetica", "I", 9); pdf.set_text_color(*GREY)
    pdf.cell(0, 5, _s("Generated " + datetime.now().strftime("%B %Y") + " - for personal reference only"), align="C")

    # ── TOC ──────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("What's Inside")
    toc = [
        "1. First time? Start here",
        "2. The Home Page (when someone types the address)",
        "3. The Main App Page - where the real work happens",
        "4. LEXI - your AI chat assistant",
        "5. The IPC to BNS Converter",
        "6. Tabular Contract Review",
        "7. Supreme Court Monitor",
        "8. Matters - your case folders",
        "9. NALSA Registration page",
        "10. Trust & DPDP page",
        "11. SOC 2 Dashboard",
        "12. The Operator Dashboard (admin home page)",
        "13. The API Docs page",
        "14. Login + Sessions (how login works)",
        "15. The Status page",
        "16. Webhooks - sending notifications elsewhere",
        "17. Pricing - free, NALSA, firm, internal",
        "18. Cron Jobs - scheduled tasks",
        "19. SMS and WhatsApp Alerts",
        "20. Common problems and how to fix them",
        "21. Glossary - what every word means",
    ]
    pdf.set_font("Helvetica", "", 11)
    for i, t in enumerate(toc, 1):
        pdf.set_text_color(*GOLD); pdf.set_font("Helvetica", "B", 10)
        pdf.cell(12, 7, _s(f"{i}."))
        pdf.set_text_color(*BLACK); pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, _s(t[len(str(i))+2:]), new_y=YPos.NEXT)

    # ── 1. FIRST TIME ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("1. First Time? Start Here")
    pdf.h2("Step 1 - Open your terminal and go to the project folder")
    pdf.set_font("Courier", "", 9); pdf.set_fill_color(*LIGHT_GREY); pdf.set_text_color(*BLACK)
    avail = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(avail, 5, _s("$ cd /Users/yuvrajpratapsingh/Desktop/legal_ai"), fill=True, border=0)
    pdf.ln(2)

    pdf.h2("Step 2 - Make sure your Gemini API key is set")
    pdf.para(
        "Open the .env file. You should see a line like GEMINI_API_KEY=AIza... If it isn't "
        "there, get a key from https://aistudio.google.com/app/apikey and paste it in. "
        "Without this key, the AI can't generate legal briefs."
    )

    pdf.h2("Step 3 - Start the app")
    pdf.set_font("Courier", "", 9); pdf.set_fill_color(*LIGHT_GREY); pdf.set_text_color(*BLACK)
    pdf.multi_cell(avail, 5, _s("$ python3 app.py"), fill=True, border=0)
    pdf.ln(2)
    pdf.para(
        "You'll see a message like 'Running on http://127.0.0.1:8080'. That means the app is "
        "alive. Don't close this terminal window - it's the server."
    )

    pdf.h2("Step 4 - Open it in your browser")
    pdf.para(
        "Go to http://localhost:8080 in Chrome / Safari / Firefox. You'll land on the home "
        "page with the spinning 3D knowledge-graph in the background. Welcome to Lex-Indic."
    )

    pdf.callout(
        "TIP: If you want to stop the app, press Ctrl+C in the terminal where you ran it. "
        "If you want to run it in the background, use 'python3 app.py &'.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 2. HOME PAGE ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("2. The Home Page (http://localhost:8080/)")
    pdf.h2("What this page is for")
    pdf.para(
        "This is the marketing landing page - the first thing a new visitor sees. It's "
        "designed to convince a lawyer or law-firm partner that Lex-Indic is worth trying. "
        "There's a 3D spinning knowledge-graph hero (Three.js), three feature cards, "
        "testimonials, and a big 'Try the AI Junior Associate' button."
    )

    pdf.h2("What you can click")
    pdf.bullet("Top-right 'Try Lex-Indic' button - takes you to the main app page (/app)")
    pdf.bullet("Top-right 'Login' button - takes you to the magic-link login page")
    pdf.bullet("Top-right language toggle (EN / HI) - switches the entire UI to Hindi")
    pdf.bullet("Bottom-right floating LEXI bubble - opens the AI chat")
    pdf.bullet("Navigation links in the header - Trust page, NALSA, Convert, Monitors")

    pdf.callout(
        "TIP: If you want a clean version of the home page for screenshots, open it in "
        "incognito mode - no top-bar 'logged in as' chip will appear.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 3. MAIN APP PAGE ──────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("3. The Main App Page (/app)")
    pdf.h2("What this page is for")
    pdf.para(
        "This is where the real work happens. A lawyer types in the client's story (or "
        "dictates it with the microphone), clicks the green 'Generate Case Brief' button, "
        "and 15 seconds later sees the AI's complete 6-section legal analysis."
    )

    pdf.h2("What you see on the page (top to bottom)")
    pdf.bullet("Top header bar - logo, language toggle, login chip")
    pdf.bullet("A big text box labelled 'Client's Statement' - this is where you type the story")
    pdf.bullet("A microphone button to the right of the text box - click it to dictate instead of type")
    pdf.bullet("A small 'Additional Info' textbox - extra context (e.g. 'happened on 15 May 2025')")
    pdf.bullet("Attachment buttons - upload FIR copy, medical reports, photos")
    pdf.bullet("Language buttons (EN / HI) - choose the output language")
    pdf.bullet("Matter dropdown - if you've registered matters, link this analysis to one")
    pdf.bullet("The big green 'Generate Case Brief' button - click to start")

    pdf.h2("What happens when you click Generate")
    pdf.para(
        "A loading bar appears at the top. The system does the following (you don't see this; "
        "it happens behind the scenes):"
    )
    pdf.bullet("Looks up the 8 most relevant BNS sections from its knowledge base")
    pdf.bullet("Builds a prompt with the story + the 8 sections + a system instruction")
    pdf.bullet("Sends it to Gemini 1.5 Pro")
    pdf.bullet("Waits for the response (usually 10-15 seconds)")
    pdf.bullet("Parses the response into 6 sections")
    pdf.bullet("Generates a downloadable PDF")
    pdf.bullet("Writes an audit-log entry")

    pdf.h2("What you see when it's done")
    pdf.bullet("A 'Verified Sources' card at the top - shows the 8 KB sections the AI used")
    pdf.bullet("Six big tabs / sections: Advisory, Legal Analysis, Strategy, FIR, Legal Notice, Police Help")
    pdf.bullet("Citation badges (gold) inside the text - hover to see the source")
    pdf.bullet("A 'Download PDF' button at the top-right of the results card")
    pdf.bullet("A 'Find Help Near You' section at the bottom (nearest police station + lawyer links)")

    pdf.callout(
        "TIP: The microphone button uses your browser's speech recognition. Speak slowly and "
        "clearly; pause for the system to keep up. If you're using Hindi, switch the language "
        "toggle FIRST, then click the mic - it will recognise Hindi instead of English.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )
    pdf.callout(
        "WARNING: Don't paste a client's real name, real phone number, or real address into "
        "the story unless you have their consent. The story is hashed before logging - "
        "but the AI's response may quote it back to you in plain text.",
        bg=SOFT_RED, border=RED, font_size=9,
    )

    # ── 4. LEXI CHAT ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("4. LEXI - Your AI Chat Assistant")
    pdf.h2("What this is")
    pdf.para(
        "LEXI is a chat bubble that lives in the bottom-right of every page. Click it and a "
        "chat window opens. You can ask questions like 'What is BNS section 304?' or 'What "
        "section replaced IPC 498A?'. LEXI is RAG-grounded - meaning it only answers from "
        "the 38-section BNS knowledge base. If you ask about a section that isn't in the KB, "
        "LEXI will refuse and point you to indiacode.nic.in instead of inventing a number."
    )

    pdf.h2("Where to click")
    pdf.bullet("Bottom-right of any page - click the green bubble with the speech-bubble icon")
    pdf.bullet("In the chat window: the text field at the bottom - type your question")
    pdf.bullet("Microphone icon next to the text field - click to ask by voice")
    pdf.bullet("'Voice On/Off' toggle in the chat header - mute LEXI's spoken replies")
    pdf.bullet("X in the top-right of the chat window - closes the chat")

    pdf.h2("Below each LEXI reply")
    pdf.para(
        "There's a 'Sources' strip showing the 4 KB entries LEXI consulted. Click any source "
        "to see the full BNS section text. This is the same transparency feature as the "
        "main analyzer - LEXI never invents."
    )

    pdf.callout(
        "TIP: LEXI is great for quick lookups but not for full case analysis. If your "
        "question is 'My client's husband beat her for dowry, what do we do?' - that's a "
        "case-analysis question. LEXI will suggest using the main /app page instead.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 5. CONVERTER ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("5. IPC to BNS Converter (/convert)")
    pdf.h2("What this is")
    pdf.para(
        "Take any document or pleading written under the old IPC, and the converter will (a) "
        "find every IPC section reference, (b) show you the BNS equivalent, and (c) let you "
        "download a marked-up version with IPC highlighted yellow and BNS inserted in red."
    )

    pdf.h2("Two ways to use it")
    pdf.bullet("Paste text into the big text box - works for chunks of pleading text")
    pdf.bullet("Drag a .docx file into the upload area - works for full pleadings")

    pdf.h2("What you see in the result")
    pdf.bullet("Side-by-side panels: original (with IPC highlighted) and annotated (with BNS inserted)")
    pdf.bullet("Summary card at the top: 'Found 12 IPC references; 11 mapped, 1 unmapped'")
    pdf.bullet("For each match: the IPC section, the BNS section it maps to, the section title")
    pdf.bullet("'Download annotated .docx' button (top-right)")

    pdf.callout(
        "TIP: There's also a Microsoft Word add-in version of this. Go to /addin/install for "
        "the manifest XML, sideload it into Word, and the converter appears as a task pane "
        "INSIDE Word. Much faster than the web flow for a lawyer who lives in Word.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 6. TABULAR ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("6. Tabular Contract Review (/tabular)")
    pdf.h2("What this is")
    pdf.para(
        "Drop a contract (PDF or DOCX) and the system breaks it into clauses, classifies each "
        "(payment, termination, indemnity, etc), and flags the risky ones against an Indian-law "
        "playbook. Think of it as having a senior contracts associate read the whole document "
        "in 10 seconds."
    )

    pdf.h2("How to use")
    pdf.bullet("Drag-and-drop the contract into the big upload zone, OR click 'Browse'")
    pdf.bullet("Wait 10-30 seconds (longer for big contracts)")
    pdf.bullet("Look at the table: each row is one clause")

    pdf.h2("The table columns")
    pdf.bullet("Clause number (1, 2, 3...)")
    pdf.bullet("Clause type (payment, term, IP, confidentiality, etc)")
    pdf.bullet("Risk flag (green/yellow/red)")
    pdf.bullet("Snippet of the clause text")
    pdf.bullet("Suggested edit (if any)")

    # ── 7. MONITOR ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("7. Supreme Court Monitor (/monitors)")
    pdf.h2("What this is")
    pdf.para(
        "Tell the system which areas of law you care about ('dowry death', 'snatching', 'BNS "
        "304'), and every day it scans the latest Supreme Court rulings and shows you any "
        "that match. Saves a senior advocate about 1 hour per day of reading SCC Online / "
        "LiveLaw."
    )

    pdf.h2("How to add a watch-matter")
    pdf.bullet("Click 'Add new matter' at the top")
    pdf.bullet("Type a label (e.g. 'My dowry cases')")
    pdf.bullet("Type keywords, comma-separated (e.g. 'dowry, 498A, matrimonial cruelty')")
    pdf.bullet("Type sections, comma-separated (e.g. 'BNS 85, BNS 80')")
    pdf.bullet("Click 'Save'")

    pdf.h2("Reading the digest")
    pdf.bullet("Today's date appears at the top")
    pdf.bullet("Each watch-matter has its own card")
    pdf.bullet("Inside each card: the matched SC rulings with a match percentage")
    pdf.bullet("Click a ruling title to expand the full ratio + practice impact")

    pdf.callout(
        "TIP: There's also a /monitors/digest.txt endpoint that returns the same digest as "
        "plain text. Pipe it to email or cat it from a cron job. The Day 24 cron.py runs this "
        "automatically at 07:00 IST every day.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 8. MATTERS ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("8. Matters - Your Case Folders (/matters)")
    pdf.h2("What this is")
    pdf.para(
        "A simple firm -> lawyer -> matter registry. Register your firm once, register the "
        "lawyers in your firm, then every case (matter) is filed under a lawyer. When you "
        "run /analyze, you can pick a matter from a dropdown, and the resulting PDF + audit "
        "entry are threaded under that case folder."
    )

    pdf.h2("First time? Do these three things in order")
    pdf.bullet("Click 'Add firm' -> type the firm name + address -> Save. You get a firm_id.")
    pdf.bullet("Click 'Add lawyer' -> pick the firm -> type the lawyer's name, BCI number, email, role -> Save. You get a lwy_id.")
    pdf.bullet("Click 'Add matter' -> pick firm + lawyer -> type client name, opposing party, matter type. The system AUTOMATICALLY checks for conflicts and warns you if any of your existing matters has the new client as an OPPOSING party.")

    pdf.h2("The conflict-of-interest check")
    pdf.callout(
        "Example: Last year you represented Mr. Sharma. Today, a new client wants you to sue "
        "Mr. Sharma. The system spots this and shows a red warning: 'You previously represented "
        "Mr. Sharma; review before accepting'. This is the kind of check that, missed once, "
        "can get an advocate suspended by the Bar Council.",
        bg=SOFT_RED, border=RED, font_size=9,
    )

    # ── 9. NALSA ───────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("9. NALSA Registration Page (/nalsa)")
    pdf.h2("What this is")
    pdf.para(
        "NALSA is the National Legal Services Authority - the body that runs free legal aid "
        "in India. There are 70,000 panel advocates across all the states. Lex-Indic is free "
        "for them - permanently. /nalsa is where they self-register their panel ID, so the "
        "system knows to give them unlimited free analyses."
    )

    pdf.h2("Two pages")
    pdf.bullet("/nalsa - the marketing landing pitched specifically at panel lawyers")
    pdf.bullet("/nalsa/register - the form to self-claim panel membership")

    pdf.h2("On the register form, you fill in")
    pdf.bullet("Full name")
    pdf.bullet("Panel ID (e.g. 'MAH/1234/2010')")
    pdf.bullet("State Legal Services Authority (dropdown of 36 SLSAs)")
    pdf.bullet("Bar Council number")
    pdf.bullet("Email + Phone")
    pdf.bullet("Practice areas (optional)")
    pdf.bullet("Tick the consent-to-contact box (required)")

    pdf.h2("What happens after submitting")
    pdf.para(
        "Immediately: (a) a WhatsApp welcome message goes to the phone number (Day 25 SMS "
        "feature), (b) the registration is logged in outputs/nalsa/registry.json, (c) the "
        "user can now use /analyze without any quota limit."
    )

    # ── 10. TRUST ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("10. Trust & DPDP Page (/trust)")
    pdf.h2("What this is")
    pdf.para(
        "A read-only page that lays out how Lex-Indic complies with India's DPDP Act 2023 "
        "(Digital Personal Data Protection). Show this to a general counsel before they sign "
        "the firm up. It answers the 28 standard GC questions: data residency, encryption "
        "at rest, who can access data, what happens on deletion request, etc."
    )

    pdf.h2("Things you'll see on this page")
    pdf.bullet("'Data flow' diagram - what data goes where")
    pdf.bullet("'Sub-processors' table - every third-party we use (Gemini, Groq, Hetzner)")
    pdf.bullet("'Right to erasure' button - one-click triggers the deletion workflow")
    pdf.bullet("'Download DPA pack' - a .docx with the Data Processing Agreement template")

    # ── 11. SOC 2 ───────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("11. SOC 2 Dashboard (/admin/soc2)")
    pdf.h2("What this is")
    pdf.para(
        "An admin-only page that shows the live status of 10 SOC 2 Type II controls. Each "
        "control has live evidence (e.g. CC8.1 Change Management pulls the latest test-suite "
        "run from CI). This is what the firm's external auditor would inspect."
    )

    pdf.h2("Each control card shows")
    pdf.bullet("Control code (e.g. CC1.1)")
    pdf.bullet("Plain-English description")
    pdf.bullet("Pass / fail / in-progress badge")
    pdf.bullet("'Evidence' link - clicks through to the underlying file")

    pdf.callout(
        "WARNING: This page is admin-only. You need to send the X-Admin-Token header with "
        "your request. In dev: just open the page (no token check). In prod: set the "
        "ADMIN_TOKEN env var and pass it as X-Admin-Token in your request headers.",
        bg=SOFT_RED, border=RED, font_size=9,
    )

    # ── 12. DASHBOARD ──────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("12. The Operator Dashboard (/dashboard)")
    pdf.h2("What this is")
    pdf.para(
        "This is YOUR home page as the operator. Look here every morning. It shows: how many "
        "analyses ran in the last 24 hours, how many new leads / NALSA registrations came in, "
        "how many errors were thrown, and which BNS sections are most-retrieved. Auto-refreshes "
        "every 60 seconds."
    )

    pdf.h2("What's on the page")
    pdf.bullet("Top: six big KPI tiles (Leads, Analyses, Matters, Monitor Hits, Sessions, Errors)")
    pdf.bullet("Below: 4-step onboarding funnel (Landing -> /try -> /app opened -> Analysis run)")
    pdf.bullet("Two cards side-by-side: recent analyses (left) + top retrieved sections (right)")
    pdf.bullet("Bar chart: 14-day analysis volume")
    pdf.bullet("Recent leads table")
    pdf.bullet("Storage backend card (Day 21) - shows json / sqlite / postgres for each module")

    pdf.callout(
        "TIP: The storage card lets you see at a glance whether the JSON files or the Postgres "
        "is being used. If you set DATABASE_URL, the badges turn from grey 'json' to gold "
        "'sqlite' or green 'postgres'. The dashboard is your fastest way to verify the dual-"
        "backend switch is live.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 13. API DOCS ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("13. The API Docs Page (/api/v1/docs)")
    pdf.h2("What this is")
    pdf.para(
        "A Swagger UI page that lets a firm's developer test your REST API right from the "
        "browser. They see every endpoint, paste their API key, click 'Try it out', see the "
        "response. Standard developer experience - this is what makes your tool feel "
        "enterprise-grade."
    )

    pdf.h2("How a developer uses it")
    pdf.bullet("Open /api/v1/docs in browser")
    pdf.bullet("Click 'Authorize' (top-right)")
    pdf.bullet("Paste their API key (format: lex_live_<id>:<secret>)")
    pdf.bullet("Click any endpoint to expand")
    pdf.bullet("Click 'Try it out' -> fill in body -> 'Execute' -> see the live response")

    pdf.h2("How to give a firm an API key")
    pdf.bullet("Open the admin API-keys page: /admin/api-keys (admin-token-gated)")
    pdf.bullet("Click 'Issue new key'")
    pdf.bullet("Choose tier: free / nalsa / firm / internal")
    pdf.bullet("Choose rate limit (default 60/min)")
    pdf.bullet("Click 'Issue' - the secret is shown ONCE; copy it and email to the firm")
    pdf.bullet("The key + secret combined form the lex_live_xxx:yyy string they use")

    # ── 14. LOGIN ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("14. Login (Magic Link)")
    pdf.h2("What this is")
    pdf.para(
        "Lex-Indic doesn't use passwords. You type your email, the system sends you a 6-digit "
        "code, you type the code, and you're in. Standard 'passwordless' or 'magic-link' "
        "flow. Safer than passwords (nothing to steal); easier for non-technical lawyers."
    )

    pdf.h2("Step by step")
    pdf.bullet("Go to /auth/login or click 'Login' in the top-right of any page")
    pdf.bullet("Type your email address (e.g. yuvraj@lex-indic.in)")
    pdf.bullet("Click 'Send code'")
    pdf.bullet("Check your inbox (or your terminal, if MAIL_PROVIDER=stdout in dev)")
    pdf.bullet("Type the 6-digit code into the next form")
    pdf.bullet("Click 'Verify'")
    pdf.bullet("You're now logged in - a session cookie is set, valid for 7 days")

    pdf.callout(
        "TIP: In dev mode, the code is printed to the terminal where 'python3 app.py' is "
        "running. Look for a line that starts with '[stdout] Sending...'. Copy the 6-digit "
        "code from there. In production, configure MAIL_PROVIDER=smtp and set SMTP_HOST etc.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 15. STATUS ───────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("15. The Status Page (/status)")
    pdf.h2("What this is")
    pdf.para(
        "A public uptime page. Anyone can visit it (no login). Shows: 'All systems operational', "
        "or 'Degraded performance', or 'Major outage'. Used during sales calls to demonstrate "
        "reliability."
    )
    pdf.h2("What's shown")
    pdf.bullet("Overall status banner (green / yellow / red)")
    pdf.bullet("Per-component status (Web, Database, LLM provider, Monitor scraper)")
    pdf.bullet("90-day uptime percentage")
    pdf.bullet("Last 5 incidents (with timestamps and resolutions)")

    # ── 16. WEBHOOKS ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("16. Webhooks - Sending Notifications Elsewhere (/webhooks)")
    pdf.h2("What this is")
    pdf.para(
        "Webhooks let the firm get a notification in their own system (Slack, Jira, WhatsApp "
        "via Glific) every time something happens inside Lex-Indic. For example: every time "
        "a new lead is captured at /try, fire a webhook to the firm's #leads Slack channel."
    )

    pdf.h2("The five events Lex-Indic fires")
    pdf.bullet("analysis.completed - every /analyze call that succeeds")
    pdf.bullet("monitor.digest.ready - when the daily digest is computed")
    pdf.bullet("matter.created - when a new matter is added via /matters")
    pdf.bullet("nalsa.registered - when a NALSA registration is recorded")
    pdf.bullet("lead.captured - when someone submits /try")

    pdf.h2("How to add a webhook")
    pdf.bullet("Go to /webhooks (admin-gated)")
    pdf.bullet("Click 'Add subscription'")
    pdf.bullet("Type the URL the firm wants to POST to (e.g. their Slack incoming-webhook URL)")
    pdf.bullet("Tick the events they want")
    pdf.bullet("Save - you get a wh_xxx ID")

    pdf.h2("Day 22 retry queue")
    pdf.para(
        "If a delivery fails (the firm's endpoint returns 500, or it's offline), the system "
        "doesn't drop it. It writes the failed delivery to a SQLite queue and retries 5 times: "
        "10 seconds, then 1 minute, 5 minutes, 15 minutes, 1 hour. If all 5 fail, it gives up "
        "and writes to deliveries.log. Look at /webhooks/api/deliveries to see the retry queue "
        "depth."
    )

    # ── 17. PRICING ──────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("17. Pricing - Free, NALSA, Firm, Internal")
    pdf.h2("What this is")
    pdf.para(
        "When a lawyer (or anonymous visitor) calls /analyze, the system checks how many "
        "analyses they've done today, and decides whether to allow this one. Four tiers."
    )
    pdf.h2("The four tiers")
    pdf.kv("Free",     "3 analyses per day per IP. Default for anonymous visitors.")
    pdf.kv("NALSA",    "Unlimited free. Activated when their email is in the NALSA registry.")
    pdf.kv("Firm",     "200/day per API key (configurable). For paying firms.")
    pdf.kv("Internal", "No limit. For your own admin / test accounts.")

    pdf.h2("What happens when a user hits the limit")
    pdf.para(
        "The /analyze endpoint returns HTTP 429 (Too Many Requests) with a JSON body like:"
    )
    pdf.set_font("Courier", "", 9); pdf.set_fill_color(*LIGHT_GREY); pdf.set_text_color(*BLACK)
    pdf.multi_cell(avail, 5, _s(
        '{\n'
        '  "error": "Anonymous users get 3 free analyses per day...",\n'
        '  "tier": "free",\n'
        '  "used": 3,\n'
        '  "limit": 3,\n'
        '  "upgrade_url": "/nalsa"\n'
        '}'
    ), fill=True, border=0)
    pdf.ln(3)
    pdf.para(
        "The UI catches this 429 and shows a friendly toast: 'You've hit the free limit. "
        "Register your NALSA panel ID for unlimited free use.' with a 'Register now' button."
    )

    pdf.callout(
        "TIP: For dev, set DISABLE_RATE_LIMITS=1 in your .env. This bypasses all pricing "
        "checks - useful when you're testing the AI itself and don't want to keep hitting "
        "the limit.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 18. CRON ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("18. Cron Jobs - Scheduled Tasks (cron.py)")
    pdf.h2("What this is")
    pdf.para(
        "There are three things that need to run on a schedule, not on a user request. "
        "These live in cron.py:"
    )
    pdf.h2("The three jobs")
    pdf.kv("digest_email",     "07:00 IST daily - runs the SC monitor digest, emails it to all users with watch-matters.")
    pdf.kv("nalsa_csv",         "00:00 IST Sunday - exports the NALSA registry to a dated CSV.")
    pdf.kv("cleanup",           "02:00 IST daily - deletes audit logs older than 90 days.")

    pdf.h2("How to run them")
    pdf.set_font("Courier", "", 9); pdf.set_fill_color(*LIGHT_GREY); pdf.set_text_color(*BLACK)
    pdf.multi_cell(avail, 5, _s(
        "$ python3 cron.py digest_email   # send today's digest emails\n"
        "$ python3 cron.py nalsa_csv      # export NALSA CSV\n"
        "$ python3 cron.py cleanup        # purge old audit logs\n"
        "$ python3 cron.py all            # run all three"
    ), fill=True, border=0)
    pdf.ln(2)

    pdf.h2("In production")
    pdf.para(
        "Add these three lines to /etc/cron.d/lex-indic on your server. Or, on Render.com, "
        "use the cron-job feature and call /cron/digest_email, /cron/nalsa_csv, /cron/cleanup "
        "via HTTP POST (admin-gated)."
    )

    pdf.callout(
        "TIP: All cron jobs accept --dry-run. Use this to verify what will happen before "
        "actually running. For digest_email, --dry-run prints the email body to stdout "
        "instead of sending it.",
        bg=SOFT_GOLD, border=GOLD, font_size=9,
    )

    # ── 19. SMS ─────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("19. SMS and WhatsApp Alerts (sms.py)")
    pdf.h2("What this is")
    pdf.para(
        "India-first push notifications. When a NALSA advocate registers, they get a WhatsApp "
        "welcome. When the SC monitor finds a match in their watch-matter, they get a digest "
        "alert. When a magic-link login is needed, the code can go by SMS instead of email "
        "(faster on Indian mobile networks)."
    )
    pdf.h2("The three providers")
    pdf.kv("stdout",  "Dev mode. Prints to terminal instead of sending. SMS_PROVIDER unset.")
    pdf.kv("msg91",   "India-first SMS/WhatsApp gateway. Requires MSG91_AUTH_KEY env var. DLT-template compliant for TRAI.")
    pdf.kv("twilio",  "Global fallback. Requires TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN.")

    pdf.h2("How to test SMS yourself")
    pdf.bullet("Go to /sms/test (admin-gated)")
    pdf.bullet("Type a phone number (10-digit Indian or +91 prefixed)")
    pdf.bullet("Choose channel: SMS or WhatsApp")
    pdf.bullet("Click 'Send'")
    pdf.bullet("Look at the response - ok:true means it was queued; ok:false means provider error")

    pdf.callout(
        "WARNING: MSG91 requires DLT (Distributed Ledger Technology) template registration in "
        "India - it's a TRAI mandate. The templates in sms.py are placeholders. Before going "
        "live, register each template via MSG91's panel and set the MSG91_TEMPLATE_ID_* env "
        "vars to the assigned IDs.",
        bg=SOFT_RED, border=RED, font_size=9,
    )

    # ── 20. PROBLEMS ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("20. Common Problems and How to Fix Them")
    fixes = [
        ("'AI gave a wrong section number'",
         "The /analyze pipeline is RAG-grounded - it can only cite sections that are in the "
         "knowledge base. If you see a wrong number, it means the section isn't in the KB. "
         "Add it to data/bns_knowledge_base.py and restart the app."),
        ("'/analyze is taking 90 seconds the first time'",
         "ChromaDB cold-starts by re-embedding the entire KB. Run "
         "'python3 tools/prewarm_embeddings.py' once - it caches the embeddings to disk. "
         "Subsequent restarts will be fast."),
        ("'I keep hitting the 3/day limit during testing'",
         "Add DISABLE_RATE_LIMITS=1 to your .env, restart the app. Done."),
        ("'Magic-link email never arrived'",
         "If you're in dev mode (MAIL_PROVIDER=stdout), the code is in your terminal "
         "where you ran python3 app.py. Search for 'Sending login code to'. The 6 digits "
         "appear in that line."),
        ("'Webhook is not delivering'",
         "Look at /webhooks/api/deliveries. If you see 'retry_queue.pending > 0', the system "
         "is retrying. If pending is 0 and the firm still doesn't see it, the firm's endpoint "
         "is probably returning a 2xx but ignoring the body. Hit them with a curl."),
        ("'Hindi UI shows '???' instead of Devanagari'",
         "The Helvetica font that fpdf2 uses by default is latin-1 only. The web UI shows "
         "Hindi correctly (browser fonts handle it). The PDF for Hindi output uses a "
         "different font path (NotoSans-Devanagari). Check that the font file is in static/fonts/."),
        ("'I want to delete a user / lawyer / matter'",
         "There's no UI for delete yet. Use SQL directly: connect to your Postgres (or the "
         "SQLite at outputs/lex.db) and DELETE the row. The dual-backed code reads from "
         "whichever is configured, so your delete is immediately visible."),
        ("'I want to back up everything'",
         "Two locations: (1) outputs/ folder has all JSON files, audit logs, generated PDFs. "
         "(2) outputs/lex.db is the SQLite DB. Just tar both up. For Postgres, use "
         "pg_dump. Daily cron job is on the Q3 2026 roadmap."),
    ]
    for q, a in fixes:
        pdf.h2(q, colour=ORANGE)
        pdf.para(a, size=9)

    # ── 21. GLOSSARY ────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1("21. Glossary - Every Word You Might Not Know")
    gloss = [
        ("BNS",          "Bharatiya Nyaya Sanhita 2023 - India's new penal code, replaced the IPC on 1 July 2024."),
        ("BNSS",         "Bharatiya Nagarik Suraksha Sanhita 2023 - new procedure code, replaced CrPC."),
        ("BSA",          "Bharatiya Sakshya Adhiniyam 2023 - new evidence law, replaced Indian Evidence Act 1872."),
        ("IPC",          "Indian Penal Code 1860 - the old colonial-era penal code, now replaced by BNS."),
        ("NALSA",        "National Legal Services Authority - constitutional body that runs free legal aid."),
        ("SLSA",         "State Legal Services Authority - state-level branch of NALSA. 36 of them across India."),
        ("DLSA",         "District Legal Services Authority - district-level branch."),
        ("DPDP",         "Digital Personal Data Protection Act 2023 - India's GDPR-equivalent."),
        ("SOC 2",        "Service Organization Control 2 - US security certification firms ask for."),
        ("RAG",          "Retrieval-Augmented Generation - the AI only answers from a verified KB; cannot hallucinate."),
        ("ChromaDB",     "Open-source vector database that holds the KB embeddings."),
        ("Gemini 1.5",   "Google's flagship LLM. We use it at temperature 0.2 for precise legal output."),
        ("Flask",        "The Python web framework powering the entire app."),
        ("FIR",          "First Information Report - what police file when a complaint is registered."),
        ("CNR",          "Case Number Record - India's national case identifier on the e-Courts system."),
        ("HMAC",         "Hash-based Message Authentication Code - how we sign session cookies + webhooks."),
        ("DLT template", "Distributed Ledger Technology template - TRAI-mandated SMS template registration in India."),
        ("MSG91",        "India's dominant SMS/WhatsApp gateway provider (~65% market share)."),
        ("Twilio",       "Global SMS/WhatsApp provider, used as fallback for international firms."),
        ("Webhook",      "An HTTP POST sent from our system to a firm's system when something happens."),
        ("Citation badge", "The small gold pill around a BNS section number in the analysis - shows it's verified."),
        ("Verified Sources panel", "The card above the analysis showing the 8 KB entries the AI used."),
        ("Magic link",   "Passwordless login - we email a one-time code instead of asking for a password."),
        ("Audit log",    "outputs/audit/audit-YYYY-MM-DD.log - one JSONL line per /analyze request."),
        ("Salted hash",  "SHA-256 of (salt + plaintext). Used for the story_hash in audit log - irreversible."),
    ]
    for term, defn in gloss:
        pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(*GREEN)
        pdf.cell(35, 6, _s(term))
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*BLACK)
        x = pdf.get_x(); y = pdf.get_y()
        pdf.multi_cell(avail - 35, 5.5, _s(defn))
        pdf.ln(0.5)

    pdf.add_page()
    pdf.h1("That's It!")
    pdf.callout(
        "You now know every page of Lex-Indic, where to click, what each thing does, and "
        "what to do when something breaks. Keep this PDF in your dropbox / iCloud - you can "
        "share it with anyone you onboard to the project later.",
        bg=SOFT_GREEN, border=GREEN, font_size=11, bold_first=True,
    )
    pdf.spacer(10)
    pdf.h2("If you ever forget something:")
    pdf.bullet("Re-read this PDF.")
    pdf.bullet("Read README.md in the project folder.")
    pdf.bullet("Read tests/test_pure.py - it's the closest thing to a working spec.")
    pdf.bullet("Run 'python -m pytest tests/test_pure.py -v' to see every feature in action.")

    pdf.spacer(10)
    pdf.set_font("Helvetica", "I", 10); pdf.set_text_color(*GREY)
    pdf.multi_cell(avail, 6, _s(
        "Generated for personal reference on " + datetime.now().strftime("%d %B %Y") +
        ". Project home: github.com/Yuvraj235/Lex-Indic-legal"
    ), align="C")

    out = OUTPUT_DIR / "03_UserGuide_EasyLanguage.pdf"
    pdf.output(str(out))
    print(f"  [OK] {out.relative_to(OUTPUT_DIR.parent.parent)}")
    return out


# ═══════════════════════════════════════════════════════════════════════════
def main():
    print("Generating Lex-Indic pitch PDFs...")
    print(f"  Output folder: {OUTPUT_DIR}")
    build_sales_pitch_pdf()
    build_technical_deepdive_pdf()
    build_user_guide_pdf()
    print("\nAll three PDFs generated successfully.")
    print(f"Open the folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
