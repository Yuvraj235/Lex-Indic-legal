"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          LEX-INDIC: THE BNS TRANSITION ENGINE — v1.0                        ║
║          Phase 2: Professional PDF Case Brief Generator                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS FILE DOES:
────────────────────
Reads the text output saved by main.py (Phase 1) and converts it into a
professionally formatted, print-ready PDF Case Brief that law firms can:
  - File directly in physical case folders
  - Hand to clients as a first advisory document
  - Present to police and courts as a drafted document

HOW TO USE:
───────────
1. Run main.py first to generate a case analysis text file in outputs/
2. Then run:  python3 pdf_generator.py
3. The PDF is saved to: outputs/CaseBrief_[Date].pdf

To convert a specific file:
   python3 pdf_generator.py outputs/case_analysis_20260304_205234.txt
"""

import sys
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fpdf import FPDF
from fpdf.enums import XPos, YPos

load_dotenv()


# ──────────────────────────────────────────────────────────────────────────────
# LAW-FIRM LETTERHEAD CONFIG (override via .env to white-label the PDF)
# ──────────────────────────────────────────────────────────────────────────────
# Why this exists: a real law firm cannot hand a client a brief stamped
# "Lex-Indic". They need their own name on the cover, header, and disclaimer.
# Set these in .env to white-label the PDF for a specific firm. The engine
# attribution stays in the footer (deliberately — disclaims that the firm
# wrote the AI, which protects them legally).
#
# Example .env:
#   LAW_FIRM_NAME=SINGHANIA & PARTNERS
#   LAW_FIRM_TAGLINE=ADVOCATES & SOLICITORS
#   LAW_FIRM_SUBTITLE=Mumbai · Delhi · Bengaluru
#   LAW_FIRM_DISCLAIMER=This document was prepared as a draft by Singhania & Partners and must be reviewed by the assigned advocate before filing.
LAW_FIRM_NAME       = os.getenv("LAW_FIRM_NAME",       "LEX-INDIC")
LAW_FIRM_TAGLINE    = os.getenv("LAW_FIRM_TAGLINE",    "BNS TRANSITION ENGINE")
LAW_FIRM_SUBTITLE   = os.getenv("LAW_FIRM_SUBTITLE",   "AI-Powered Junior Associate for Indian Law Firms")
LAW_FIRM_HEADER     = os.getenv("LAW_FIRM_HEADER",     f"{LAW_FIRM_NAME}  |  BNS Case Brief  |  CONFIDENTIAL")
LAW_FIRM_DISCLAIMER = os.getenv(
    "LAW_FIRM_DISCLAIMER",
    "Lex-Indic is not a law firm and this document does not constitute legal advice.",
)


# ──────────────────────────────────────────────────────────────────────────────
# BRAND COLOURS  (change these to match the law firm's branding)
# ──────────────────────────────────────────────────────────────────────────────
COLOUR = {
    "navy":      (15,  40,  80),    # Deep navy — headers, cover page
    "gold":      (180, 140,  40),   # Gold — accent, dividers
    "red":       (180,  30,  30),   # Red — advisory panels
    "red_light": (255, 235, 235),   # Light red — advisory background
    "blue":      (30,  80, 160),    # Blue — legal analysis headers
    "blue_light":(230, 240, 255),   # Light blue — legal analysis background
    "green":     (20, 100,  50),    # Green — FIR headers
    "green_light":(225, 245, 230),  # Light green — FIR background
    "teal":      (20, 110, 110),    # Teal — legal notice headers
    "teal_light":(225, 245, 245),   # Light teal — legal notice background
    "purple":    (90,  30, 120),    # Purple — case strategy
    "purple_light":(245, 230, 255), # Light purple — strategy background
    "orange":    (160,  80,   0),   # Orange — police report
    "orange_light":(255, 242, 220), # Light orange — police report background
    "grey":      (100, 100, 100),   # Medium grey — body text
    "light_grey":(245, 245, 245),   # Panel backgrounds
    "white":     (255, 255, 255),
    "black":     (0,   0,   0),
}


# ──────────────────────────────────────────────────────────────────────────────
# TEXT SANITIZER (latin-1 safe — Helvetica font limitation)
# ──────────────────────────────────────────────────────────────────────────────
_CHAR_MAP = {
    "\u2014": "-",   # em dash
    "\u2013": "-",   # en dash
    "\u2019": "'",   # right single quote
    "\u2018": "'",   # left single quote
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u2022": "-",   # bullet
    "\u2026": "...", # ellipsis
    "\u2605": "*",   # black star
    "\u26a0": "[!]", # warning sign
    "\u2713": "OK",  # check mark
    "\u00b7": ".",   # middle dot (actually latin-1 OK, keep as-is)
}

def _s(text: str) -> str:
    """Sanitize text to latin-1 safe characters for Helvetica font."""
    for char, replacement in _CHAR_MAP.items():
        text = text.replace(char, replacement)
    # Fallback: replace any remaining non-latin-1 character with "?"
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION PARSER
# ──────────────────────────────────────────────────────────────────────────────
def parse_sections(text: str) -> dict:
    """
    Parses the 6-section text output from main.py into a dictionary.
    Returns: { 'client_statement': str, 'section_1': str, ..., 'section_6': str }
    """
    result = {}

    # ── Extract client statement ──────────────────────────────────────────────
    cs_match = re.search(
        r"CLIENT'S STATEMENT:\s*\n(.*?)(?:={10,}|━{10,}|SECTION 1)",
        text, re.DOTALL
    )
    if cs_match:
        result["client_statement"] = cs_match.group(1).strip()
    else:
        result["client_statement"] = "Client statement not found in report."

    # ── Extract generated date ────────────────────────────────────────────────
    date_match = re.search(r"Generated:\s*(.+)", text)
    result["generated"] = date_match.group(1).strip() if date_match else datetime.now().strftime("%d %B %Y, %H:%M:%S")

    # ── Extract each numbered section ─────────────────────────────────────────
    section_patterns = {
        "section_1": r"SECTION 1:\s*IMMEDIATE CLIENT ADVISORY",
        "section_2": r"SECTION 2:\s*LEGAL ANALYSIS UNDER BNS 2023",
        "section_3": r"SECTION 3:\s*CASE STRATEGY.*?ASSESSMENT",
        "section_4": r"SECTION 4:\s*DRAFT FIRST INFORMATION REPORT.*?\(FIR\)",
        "section_5": r"SECTION 5:\s*DRAFT LEGAL NOTICE",
        "section_6": r"SECTION 6:\s*POLICE HELP REPORT",
    }

    # Find positions of all section headings
    positions = {}
    for key, pattern in section_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            positions[key] = match.start()

    sorted_sections = sorted(positions.items(), key=lambda x: x[1])

    for i, (key, start_pos) in enumerate(sorted_sections):
        # Content ends where the next section begins (or at end of text)
        if i + 1 < len(sorted_sections):
            end_pos = sorted_sections[i + 1][1]
        else:
            end_pos = len(text)

        raw = text[start_pos:end_pos]
        # Strip the heading line and the ━━━ divider lines
        lines = raw.split("\n")
        content_lines = []
        skip_next = False
        for j, line in enumerate(lines):
            if j == 0:               # skip heading line
                continue
            if re.match(r"^[━=─]{5,}", line.strip()):
                continue             # skip divider lines
            content_lines.append(line)

        result[key] = "\n".join(content_lines).strip()

    # Fill missing sections with a placeholder
    for key in section_patterns:
        if key not in result:
            result[key] = f"[{key.upper().replace('_', ' ')} - not found in report]"

    return result


# ──────────────────────────────────────────────────────────────────────────────
# PDF CLASS
# ──────────────────────────────────────────────────────────────────────────────
class LexIndicPDF(FPDF):
    """
    Custom FPDF subclass for Lex-Indic Case Briefs.
    Handles headers, footers, page numbering, and watermarks automatically.
    """

    def __init__(self, generated_date: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.generated_date = generated_date
        self.set_margins(left=18, top=18, right=18)
        self.set_auto_page_break(auto=True, margin=20)
        self.is_cover_page = False  # Set True for cover page (no header/footer)

    # ── Running header on every page (except cover) ───────────────────────────
    def header(self):
        if self.is_cover_page:
            return
        if self.page_no() <= 1:
            return
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*COLOUR["navy"])
        self.set_fill_color(*COLOUR["light_grey"])
        self.rect(0, 0, 210, 12, style="F")
        self.set_y(3)
        self.cell(0, 6, _s(LAW_FIRM_HEADER), align="C",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*COLOUR["gold"])
        self.set_line_width(0.4)
        self.line(18, 13, 192, 13)
        self.set_y(16)

    # ── Running footer on every page (except cover) ───────────────────────────
    def footer(self):
        if self.is_cover_page:
            return
        if self.page_no() <= 1:
            return
        self.set_y(-14)
        self.set_draw_color(*COLOUR["gold"])
        self.set_line_width(0.3)
        self.line(18, self.get_y(), 192, self.get_y())
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*COLOUR["grey"])
        self.cell(0, 5,
                  f"Generated by Lex-Indic BNS Transition Engine  |  {self.generated_date}  |  Page {self.page_no()}",
                  align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── "CONFIDENTIAL" diagonal watermark ─────────────────────────────────────
    def add_watermark(self):
        """Adds a faint diagonal CONFIDENTIAL watermark to the current page."""
        with self.rotation(45, x=105, y=148.5):
            self.set_font("Helvetica", "B", 52)
            self.set_text_color(220, 220, 220)
            self.text(x=20, y=155, text="CONFIDENTIAL")
        self.set_text_color(*COLOUR["black"])

    # ── Coloured section title banner ─────────────────────────────────────────
    def section_banner(self, title: str, subtitle: str = "", color_key: str = "navy"):
        """Draws a full-width coloured banner for section headings."""
        bg = COLOUR[color_key]
        self.set_fill_color(*bg)
        self.set_text_color(*COLOUR["white"])
        self.set_font("Helvetica", "B", 13)
        banner_h = 10 if not subtitle else 8
        self.cell(0, banner_h, f"  {title}", fill=True,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.set_font("Helvetica", "", 8)
            self.set_fill_color(*bg)
            self.cell(0, 6, f"  {subtitle}", fill=True,
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*COLOUR["black"])
        self.ln(3)

    # ── Coloured info panel (background fill + content) ───────────────────────
    def info_panel(self, content: str, bg_color_key: str = "light_grey",
                   text_color_key: str = "black", font_size: int = 10,
                   font_style: str = ""):
        """Renders multi-line text inside a coloured rounded panel."""
        self.set_fill_color(*COLOUR[bg_color_key])
        self.set_text_color(*COLOUR[text_color_key])
        self.set_font("Helvetica", font_style, font_size)

        # Measure content height
        lines = content.split("\n")
        line_height = font_size * 0.45 + 1.0
        total_h = len(lines) * line_height + 6

        x = self.get_x()
        y = self.get_y()
        w = self.epw  # effective page width

        self.rect(x, y, w, total_h, style="F")
        self.set_xy(x + 3, y + 3)

        for line in lines:
            self.cell(0, line_height, line.rstrip(),
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(y + total_h + 2)
        self.set_text_color(*COLOUR["black"])

    # ── Body text paragraph ───────────────────────────────────────────────────
    def body_text(self, text: str, font_size: int = 10, indent: int = 0,
                  font_style: str = "", color_key: str = "black"):
        """Writes multi-line body text with line-wrapping."""
        self.set_font("Helvetica", font_style, font_size)
        self.set_text_color(*COLOUR[color_key])
        self.set_left_margin(18 + indent)
        self.multi_cell(0, 5.5, _s(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_left_margin(18)
        self.ln(1)

    # ── Gold horizontal divider ───────────────────────────────────────────────
    def gold_divider(self):
        self.set_draw_color(*COLOUR["gold"])
        self.set_line_width(0.5)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(3)


# ──────────────────────────────────────────────────────────────────────────────
# PAGE BUILDERS
# ──────────────────────────────────────────────────────────────────────────────

def build_cover_page(pdf: LexIndicPDF, sections: dict):
    """Page 1 — Cover page with logo, title, client info, and CONFIDENTIAL stamp."""
    pdf.add_page()
    pdf.is_cover_page = True

    # ── Full navy background top half ─────────────────────────────────────────
    pdf.set_fill_color(*COLOUR["navy"])
    pdf.rect(0, 0, 210, 140, style="F")

    # ── Gold accent stripe ────────────────────────────────────────────────────
    pdf.set_fill_color(*COLOUR["gold"])
    pdf.rect(0, 140, 210, 3, style="F")

    # ── Logo area (text-based since no image asset) ───────────────────────────
    # Auto-shrink the firm-name font if a long firm name was configured, so a
    # name like "Khaitan & Co — Advocates" doesn't overflow the page width.
    pdf.set_y(28)
    pdf.set_text_color(*COLOUR["gold"])
    name_len = len(LAW_FIRM_NAME)
    if name_len <= 12:
        firm_font_size = 36
    elif name_len <= 22:
        firm_font_size = 28
    else:
        firm_font_size = 22
    pdf.set_font("Helvetica", "B", firm_font_size)
    pdf.cell(0, 16, _s(LAW_FIRM_NAME), align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(0, 7, _s(LAW_FIRM_TAGLINE), align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, _s(LAW_FIRM_SUBTITLE),
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Main document title ───────────────────────────────────────────────────
    pdf.set_y(90)
    pdf.set_text_color(*COLOUR["white"])
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 12, "CASE ANALYSIS BRIEF", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(0, 7,
             "Bharatiya Nyaya Sanhita (BNS) 2023  ·  Legal Triage & Document Drafting",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── White bottom card area ────────────────────────────────────────────────
    pdf.set_fill_color(*COLOUR["white"])
    pdf.rect(0, 143, 210, 297 - 143, style="F")

    # ── CONFIDENTIAL red stamp ────────────────────────────────────────────────
    pdf.set_y(152)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*COLOUR["white"])
    pdf.set_fill_color(*COLOUR["red"])
    pdf.cell(0, 9, "  ***  CONFIDENTIAL - FOR AUTHORISED PERSONNEL ONLY  ***",
             fill=True, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Report meta card ──────────────────────────────────────────────────────
    pdf.set_y(172)
    card_x = 28
    card_w = 154
    pdf.set_fill_color(*COLOUR["light_grey"])
    pdf.rect(card_x, pdf.get_y(), card_w, 70, style="F")

    def meta_row(label: str, value: str):
        pdf.set_x(card_x + 5)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*COLOUR["navy"])
        pdf.cell(40, 8, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*COLOUR["grey"])
        pdf.cell(card_w - 50, 8, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(pdf.get_y() + 6)
    meta_row("Generated:",     sections.get("generated", datetime.now().strftime("%d %B %Y")))
    meta_row("Engine:",        "Lex-Indic BNS Transition Engine v1.0")
    meta_row("AI Model:",      "Groq Llama-3.3-70B  +  Gemini Embeddings")
    meta_row("Legal Framework:", "Bharatiya Nyaya Sanhita (BNS), 2023")
    meta_row("Status:",        "Draft - Must be reviewed by a licensed Advocate")
    meta_row("Classification:", "CONFIDENTIAL - Attorney-Client Privilege")

    # ── Bottom instruction ────────────────────────────────────────────────────
    pdf.set_y(255)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*COLOUR["grey"])
    pdf.cell(0, 5,
             "This document was generated by AI and must be reviewed and certified by a licensed Advocate before use.",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5,
             _s(LAW_FIRM_DISCLAIMER),
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Page number suppressed on cover ──────────────────────────────────────
    pdf.is_cover_page = False


def build_advisory_page(pdf: LexIndicPDF, sections: dict):
    """Page 2 — Immediate Client Advisory in red panels (urgent safety steps)."""
    pdf.add_page()
    pdf.add_watermark()

    pdf.section_banner(
        "SECTION 1: IMMEDIATE CLIENT ADVISORY",
        subtitle="Urgent safety and evidence preservation steps - Take action NOW",
        color_key="red"
    )

    advisory_text = _s(sections.get("section_1", ""))

    # Extract numbered items and render each as a red card
    items = re.split(r"\n(?=\d+[\.\)])", advisory_text)
    for item in items:
        item = item.strip()
        if not item:
            continue

        # Check if item starts with a number (it's a numbered step)
        num_match = re.match(r"^(\d+)[\.\)]\s*\*?\*?(.+?)(?:\*\*)?$", item, re.DOTALL)
        if num_match:
            step_num = num_match.group(1)
            step_text = num_match.group(2).strip()
            # Remove markdown bold markers
            step_text = re.sub(r"\*\*(.+?)\*\*", r"\1", step_text)
            step_text = step_text.replace("**", "")

            # Step number circle (filled)
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.set_fill_color(*COLOUR["red"])
            pdf.ellipse(x, y + 0.5, 7, 7, style="F")
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*COLOUR["white"])
            pdf.set_xy(x, y + 0.5)
            pdf.cell(7, 7, step_num, align="C")

            # Step text
            pdf.set_text_color(*COLOUR["black"])
            pdf.set_font("Helvetica", "", 10)
            pdf.set_xy(x + 10, y)
            pdf.multi_cell(pdf.epw - 10, 5.5, step_text,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

            # Thin red underline
            pdf.set_draw_color(*COLOUR["red"])
            pdf.set_line_width(0.2)
            pdf.line(18, pdf.get_y(), 192, pdf.get_y())
            pdf.ln(3)
        else:
            # Non-numbered paragraph
            item_clean = re.sub(r"\*\*(.+?)\*\*", r"\1", item).replace("**", "")
            pdf.body_text(item_clean)


def build_legal_analysis_page(pdf: LexIndicPDF, sections: dict):
    """Pages 3-4 — BNS Legal Analysis with charge details."""
    pdf.add_page()
    pdf.add_watermark()

    pdf.section_banner(
        "SECTION 2: LEGAL ANALYSIS UNDER BNS 2023",
        subtitle="Applicable charges, punishments, and IPC transition notes",
        color_key="blue"
    )

    analysis_text = _s(sections.get("section_2", ""))

    # Try to parse individual charge blocks (each starting with a BNS section)
    # Pattern: lines starting with "- **BNS Section" or "**BNS"
    charge_blocks = re.split(r"\n(?=[-•]\s*\*\*BNS|\n\*\*BNS)", analysis_text)

    if len(charge_blocks) > 1:
        for block in charge_blocks:
            block = block.strip()
            if not block:
                continue

            # Extract section heading (bold text at start)
            heading_match = re.match(r"[-•]?\s*\*\*(.+?)\*\*[:\s]*(.*)", block, re.DOTALL)
            if heading_match:
                heading = heading_match.group(1).strip()
                rest = heading_match.group(2).strip()

                # Draw heading as blue banner
                pdf.set_fill_color(*COLOUR["blue_light"])
                pdf.set_text_color(*COLOUR["blue"])
                pdf.set_font("Helvetica", "B", 11)
                h = 8
                pdf.cell(0, h, f"  {heading}", fill=True,
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                # Draw rest as body text
                rest_clean = re.sub(r"\*\*(.+?)\*\*", r"\1", rest)
                rest_clean = rest_clean.replace("**", "")
                pdf.set_fill_color(*COLOUR["white"])
                pdf.set_text_color(*COLOUR["grey"])
                pdf.set_font("Helvetica", "", 9.5)
                pdf.multi_cell(0, 5, rest_clean.strip(),
                               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(3)
            else:
                # Plain block — render as body text
                block_clean = re.sub(r"\*\*(.+?)\*\*", r"\1", block)
                block_clean = block_clean.replace("**", "").strip()
                if block_clean:
                    pdf.body_text(block_clean, font_size=9.5)
    else:
        # Fallback: render raw text with markdown cleanup
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", analysis_text)
        clean = clean.replace("**", "")
        pdf.body_text(clean, font_size=10)


def build_strategy_page(pdf: LexIndicPDF, sections: dict):
    """Page 5 — Case Strategy & Strength Assessment."""
    pdf.add_page()
    pdf.add_watermark()

    pdf.section_banner(
        "SECTION 3: CASE STRATEGY & STRENGTH ASSESSMENT",
        subtitle="Evidence requirements, defence predictions, and recommended approach",
        color_key="purple"
    )

    strategy_text = _s(sections.get("section_3", ""))

    # Detect case strength keyword for highlighted banner
    strength = "UNKNOWN"
    if "STRONG" in strategy_text.upper():
        strength = "STRONG"
        strength_bg = COLOUR["green"]
    elif "MODERATE" in strategy_text.upper():
        strength = "MODERATE"
        strength_bg = COLOUR["orange"]
    else:
        strength = "WEAK"
        strength_bg = (160, 40, 40)

    # Strength badge
    pdf.set_fill_color(*strength_bg)
    pdf.set_text_color(*COLOUR["white"])
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, f"  CASE STRENGTH: {strength}", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Render rest of strategy
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", strategy_text)
    clean = clean.replace("**", "")

    # Split into sub-sections by bullet or dash
    lines = clean.split("\n")
    for line in lines:
        line = line.rstrip()
        if not line:
            pdf.ln(1)
            continue
        if line.startswith(("* ", "- ", "• ")):
            bullet_text = line[2:].strip()
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.set_fill_color(*COLOUR["purple"])
            pdf.ellipse(x + 1, y + 2, 3, 3, style="F")
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*COLOUR["black"])
            pdf.set_xy(x + 6, y)
            pdf.multi_cell(pdf.epw - 6, 5.5, bullet_text,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif line.startswith(("  * ", "  - ")):
            sub_text = line.strip()[2:]
            pdf.set_font("Helvetica", "I", 9.5)
            pdf.set_text_color(*COLOUR["grey"])
            pdf.set_x(24)
            pdf.multi_cell(pdf.epw - 6, 5, sub_text,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*COLOUR["black"])
            pdf.multi_cell(0, 5.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_fir_page(pdf: LexIndicPDF, sections: dict):
    """Pages 6-7 — Draft FIR in print-ready court format."""
    pdf.add_page()
    pdf.add_watermark()

    pdf.section_banner(
        "SECTION 4: DRAFT FIRST INFORMATION REPORT (FIR)",
        subtitle="Ready to file - Replace ALL CAPS placeholders before submission",
        color_key="green"
    )

    # Official document styling note
    pdf.set_fill_color(*COLOUR["green_light"])
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*COLOUR["green"])
    pdf.cell(0, 7,
             "  [!]  Draft document - must be reviewed and signed by the complainant in the presence of an Advocate",
             fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    fir_text = _s(sections.get("section_4", ""))
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", fir_text)
    clean = clean.replace("**", "")

    # Render in monospace-like style (Courier = court document feel)
    lines = clean.split("\n")
    for line in lines:
        line = line.rstrip()
        if not line:
            pdf.ln(2)
            continue
        # Highlight placeholder fields in ALL CAPS brackets
        if re.search(r"\[[A-Z ]+\]", line):
            # Split line into parts, highlight placeholders
            parts = re.split(r"(\[[A-Z ]+\])", line)
            pdf.set_x(18)
            for part in parts:
                if re.match(r"\[[A-Z ]+\]", part):
                    pdf.set_font("Courier", "B", 9)
                    pdf.set_text_color(*COLOUR["red"])
                else:
                    pdf.set_font("Courier", "", 9)
                    pdf.set_text_color(*COLOUR["black"])
                if part:
                    pdf.cell(pdf.get_string_width(part) + 0.5, 5, part)
            pdf.ln(5)
        else:
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(*COLOUR["black"])
            pdf.multi_cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Signature block ───────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.gold_divider()
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*COLOUR["navy"])
    pdf.cell(95, 6, "Signature of Complainant", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(80, 6, "Date & Place", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_draw_color(*COLOUR["grey"])
    pdf.set_line_width(0.3)
    pdf.line(18, pdf.get_y(), 100, pdf.get_y())
    pdf.line(115, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*COLOUR["grey"])
    pdf.cell(95, 5, "(Name & Signature)", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(80, 5, "(Date / Place)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_notice_page(pdf: LexIndicPDF, sections: dict):
    """Pages 8-9 — Draft Legal Notice in letterhead format."""
    pdf.add_page()
    pdf.add_watermark()

    pdf.section_banner(
        "SECTION 5: DRAFT LEGAL NOTICE",
        subtitle="Formal legal notice from Advocate - Replace ALL CAPS placeholders before sending",
        color_key="teal"
    )

    notice_text = _s(sections.get("section_5", ""))
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", notice_text)
    clean = clean.replace("**", "")

    lines = clean.split("\n")
    for line in lines:
        line = line.rstrip()
        if not line:
            pdf.ln(2)
            continue

        is_heading = (
            line.startswith("Subject:") or
            line.startswith("Date:") or
            line.startswith("To:") or
            line.startswith("From:") or
            line.startswith("Sender:") or
            line.startswith("Addressee:") or
            line.startswith("Notice") or
            line.startswith("Dear")
        )

        if re.search(r"\[[A-Z ]+\]", line):
            parts = re.split(r"(\[[A-Z ]+\])", line)
            pdf.set_x(18)
            for part in parts:
                if re.match(r"\[[A-Z ]+\]", part):
                    pdf.set_font("Helvetica", "B", 9.5)
                    pdf.set_text_color(*COLOUR["red"])
                else:
                    style = "B" if is_heading else ""
                    pdf.set_font("Helvetica", style, 9.5)
                    pdf.set_text_color(*COLOUR["black"])
                if part:
                    pdf.cell(pdf.get_string_width(part) + 0.5, 5.5, part)
            pdf.ln(5.5)
        elif is_heading:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*COLOUR["navy"])
            pdf.multi_cell(0, 5.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(*COLOUR["black"])
            pdf.multi_cell(0, 5.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Advocate signature block ──────────────────────────────────────────────
    pdf.ln(6)
    pdf.gold_divider()
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*COLOUR["navy"])
    pdf.cell(95, 6, "Signature of Advocate", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(80, 6, "Office Stamp", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_draw_color(*COLOUR["grey"])
    pdf.set_line_width(0.3)
    pdf.line(18, pdf.get_y(), 100, pdf.get_y())
    pdf.rect(115, pdf.get_y() - 10, 77, 20)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*COLOUR["grey"])
    pdf.cell(95, 5, "(Advocate Name, Bar Council Reg. No.)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_police_report_page(pdf: LexIndicPDF, sections: dict):
    """Page 10 — Police Help Report in plain-language narrative."""
    pdf.add_page()
    pdf.add_watermark()

    pdf.section_banner(
        "SECTION 6: POLICE HELP REPORT",
        subtitle="Plain-language companion document for the Station House Officer (SHO)",
        color_key="orange"
    )

    report_text = _s(sections.get("section_6", ""))
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", report_text)
    clean = clean.replace("**", "")

    # Detect danger level
    danger = "UNKNOWN"
    if "HIGH" in clean.upper():
        danger = "HIGH"
        danger_bg = COLOUR["red"]
    elif "MEDIUM" in clean.upper():
        danger = "MEDIUM"
        danger_bg = COLOUR["orange"]
    else:
        danger = "LOW"
        danger_bg = COLOUR["green"]

    # Danger level badge
    pdf.set_fill_color(*danger_bg)
    pdf.set_text_color(*COLOUR["white"])
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"  [!]  CURRENT DANGER LEVEL: {danger}", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    lines = clean.split("\n")
    for line in lines:
        line = line.rstrip()
        if not line:
            pdf.ln(1)
            continue

        is_subheading = line.startswith(("**Incident Timeline", "**Current Danger",
                                          "**Immediate Police", "**Witness",
                                          "**Evidence", "**Victim's",
                                          "Incident Timeline", "Current Danger",
                                          "Immediate Police", "Witness Information",
                                          "Evidence to Seize", "Victim's Current"))

        if is_subheading:
            pdf.ln(2)
            pdf.set_fill_color(*COLOUR["orange_light"])
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*COLOUR["orange"])
            pdf.cell(0, 7, f"  {line.strip('*').strip()}", fill=True,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif line.startswith(("- ", "* ", "• ")):
            bullet_text = line[2:].strip()
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.set_fill_color(*COLOUR["orange"])
            pdf.rect(x + 1, y + 1.5, 2.5, 2.5, style="F")
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*COLOUR["black"])
            pdf.set_xy(x + 6, y)
            pdf.multi_cell(pdf.epw - 6, 5.5, bullet_text,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            if re.search(r"\[[A-Z ]+\]", line):
                parts = re.split(r"(\[[A-Z ]+\])", line)
                pdf.set_x(18)
                for part in parts:
                    if re.match(r"\[[A-Z ]+\]", part):
                        pdf.set_font("Helvetica", "B", 9.5)
                        pdf.set_text_color(*COLOUR["red"])
                    else:
                        pdf.set_font("Helvetica", "", 9.5)
                        pdf.set_text_color(*COLOUR["black"])
                    if part:
                        pdf.cell(pdf.get_string_width(part) + 0.5, 5.5, part)
                pdf.ln(5.5)
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(*COLOUR["black"])
                pdf.multi_cell(0, 5.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_disclaimer_page(pdf: LexIndicPDF):
    """Final page — Disclaimer, tech explanation, and contact."""
    pdf.add_page()

    # Navy top bar
    pdf.set_fill_color(*COLOUR["navy"])
    pdf.rect(0, 0, 210, 30, style="F")
    pdf.set_y(8)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*COLOUR["white"])
    pdf.cell(0, 10, "IMPORTANT DISCLAIMER", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(0, 6, "Please read before using this document", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(38)
    pdf.set_text_color(*COLOUR["black"])

    disclaimer_sections = [
        (
            "LEGAL DISCLAIMER",
            COLOUR["red_light"],
            COLOUR["red"],
            """This document was generated by Lex-Indic, an AI-powered legal research tool.
It is NOT a substitute for advice from a licensed Advocate enrolled with the Bar Council of India.

The contents of this document:
  - Have NOT been reviewed or approved by a licensed legal practitioner
  - May contain errors, omissions, or outdated information
  - Cannot be relied upon as legal advice in any proceedings
  - Must be reviewed, amended, and approved by a qualified Advocate before use

Under the Advocates Act, 1961, only enrolled Advocates may practise law in India.
Using this document without Advocate review may result in adverse legal consequences.""",
        ),
        (
            "HOW THIS DOCUMENT WAS GENERATED",
            COLOUR["blue_light"],
            COLOUR["blue"],
            """Lex-Indic uses a Retrieval-Augmented Generation (RAG) architecture:

  1. A curated knowledge base of BNS 2023 sections, IPC-BNS mappings, and
     Supreme Court landmark cases is loaded into ChromaDB (a vector database).

  2. The client's statement is converted into a mathematical embedding using
     Google Gemini's embedding model, and the most relevant legal sections
     are retrieved from the knowledge base.

  3. The retrieved sections + client facts are sent to Groq's Llama-3.3-70B
     large language model, which generates this analysis.

  4. The AI is instructed to ONLY cite sections provided from the knowledge
     base, reducing (but not eliminating) the risk of hallucinated citations.""",
        ),
        (
            "ABOUT LEX-INDIC",
            COLOUR["light_grey"],
            COLOUR["navy"],
            """Lex-Indic: The BNS Transition Engine is built to help Indian law firms
rapidly adapt to the new Bharatiya Nyaya Sanhita (BNS) 2023, which replaced
the Indian Penal Code (IPC) 1860 with effect from 01 July 2024.

For queries, customisation, or licensing:
  - Engine Version: Lex-Indic v1.0
  - Legal Framework: BNS 2023 (effective 01 July 2024)
  - AI Models: Groq Llama-3.3-70B (generation) + Gemini Embedding-001 (search)""",
        ),
    ]

    for title, bg, title_color, content in disclaimer_sections:
        pdf.set_fill_color(*title_color)
        pdf.set_text_color(*COLOUR["white"])
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 8, f"  {title}", fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_fill_color(*bg)
        pdf.set_text_color(*COLOUR["black"])
        pdf.set_font("Helvetica", "", 9)
        x = pdf.get_x()
        y = pdf.get_y()
        lines = content.strip().split("\n")
        total_h = len(lines) * 5 + 6
        pdf.rect(x, y, pdf.epw, total_h, style="F")
        pdf.set_xy(x + 4, y + 3)
        for line in lines:
            pdf.set_x(22)
            pdf.cell(0, 5, _s(line.rstrip()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_y(y + total_h + 3)
        pdf.ln(1)

    # Footer stamp
    pdf.set_y(270)
    pdf.set_fill_color(*COLOUR["navy"])
    pdf.rect(0, 270, 210, 30, style="F")
    pdf.set_y(274)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*COLOUR["gold"])
    pdf.cell(0, 6, "LEX-INDIC  |  BNS Transition Engine  |  © 2024-2026",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(0, 5,
             "Generated by AI under attorney supervision. All BNS citations are sourced from "
             "indiacode.nic.in. Not a substitute for legal advice.",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────────────────────────────────
def generate_pdf(input_txt_path: str) -> str:
    """
    Reads a Lex-Indic text output file and generates a professional PDF Case Brief.

    Args:
        input_txt_path: Path to the case_analysis_*.txt file from main.py

    Returns:
        Path to the generated PDF file
    """
    # ── Read the text file ────────────────────────────────────────────────────
    txt_path = Path(input_txt_path)
    if not txt_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_txt_path}")

    print(f"  Reading: {txt_path.name}")
    with open(txt_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # ── Parse into sections ───────────────────────────────────────────────────
    print("  Parsing sections...")
    sections = parse_sections(raw_text)
    print(f"  Parsed: {sum(1 for k in sections if k.startswith('section_'))} sections found")

    # ── Create PDF ────────────────────────────────────────────────────────────
    print("  Building PDF pages...")
    pdf = LexIndicPDF(generated_date=sections.get("generated", ""))

    build_cover_page(pdf, sections)
    print("    ✓ Cover page")

    build_advisory_page(pdf, sections)
    print("    ✓ Immediate Advisory (Page 2)")

    build_legal_analysis_page(pdf, sections)
    print("    ✓ BNS Legal Analysis (Pages 3-4)")

    build_strategy_page(pdf, sections)
    print("    ✓ Case Strategy (Page 5)")

    build_fir_page(pdf, sections)
    print("    ✓ Draft FIR (Pages 6-7)")

    build_notice_page(pdf, sections)
    print("    ✓ Draft Legal Notice (Pages 8-9)")

    build_police_report_page(pdf, sections)
    print("    ✓ Police Help Report (Page 10)")

    build_disclaimer_page(pdf)
    print("    ✓ Disclaimer (Final page)")

    # ── Save PDF ──────────────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"CaseBrief_{timestamp}.pdf"

    pdf.output(str(output_path))
    return str(output_path)


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   LEX-INDIC  —  PDF Case Brief Generator  (Phase 2)     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # ── Determine input file ──────────────────────────────────────────────────
    if len(sys.argv) > 1:
        # File path provided as command-line argument
        input_file = sys.argv[1]
    else:
        # Auto-select the most recent case_analysis_*.txt in outputs/
        output_dir = Path("outputs")
        txt_files = sorted(output_dir.glob("case_analysis_*.txt"), reverse=True)
        if not txt_files:
            print("ERROR: No case analysis files found in outputs/")
            print("Run main.py first to generate a case analysis, then run this script.")
            sys.exit(1)
        input_file = str(txt_files[0])
        print(f"  Auto-selected latest case file: {Path(input_file).name}")

    print()

    try:
        output_pdf = generate_pdf(input_file)
        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║                  PDF GENERATED SUCCESSFULLY              ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║  File: {output_pdf:<50} ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print("║  Contents:                                               ║")
        print("║    Page 1   — Cover Page (Confidential stamp)            ║")
        print("║    Page 2   — Immediate Client Advisory                  ║")
        print("║    Pages 3-4 — BNS Legal Analysis                        ║")
        print("║    Page 5   — Case Strategy & Strength Assessment        ║")
        print("║    Pages 6-7 — Draft FIR (Print-ready)                   ║")
        print("║    Pages 8-9 — Draft Legal Notice (Letterhead format)    ║")
        print("║    Page 10  — Police Help Report                         ║")
        print("║    Page 11  — Disclaimer                                 ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print("║  IMPORTANT: Review with a licensed Advocate before use.  ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
