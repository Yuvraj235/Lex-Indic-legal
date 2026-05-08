"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          LEX-INDIC: THE BNS TRANSITION ENGINE — v1.0                        ║
║          Phase 3: Flask Web Application                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

HOW TO RUN:
    python3 app.py
    Then open: http://localhost:5000

ROUTES:
    GET  /                  — Main page (intake form + results)
    POST /analyze           — Run legal triage, returns JSON
    GET  /history           — Returns list of past cases as JSON
    GET  /download/<fname>  — Download a generated PDF
"""

import os
import re
import sys
import time
import json
import base64
import textwrap
from datetime import datetime
from pathlib import Path
from io import BytesIO

import pdfplumber
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

# ── Import pipeline functions from main.py ────────────────────────────────────
from main import (
    configure_gemini_embeddings,
    configure_groq,
    build_rag_knowledge_base,
    retrieve_relevant_sections,
    build_legal_prompt,
    LEXI_SYSTEM_PROMPT,
    save_raw_output,
)
# Used by the RAG-grounded /chat endpoint to search the same KB as /analyze
from main import _get_embedding_with_cache, _load_embedding_cache
from pdf_generator import generate_pdf, parse_sections

# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# ── Global state: build the knowledge base ONCE at startup ───────────────────
# This avoids re-embedding 79 documents on every request (would be very slow)
print("\n  Lex-Indic Web Server — Starting up...")
print("  Loading BNS Legal Knowledge Base... (first time is slow, ~30s)")

configure_gemini_embeddings()
groq_client = configure_groq()
rag_collection = build_rag_knowledge_base()

print("  Knowledge Base ready. Server is live.\n")


# ── File extraction helpers ───────────────────────────────────────────────────

def extract_pdf_text(file_stream) -> str:
    """Extract text from an uploaded PDF (up to 15 pages)."""
    try:
        with pdfplumber.open(file_stream) as pdf:
            pages = []
            for page in pdf.pages[:15]:
                t = page.extract_text()
                if t:
                    pages.append(t.strip())
        return "\n\n".join(pages) if pages else "[No readable text found in PDF]"
    except Exception as e:
        return f"[PDF extraction failed: {str(e)[:120]}]"


def extract_image_text(file_bytes: bytes, mime_type: str) -> str:
    """Use Gemini Vision to extract text and describe an image as legal evidence."""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([
            "You are a legal document analyst. This image is evidence in an Indian legal case. "
            "Extract ALL visible text verbatim. Then describe any relevant visual information "
            "(injuries, documents, screenshots of messages, receipts, etc.) in precise detail.",
            {"mime_type": mime_type, "data": base64.b64encode(file_bytes).decode()},
        ])
        return response.text.strip()
    except Exception as e:
        return f"[Image analysis failed: {str(e)[:120]}]"


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 1: Main page
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 2: Run legal triage — the core API endpoint
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Receives client story as JSON, runs the full legal pipeline, and returns:
    {
        "sections": { "section_1": "...", ..., "section_6": "..." },
        "client_statement": "...",
        "pdf_filename": "CaseBrief_TIMESTAMP.pdf",
        "generated": "04 March 2026, 21:15:00",
        "error": null
    }
    """
    # Accept multipart/form-data (with files) OR plain JSON
    ct = request.content_type or ""
    if "multipart" in ct or "form" in ct:
        client_story    = request.form.get("client_story", "").strip()
        additional_info = request.form.get("additional_info", "").strip()
        uploaded_files  = request.files.getlist("attachments")
    else:
        data            = request.get_json() or {}
        client_story    = data.get("client_story", "").strip()
        additional_info = data.get("additional_info", "").strip()
        uploaded_files  = []

    if not client_story:
        return jsonify({"error": "Please enter the client's story."}), 400

    if len(client_story) < 30:
        return jsonify({"error": "Please provide more details about the client's situation."}), 400

    try:
        # ── Step 0: Process any attached files ────────────────────────────────
        attachment_blocks = []
        for f in uploaded_files:
            fname = f.filename or ""
            fname_lower = fname.lower()
            if fname_lower.endswith(".pdf"):
                text = extract_pdf_text(BytesIO(f.read()))
                attachment_blocks.append(f"[Attached Document — {fname}]\n{text}")
            elif fname_lower.endswith((".jpg", ".jpeg")):
                text = extract_image_text(f.read(), "image/jpeg")
                attachment_blocks.append(f"[Attached Image Evidence — {fname}]\n{text}")
            elif fname_lower.endswith(".png"):
                text = extract_image_text(f.read(), "image/png")
                attachment_blocks.append(f"[Attached Image Evidence — {fname}]\n{text}")

        if additional_info:
            client_story += (
                "\n\nADDITIONAL INFORMATION / LAWYER'S CORRECTIONS:\n" + additional_info
            )
        if attachment_blocks:
            client_story += (
                "\n\nATTACHED EVIDENCE & DOCUMENTS:\n"
                + "\n\n".join(attachment_blocks)
            )

        # ── Step 1: RAG search for relevant BNS sections ──────────────────────
        retrieved_context = retrieve_relevant_sections(rag_collection, client_story)

        # ── Step 2: Build prompt and call Groq ────────────────────────────────
        prompt = build_legal_prompt(client_story, retrieved_context)

        ai_response = None
        for attempt in range(4):
            try:
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": LEXI_SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=8192,
                )
                ai_response = completion.choices[0].message.content
                break
            except Exception as e:
                err = str(e)
                if ("429" in err or "rate_limit" in err.lower()) and attempt < 3:
                    time.sleep(20 * (attempt + 1))
                else:
                    raise

        if not ai_response:
            return jsonify({"error": "AI model did not return a response. Try again."}), 500

        # ── Step 3: Save text output ──────────────────────────────────────────
        txt_path = save_raw_output(client_story, ai_response)

        # ── Step 4: Generate PDF ──────────────────────────────────────────────
        pdf_path = generate_pdf(txt_path)
        pdf_filename = Path(pdf_path).name

        # ── Step 5: Parse sections for the frontend ───────────────────────────
        with open(txt_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        sections = parse_sections(raw_text)

        # Clean markdown bold markers for web display
        for key in sections:
            if isinstance(sections[key], str):
                sections[key] = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", sections[key])

        return jsonify({
            "sections":          sections,
            "client_statement":  client_story,
            "pdf_filename":      pdf_filename,
            "generated":         sections.get("generated", datetime.now().strftime("%d %B %Y, %H:%M:%S")),
            "error":             None,
        })

    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)[:300]}"}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 3: Case history list
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/history")
def history():
    """
    Returns a list of past cases from the outputs/ folder.
    Each entry: { "txt_file": "case_analysis_...", "pdf_file": "CaseBrief_...",
                  "date": "04 March 2026, 20:52", "snippet": "Client is a 28..." }
    """
    output_dir = Path("outputs")
    cases = []

    txt_files = sorted(output_dir.glob("case_analysis_*.txt"), reverse=True)
    # Build a map of pdf files by timestamp for matching
    pdf_map = {}
    for pdf in output_dir.glob("CaseBrief_*.pdf"):
        # Extract timestamp from CaseBrief_YYYYMMDD_HHMMSS.pdf
        m = re.search(r"CaseBrief_(\d{8}_\d{6})\.pdf", pdf.name)
        if m:
            pdf_map[m.group(1)] = pdf.name

    for txt in txt_files:
        try:
            content = txt.read_text(encoding="utf-8")

            # Extract date from file
            date_match = re.search(r"Generated:\s*(.+)", content)
            date_str = date_match.group(1).strip() if date_match else txt.stem

            # Extract client statement snippet
            cs_match = re.search(
                r"CLIENT'S STATEMENT:\s*\n(.*?)(?:={10,}|SECTION 1)",
                content, re.DOTALL
            )
            snippet = ""
            if cs_match:
                snippet = cs_match.group(1).strip()
                snippet = " ".join(snippet.split())[:100]  # 100 chars, no newlines

            # Match PDF by timestamp
            ts_match = re.search(r"case_analysis_(\d{8}_\d{6})\.txt", txt.name)
            pdf_name = None
            if ts_match:
                # Find the closest PDF (generated right after)
                ts = ts_match.group(1)
                # Look for a PDF with a timestamp within 60 seconds
                for pdf_ts, pdf_fn in pdf_map.items():
                    if abs(_ts_diff(ts, pdf_ts)) <= 120:
                        pdf_name = pdf_fn
                        break

            cases.append({
                "txt_file":  txt.name,
                "pdf_file":  pdf_name,
                "date":      date_str,
                "snippet":   snippet or "No preview available",
            })
        except Exception:
            continue

    return jsonify(cases)


def _ts_diff(ts1: str, ts2: str) -> int:
    """Returns absolute difference in seconds between two YYYYMMDD_HHMMSS strings."""
    try:
        t1 = datetime.strptime(ts1, "%Y%m%d_%H%M%S")
        t2 = datetime.strptime(ts2, "%Y%m%d_%H%M%S")
        return abs(int((t2 - t1).total_seconds()))
    except Exception:
        return 9999


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 4: Load a past case (returns parsed sections from a saved .txt file)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/load/<filename>")
def load_case(filename):
    """Load a previously saved case analysis from outputs/ folder."""
    # Security: only allow reading files from outputs/ with expected name pattern
    if not re.match(r"^case_analysis_\d{8}_\d{6}\.txt$", filename):
        return jsonify({"error": "Invalid filename."}), 400

    txt_path = Path("outputs") / filename
    if not txt_path.exists():
        return jsonify({"error": "Case file not found."}), 404

    try:
        content = txt_path.read_text(encoding="utf-8")
        sections = parse_sections(content)

        for key in sections:
            if isinstance(sections[key], str):
                sections[key] = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", sections[key])

        # Find matching PDF
        ts_match = re.search(r"case_analysis_(\d{8}_\d{6})\.txt", filename)
        pdf_filename = None
        if ts_match:
            ts = ts_match.group(1)
            for pdf in Path("outputs").glob("CaseBrief_*.pdf"):
                m = re.search(r"CaseBrief_(\d{8}_\d{6})\.pdf", pdf.name)
                if m and abs(_ts_diff(ts, m.group(1))) <= 120:
                    pdf_filename = pdf.name
                    break

        return jsonify({
            "sections":         sections,
            "client_statement": sections.get("client_statement", ""),
            "pdf_filename":     pdf_filename,
            "generated":        sections.get("generated", ""),
            "error":            None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 5: PDF download
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/download/<filename>")
def download(filename):
    """Serve a PDF file from the outputs/ folder."""
    if not re.match(r"^CaseBrief_\d{8}_\d{6}\.pdf$", filename):
        return "Invalid filename.", 400
    return send_from_directory(
        Path("outputs").resolve(),
        filename,
        as_attachment=True,
        download_name=filename,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 6: Help Assistant chat
# ═══════════════════════════════════════════════════════════════════════════════

# System prompt for the Help Assistant — RAG-grounded, must cite retrieved sections only.
ASSISTANT_SYSTEM_PROMPT = """You are LEXI, a friendly AI Legal Assistant for Indian law.
Your job is to help lawyers and clients understand Indian criminal law under the
Bharatiya Nyaya Sanhita (BNS) 2023, which replaced the IPC from 1 July 2024.

You answer two types of questions:
1. "What section covers X?" — Explain the BNS section clearly (number, punishment, bailable/non-bailable)
2. "I am facing this situation..." — Briefly say which BNS sections might apply and recommend
   using the full Case Analysis tool.

CRITICAL ACCURACY RULES — these prevent legal misinformation:
- You will be given a RETRIEVED CONTEXT block containing real BNS sections from our verified
  knowledge base. ONLY cite sections, punishments, and bailable status from that block.
- NEVER invent a BNS section number or punishment from memory. If the retrieved context does
  not cover the user's question, reply: "I don't have a verified entry for that section in my
  knowledge base. Please consult a licensed Advocate or the official BNS bare act on
  indiacode.nic.in." — and stop.
- ALWAYS mention both the BNS section number AND the old IPC section it replaced (from the
  retrieved context).

Style rules:
- Be concise (3-5 sentences max per response).
- End situation-related answers by suggesting: "For a detailed FIR, legal notice, and full
  analysis, use the Case Analysis form."
- Never give advice that requires filing documents — only explain the law.
- Keep responses short and friendly — not lecture-length."""


def _retrieve_for_chat(user_msg: str, n_results: int = 4) -> str:
    """
    Run a RAG query against the same BNS collection /analyze uses, but tuned for
    short Q&A: fewer hits, formatted compactly. Returns the context block to
    inject into the LEXI system message.
    """
    cache = _load_embedding_cache()
    query_embedding = _get_embedding_with_cache(user_msg, "retrieval_query", cache)
    results = rag_collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    docs = results.get("documents", [[]])[0]
    dists = results.get("distances", [[]])[0]
    if not docs:
        return "=== RETRIEVED BNS CONTEXT ===\n(no matches found)"

    parts = ["=== RETRIEVED BNS CONTEXT (use ONLY these sections in your reply) ==="]
    for i, (doc, dist) in enumerate(zip(docs, dists)):
        relevance = round((1 - dist) * 100, 1)
        parts.append(f"\n[Match {i+1} — Relevance: {relevance}%]\n{doc}")
    return "\n".join(parts)


@app.route("/chat", methods=["POST"])
def chat():
    """
    Help Assistant endpoint — RAG-grounded.
    Accepts: { "message": "What is BNS 85?" }
    Returns: { "reply": "...", "suggest_intake": true/false }
    """
    data = request.get_json()
    user_msg = (data or {}).get("message", "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type a question.", "suggest_intake": False})

    try:
        retrieved_context = _retrieve_for_chat(user_msg, n_results=4)

        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
                {"role": "system", "content": retrieved_context},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        reply = completion.choices[0].message.content.strip()

        suggest_intake = any(kw in reply.lower() for kw in [
            "intake form", "case analysis", "full analysis", "use the form",
            "analyze", "detailed analysis"
        ])

        return jsonify({"reply": reply, "suggest_intake": suggest_intake})

    except Exception as e:
        return jsonify({
            "reply": f"Sorry, I couldn't process that right now. ({str(e)[:80]})",
            "suggest_intake": False
        })


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("  Open your browser at: http://localhost:8080\n")
    app.run(debug=False, host="0.0.0.0", port=8080)
