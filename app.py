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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from io import BytesIO

import pdfplumber
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from dotenv import load_dotenv

# ── Import pipeline functions from main.py ────────────────────────────────────
from main import (
    configure_gemini_embeddings,
    configure_groq,
    build_rag_knowledge_base,
    retrieve_relevant_sections,
    retrieve_relevant_sections_structured,
    build_legal_prompt,
    LEXI_SYSTEM_PROMPT,
    save_raw_output,
)
# Used by the RAG-grounded /chat endpoint to search the same KB as /analyze
from main import _get_embedding_with_cache, _load_embedding_cache

# Audit trail (DPDP Act 2023 compliance) — never breaks the request path
import audit
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
# ROUTE 1: Marketing landing page (3D hero, scroll animations, sales pitch)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def landing():
    """Marketing landing page — sells the product. Links to /app for the tool."""
    return render_template("landing.html")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 1b: The actual legal-triage intake form (formerly at /)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/app")
def app_page():
    """The intake form + results UI — what was previously the home page."""
    return render_template("index.html")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 1c: IPC → BNS converter (Day-1 from the Legora teardown).
# Upload an old IPC-era pleading, get back a .docx with every IPC reference
# highlighted yellow and the BNS equivalent inserted in red right after it.
# Plain-text path also available for the in-page preview.
# ═══════════════════════════════════════════════════════════════════════════════
from ipc_bns_converter import convert_text, convert_docx


@app.route("/convert")
def convert_page():
    """Drag-drop UI for the IPC→BNS converter."""
    return render_template("convert.html")


@app.route("/convert/text", methods=["POST"])
def convert_text_endpoint():
    """
    Convert a piece of plain text (paste-and-preview path).
    Accepts: { "text": "..." }
    Returns: { "annotated": "...", "summary": {...} }
    """
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Please paste some text to convert."}), 400
    if len(text) > 200_000:
        return jsonify({"error": "Text too large (limit 200,000 chars)."}), 400

    annotated, summary = convert_text(text)
    return jsonify({
        "annotated": annotated,
        "summary": summary.to_dict(),
    })


@app.route("/convert/upload", methods=["POST"])
def convert_upload():
    """
    Accept a .docx upload, run the round-trip converter, return the new .docx
    plus a JSON summary in a multipart-ish response — simplest path is to save
    the new file to outputs/converted/ and return its filename + the summary.
    """
    from werkzeug.utils import secure_filename
    from datetime import datetime

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".docx"):
        return jsonify({"error": "Only .docx files are supported."}), 400

    try:
        new_bytes, summary = convert_docx(f.stream)
    except Exception as e:
        return jsonify({"error": f"Conversion failed: {str(e)[:200]}"}), 500

    # Save the converted file to outputs/converted/
    out_dir = Path("outputs/converted")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = secure_filename(f.filename).removesuffix(".docx") or "pleading"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"{safe}_{ts}.bns.docx"
    out_path = out_dir / out_name
    with open(out_path, "wb") as out_f:
        out_f.write(new_bytes)

    return jsonify({
        "filename": out_name,
        "summary": summary.to_dict(),
    })


@app.route("/convert/download/<filename>")
def convert_download(filename):
    """Serve a converted .docx file from outputs/converted/."""
    if not re.match(r"^[A-Za-z0-9_\-]+_\d{8}_\d{6}\.bns\.docx$", filename):
        return "Invalid filename.", 400
    return send_from_directory(
        Path("outputs/converted").resolve(),
        filename,
        as_attachment=True,
        download_name=filename,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Precedent Monitor (Day-3 from the Legora teardown).
# Lawyers register matter areas; daily digest surfaces matching SC rulings.
# ═══════════════════════════════════════════════════════════════════════════════
import monitors as monitors_module
import i18n as i18n_module
import nalsa as nalsa_module
import compliance as compliance_module
import matters as matters_module
import auth as auth_module
import ecourts as ecourts_module
import llm_provider as llm_provider_module
import tabular as tabular_module
import webhooks as webhooks_module
import leads as leads_module
import api_keys as api_keys_module
import openapi_spec as openapi_spec_module


@app.route("/monitors")
def monitors_page():
    return render_template("monitors.html")


@app.route("/monitors/api/matters", methods=["GET"])
def monitors_list_matters():
    return jsonify({"matters": monitors_module.list_matters()})


@app.route("/monitors/api/matters", methods=["POST"])
def monitors_add_matter():
    data = request.get_json() or {}
    label = (data.get("label") or "").strip()
    sections = data.get("sections") or []
    keywords = data.get("keywords") or []
    if not label:
        return jsonify({"error": "Label is required."}), 400
    if not isinstance(sections, list) or not isinstance(keywords, list):
        return jsonify({"error": "Sections and keywords must be arrays."}), 400
    if not sections and not keywords:
        return jsonify({"error": "Provide at least one section or one keyword."}), 400
    saved = monitors_module.add_matter(label, keywords=keywords, sections=sections)
    return jsonify({"matter": saved})


@app.route("/monitors/api/matters/<matter_id>", methods=["DELETE"])
def monitors_remove_matter(matter_id):
    if not re.match(r"^m_\d+$", matter_id):
        return jsonify({"error": "Invalid matter id."}), 400
    ok = monitors_module.remove_matter(matter_id)
    if not ok:
        return jsonify({"error": "Matter not found."}), 404
    return jsonify({"ok": True})


@app.route("/monitors/api/digest", methods=["GET"])
def monitors_digest():
    since = request.args.get("since")  # optional YYYY-MM-DD
    d = monitors_module.run_digest(since=since)
    if request.args.get("save") == "1":
        monitors_module.save_digest(d)
    return jsonify(d)


@app.route("/monitors/digest.txt")
def monitors_digest_text():
    """Plain-text digest — pipe-friendly for cron + email."""
    d = monitors_module.run_digest()
    response = make_response(monitors_module.format_digest_text(d))
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — i18n (Day-4 from the Legora teardown).
# /i18n/strings.json     — full English+Hindi strings dict, fetched by frontend
# /i18n/strings.json?lang=hi  — pre-flattened to one language
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/i18n/strings.json")
def i18n_strings():
    lang = (request.args.get("lang") or "").lower()
    if lang in ("en", "hi"):
        return jsonify(i18n_module.get_strings(lang))
    return jsonify(i18n_module.get_all())


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — NALSA panel onboarding (Day-5 from the Legora teardown).
# Free tier for NALSA-empanelled advocates serving free legal aid.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/nalsa")
def nalsa_page():
    return render_template("nalsa.html", slsas=nalsa_module.SLSAS)


@app.route("/nalsa/api/register", methods=["POST"])
def nalsa_register():
    payload = request.get_json() or {}
    ok, error = nalsa_module.validate(payload)
    if not ok:
        return jsonify({"error": error}), 400
    try:
        reg = nalsa_module.register(payload)
    except Exception as e:
        return jsonify({"error": f"Could not save registration: {str(e)[:200]}"}), 500
    return jsonify({"registration": reg.to_dict()})


@app.route("/nalsa/api/stats")
def nalsa_stats():
    return jsonify(nalsa_module.stats())


@app.route("/nalsa/api/export.csv")
def nalsa_export_csv():
    """SLSA spot-check CSV.  Production: gate behind admin auth."""
    if os.getenv("NALSA_EXPORT_TOKEN"):
        provided = request.headers.get("X-Export-Token", "")
        if provided != os.getenv("NALSA_EXPORT_TOKEN"):
            return ("Unauthorised.", 401)
    csv_body = nalsa_module.export_csv()
    response = make_response(csv_body)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="nalsa-registry.csv"'
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Trust & Compliance (Day-6 from the Legora teardown).
# Buyer-facing page + downloadable .docx pack for the firm GC.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/trust")
def trust_page():
    return render_template("trust.html", **compliance_module.to_dict())


@app.route("/trust/pack.docx")
def trust_pack_docx():
    """Compile the procurement-grade .docx pack on-demand."""
    body = compliance_module.build_pack_docx()
    response = make_response(body)
    response.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response.headers["Content-Disposition"] = (
        'attachment; filename="lex-indic-compliance-pack.docx"'
    )
    return response


@app.route("/trust/posture.json")
def trust_posture_json():
    """Machine-readable version of the posture — for any procurement tool that
    can ingest JSON instead of asking 28 questions by hand."""
    return jsonify(compliance_module.to_dict())


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Matter intake registry (Day-9).
# Firm -> Lawyer -> Matter triple with optional analyze-tagging.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/matters")
def matters_page():
    return render_template("matters.html")


@app.route("/matters/api/firms", methods=["GET", "POST"])
def matters_firms():
    """Day-16 multi-tenant rules:
      GET  — anonymous: returns all firms (demo).
             authenticated: returns only the user's firm.
      POST — anyone can create a firm; if user is authenticated and has
             no firm_id yet, auto-bind them to the new firm as 'partner'."""
    u = _current_user()
    if request.method == "GET":
        firms = matters_module.list_firms()
        if u and u.get("firm_id"):
            firms = [f for f in firms if f["id"] == u["firm_id"]]
        return jsonify({"firms": firms})
    data = request.get_json() or {}
    try:
        firm = matters_module.add_firm(data.get("name", ""), data.get("address", ""))
        # Auto-bind the creating user to the new firm on first create
        if u and not u.get("firm_id"):
            auth_module.bind_user_to_firm(u["id"], firm["id"], role="partner")
        return jsonify({"firm": firm})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/matters/api/lawyers", methods=["GET", "POST"])
def matters_lawyers():
    u = _current_user()
    if request.method == "GET":
        lawyers = matters_module.list_lawyers()
        if u and u.get("firm_id"):
            lawyers = [l for l in lawyers if l["firm_id"] == u["firm_id"]]
        return jsonify({"lawyers": lawyers})
    data = request.get_json() or {}
    # Authenticated user: silently override firm_id to their own
    firm_id = u["firm_id"] if (u and u.get("firm_id")) else data.get("firm_id", "")
    try:
        lwy = matters_module.add_lawyer(
            firm_id=firm_id,
            full_name=data.get("full_name", ""),
            bar_council_no=data.get("bar_council_no", ""),
            email=data.get("email", ""),
            role=data.get("role", "associate"),
        )
        return jsonify({"lawyer": lwy})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/matters/api/matters", methods=["GET", "POST"])
def matters_matters():
    u = _current_user()
    if request.method == "GET":
        matters = matters_module.list_matters()
        if u and u.get("firm_id"):
            matters = [m for m in matters if m["firm_id"] == u["firm_id"]]
        return jsonify({"matters": matters})
    data = request.get_json() or {}
    firm_id = u["firm_id"] if (u and u.get("firm_id")) else data.get("firm_id", "")
    try:
        m = matters_module.add_matter(
            firm_id=firm_id,
            lawyer_id=data.get("lawyer_id", ""),
            client_name=data.get("client_name", ""),
            opposing_party=data.get("opposing_party", ""),
            matter_type=data.get("matter_type", ""),
            description=data.get("description", ""),
        )
        conflicts = matters_module.check_conflict(
            firm_id=firm_id,
            client_name=data.get("client_name", ""),
            opposing_party=data.get("opposing_party", ""),
        )
        # Day-15 webhook: matter.created
        try:
            webhooks_module.emit("matter.created", {
                "matter_id": m["id"],
                "firm_id":   m["firm_id"],
                "lawyer_id": m["lawyer_id"],
                "matter_type": m.get("matter_type"),
                "conflicts_count": len(conflicts),
                "by_user_id": (u or {}).get("id"),
            })
        except Exception:
            pass
        return jsonify({"matter": m, "conflicts": conflicts})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/matters/api/conflict-check", methods=["POST"])
def matters_conflict_check():
    """Pre-create conflict check — call before adding a matter."""
    data = request.get_json() or {}
    hits = matters_module.check_conflict(
        firm_id=data.get("firm_id", ""),
        client_name=data.get("client_name", ""),
        opposing_party=data.get("opposing_party", ""),
    )
    return jsonify({"conflicts": hits})


@app.route("/matters/api/<matter_id>/status", methods=["PATCH"])
def matters_status(matter_id):
    if not re.match(r"^[A-Z]+/\d{4}/\d{4}$", matter_id):
        return jsonify({"error": "Invalid matter ID."}), 400
    data = request.get_json() or {}
    ok = matters_module.update_matter_status(matter_id, data.get("status", ""))
    if not ok:
        return jsonify({"error": "Matter not found or invalid status."}), 400
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Multi-tenant auth (Day-10).
# Magic-link login: POST /auth/code, POST /auth/verify, GET /auth/me, /auth/logout.
# ═══════════════════════════════════════════════════════════════════════════════
from flask import make_response  # already imported earlier; harmless re-import

_DEV_MODE_AUTH = not os.getenv("AUDIT_HASH_SALT")  # dev iff salt unset


@app.route("/login")
def login_page():
    return render_template("login.html", dev_mode=_DEV_MODE_AUTH)


@app.route("/auth/code", methods=["POST"])
def auth_code():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    try:
        code = auth_module.issue_code(email)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    # In dev we expose the code in the response for easy testing.  In prod
    # (AUDIT_HASH_SALT set) we hide it and the operator's email provider
    # delivers the code.
    resp = {"ok": True}
    if _DEV_MODE_AUTH:
        resp["dev_code"] = code
    return jsonify(resp)


@app.route("/auth/verify", methods=["POST"])
def auth_verify():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    code  = (data.get("code")  or "").strip()
    user_id = auth_module.verify_code(email, code)
    if not user_id:
        return jsonify({"error": "Invalid or expired code."}), 401
    token = auth_module.make_session_token(user_id)
    response = make_response(jsonify({"ok": True, "user_id": user_id}))
    secure = request.scheme == "https"
    response.set_cookie(
        "lex_session", token,
        max_age=60 * 60 * 24 * 14,  # 14 days
        httponly=True,
        secure=secure,
        samesite="Lax",
    )
    return response


@app.route("/auth/me")
def auth_me():
    token = request.cookies.get("lex_session", "")
    user_id = auth_module.verify_session_token(token)
    if not user_id:
        return jsonify({"authenticated": False}), 401
    user = auth_module.get_user_by_id(user_id)
    if not user:
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": user})


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    response = make_response(jsonify({"ok": True}))
    response.set_cookie("lex_session", "", expires=0)
    return response


@app.route("/auth/bind-firm", methods=["POST"])
def auth_bind_firm():
    """Bind the currently-authenticated user to a firm_id.  Caller pre-creates
    the firm via /matters/api/firms.  Idempotent."""
    token = request.cookies.get("lex_session", "")
    user_id = auth_module.verify_session_token(token)
    if not user_id:
        return jsonify({"error": "Not signed in."}), 401
    data = request.get_json() or {}
    firm_id = (data.get("firm_id") or "").strip()
    role    = (data.get("role") or "associate").strip()
    if not firm_id:
        return jsonify({"error": "firm_id is required."}), 400
    ok = auth_module.bind_user_to_firm(user_id, firm_id, role=role)
    return jsonify({"ok": ok})


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — e-Courts CNR lookup (Day-12).
# Single page + 2 API endpoints.  Wire ECOURTS_PROVIDER=live + a real
# adapter in production; ships with stub data for dev/demos.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/ecourts")
def ecourts_page():
    return render_template("ecourts.html", demos=ecourts_module.demo_cnrs())


@app.route("/ecourts/api/lookup/<cnr>")
def ecourts_lookup(cnr):
    cnr_norm = ecourts_module.normalize_cnr(cnr)
    if not ecourts_module.is_valid_cnr(cnr_norm):
        return jsonify({
            "error": "Invalid CNR. Format: SCCC + 2-digit unit + 6-digit case + 4-digit year (e.g. MHCC010012342024).",
            "expected_format": "AAAA##NNNNNNYYYY (16 chars)",
        }), 400
    result = ecourts_module.fetch_cnr_status(cnr_norm)
    if not result:
        return jsonify({"error": f"CNR {cnr_norm} not found in the active provider."}), 404
    return jsonify(result)


@app.route("/ecourts/api/demos")
def ecourts_demos():
    return jsonify({"cases": ecourts_module.demo_cnrs()})


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — LLM provider status (Day-13).
# Tells the operator which inference backend is active and whether Ollama
# is reachable.  Used by /admin pages and the trust page.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/llm/status")
def llm_status():
    return jsonify(llm_provider_module.status())


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Tabular contract review (Day-14).
# Upload N contracts + pick clause-questions → matrix of answers.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/tabular")
def tabular_page():
    return render_template("tabular.html", libraries={
        k: [{"label": c.label, "question": c.question} for c in v]
        for k, v in tabular_module.CLAUSE_LIBRARIES.items()
    })


@app.route("/tabular/api/compare", methods=["POST"])
def tabular_compare():
    """Multipart: 'files' = N file uploads, 'clauses' = JSON array of
    {label, question}."""
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Upload at least one contract."}), 400
    if len(files) > 8:
        return jsonify({"error": "At most 8 contracts per comparison."}), 400

    clauses_raw = request.form.get("clauses", "[]")
    try:
        clauses_data = json.loads(clauses_raw)
    except Exception:
        return jsonify({"error": "Invalid clauses payload."}), 400
    if not isinstance(clauses_data, list) or not clauses_data:
        return jsonify({"error": "Provide at least one clause-question."}), 400
    if len(clauses_data) > 12:
        return jsonify({"error": "At most 12 clauses per comparison."}), 400

    clauses = [
        tabular_module.Clause(label=c.get("label", "")[:60], question=c.get("question", "")[:200])
        for c in clauses_data if c.get("question")
    ]
    if not clauses:
        return jsonify({"error": "Each clause needs a question."}), 400

    # Extract text from every uploaded file
    contracts = []
    for f in files:
        fname = f.filename or "contract"
        fname_lower = fname.lower()
        if fname_lower.endswith(".pdf"):
            text = extract_pdf_text(BytesIO(f.read()))
        elif fname_lower.endswith(".docx"):
            try:
                from docx import Document
                doc = Document(BytesIO(f.read()))
                text = "\n".join(p.text for p in doc.paragraphs if p.text)
            except Exception as e:
                text = f"[docx extraction failed: {e}]"
        elif fname_lower.endswith((".txt",)):
            text = f.read().decode("utf-8", errors="replace")
        else:
            return jsonify({"error": f"Unsupported file type: {fname}. Use .pdf, .docx, or .txt."}), 400
        contracts.append(tabular_module.Contract(name=fname[:60], text=text))

    # Define the llm_call closure based on the active provider
    def _llm_call(system_prompt: str, user_prompt: str) -> str:
        if llm_provider_module.get_provider() == "ollama":
            out = llm_provider_module.complete(
                system_messages=[system_prompt],
                user_message=user_prompt,
                temperature=0.0,  # we want deterministic JSON, not creative
                max_tokens=2048,
                timeout_s=120,
            )
            return out.get("text", "") or ""
        # Groq path
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        return completion.choices[0].message.content or ""

    try:
        result = tabular_module.run_comparison(contracts, clauses, _llm_call)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Comparison failed: {str(e)[:200]}"}), 500


# ─── Helper: current_user() used by any route that wants the firm tag ─────
def _current_user() -> dict | None:
    token = request.cookies.get("lex_session", "")
    if not token:
        return None
    user_id = auth_module.verify_session_token(token)
    if not user_id:
        return None
    return auth_module.get_user_by_id(user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — SOC 2 readiness scaffolding (Day-7 from the Legora teardown).
# Internal admin dashboard + evidence-snapshot trail.  Token-gated in prod.
# ═══════════════════════════════════════════════════════════════════════════════
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent / "tools" / "soc2"))
import controls as soc2_module


def _require_admin():
    """Tiny token-gate so the admin dashboard isn't world-readable in prod.
    Set ADMIN_TOKEN in .env; pass it via ?token=… or X-Admin-Token header.
    If ADMIN_TOKEN is unset (dev), allow without a check."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        return None  # dev mode — no gate
    provided = request.args.get("token") or request.headers.get("X-Admin-Token", "")
    if provided != expected:
        return ("Unauthorised. Set ADMIN_TOKEN and pass it via X-Admin-Token.", 401)
    return None


@app.route("/admin/soc2")
def admin_soc2_page():
    guard = _require_admin()
    if guard: return guard
    return render_template("admin_soc2.html")


@app.route("/admin/soc2/summary.json")
def admin_soc2_summary():
    guard = _require_admin()
    if guard: return guard
    return jsonify(soc2_module.summary())


@app.route("/admin/soc2/snapshot", methods=["POST"])
def admin_soc2_snapshot():
    guard = _require_admin()
    if guard: return guard
    path = soc2_module.save_evidence_snapshot()
    return jsonify({"path": str(path.relative_to(Path.cwd())) if path.is_absolute() else str(path)})


@app.route("/admin/soc2/snapshots")
def admin_soc2_snapshots():
    guard = _require_admin()
    if guard: return guard
    snap_dir = Path("outputs/soc2_evidence")
    if not snap_dir.exists():
        return jsonify({"snapshots": []})
    snaps = sorted(snap_dir.glob("*.json"), reverse=True)
    return jsonify({
        "snapshots": [
            {"file": p.name, "size": p.stat().st_size,
             "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}
            for p in snaps[:50]
        ]
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES 1d-h: Microsoft Word Add-in (Day-2 from the Legora teardown).
# Office Add-ins load HTML/JS in an iframe inside Word's task pane.  We serve:
#   /addin/install      → human-facing sideload instructions
#   /addin/manifest.xml → the OfficeApp manifest Word reads
#   /addin/taskpane     → the iframe UI loaded inside Word
#   /addin/commands     → required no-op shell for ribbon command actions
#   /static/addin/*     → icons (served by Flask's static handler already)
# Office requires HTTPS — run `python3 app.py --https` to enable port 8443.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/addin/install")
def addin_install_page():
    """User-facing instructions for sideloading the manifest into Word."""
    return render_template("addin/install.html")


@app.route("/addin/manifest.xml")
def addin_manifest():
    """Serve the OfficeApp manifest XML with the correct MIME type."""
    body = render_template("addin/manifest.xml")
    response = make_response(body)
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    # Always allow Word to fetch this without a CORS preflight.
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.route("/addin/taskpane")
def addin_taskpane():
    """The iframe HTML Word loads inside its task pane."""
    response = make_response(render_template("addin/taskpane.html"))
    # Office's iframe lives in an https://word-edit.officeapps.live.com origin
    # (or the desktop app's webview).  Allow framing + cross-origin XHR back to
    # this server.
    response.headers["Access-Control-Allow-Origin"] = "*"
    # Don't deny framing — Office WILL frame us; setting X-Frame-Options=DENY
    # would break the add-in entirely.
    response.headers.pop("X-Frame-Options", None)
    return response


@app.route("/addin/commands")
def addin_commands():
    """
    Required by the manifest's <FunctionFile resid="Commands.Url"/>.  We don't
    register any custom ribbon commands beyond the button that just opens the
    task pane, so this is intentionally a tiny stub.  Office still expects
    the URL to exist and return 200.
    """
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<script src="https://appsforoffice.microsoft.com/lib/1/hosted/office.js"></script>
</head><body>
<!-- Lex-Indic Word add-in commands stub. Required by Office; intentionally
     empty because all commands open the task pane via the manifest. -->
</body></html>"""


# ─── CORS for the /convert/text endpoint (the task pane calls it from an
#     iframe whose origin differs from our server's).  We only allow the
#     two endpoints the add-in actually needs.
@app.after_request
def _allow_addin_xhr(response):
    if request.path.startswith("/convert/") or request.path.startswith("/addin/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/convert/text", methods=["OPTIONS"])
@app.route("/convert/upload", methods=["OPTIONS"])
def _convert_preflight():
    """Handle CORS preflight for the task pane's XHR calls."""
    return ("", 204)


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
        "request_id": "uuid for audit trace",
        "error": null
    }
    """
    # Capture audit context up-front so it's available on every code path
    t_start    = time.monotonic()
    client_ip  = (request.headers.get("X-Forwarded-For") or request.remote_addr or "")
    user_agent = request.headers.get("User-Agent", "")
    # Day-16: enrich audit with user_id/firm_id when authenticated.
    _u = _current_user()
    _audit_extra = {
        "user_id":   (_u or {}).get("id", "") or None,
        "firm_id":   (_u or {}).get("firm_id", "") or None,
    }

    # Accept multipart/form-data (with files) OR plain JSON
    ct = request.content_type or ""
    if "multipart" in ct or "form" in ct:
        client_story    = request.form.get("client_story", "").strip()
        additional_info = request.form.get("additional_info", "").strip()
        uploaded_files  = request.files.getlist("attachments")
        language        = (request.form.get("language") or "en").lower()
        _audit_extra["matter_id"] = request.form.get("matter_id") or None
    else:
        data            = request.get_json() or {}
        client_story    = data.get("client_story", "").strip()
        additional_info = data.get("additional_info", "").strip()
        uploaded_files  = []
        language        = (data.get("language") or "en").lower()
        _audit_extra["matter_id"] = (data.get("matter_id") or None)
    if language not in ("en", "hi"):
        language = "en"

    if not client_story:
        rid = audit.log_request(
            endpoint="/analyze", client_ip=client_ip, user_agent=user_agent,
            story="", status="error", duration_ms=int((time.monotonic() - t_start) * 1000),
            error="empty client_story", extra=_audit_extra,
        )
        return jsonify({"error": "Please enter the client's story.", "request_id": rid}), 400

    if len(client_story) < 30:
        rid = audit.log_request(
            endpoint="/analyze", client_ip=client_ip, user_agent=user_agent,
            story=client_story, status="error",
            duration_ms=int((time.monotonic() - t_start) * 1000),
            error="story too short", extra=_audit_extra,
        )
        return jsonify({"error": "Please provide more details about the client's situation.", "request_id": rid}), 400

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
        # Use the structured variant so we can return sources to the frontend
        # for citation provenance (the user can verify every section we cited).
        # Day-4: drop one retrieval slot when Hindi is requested, because the
        # Hindi system instruction adds ~700 tokens and we'd otherwise blow
        # past Groq's free-tier 12K TPM per request.
        n_results = 7 if language == "hi" else 8
        retrieved_context, sources = retrieve_relevant_sections_structured(
            rag_collection, client_story, n_results=n_results
        )

        # ── Step 2: Build prompt and call Groq ────────────────────────────────
        prompt = build_legal_prompt(client_story, retrieved_context)

        # Day-4: if Hindi requested, append the Hindi system instruction.
        # We layer it as a separate system message so the original LEXI prompt
        # stays untouched and we can A/B the Hindi tail in isolation.
        system_messages = [LEXI_SYSTEM_PROMPT]
        if language == "hi":
            system_messages.append(i18n_module.HINDI_SYSTEM_INSTRUCTION)

        ai_response = None
        # Day-13: route through llm_provider so Ollama users get local inference
        # with zero sub-processors.  Groq remains the default; ollama users set
        # LLM_PROVIDER=ollama in .env.
        if llm_provider_module.get_provider() == "ollama":
            result = llm_provider_module.complete(
                system_messages=system_messages,
                user_message=prompt,
                temperature=0.2,
                max_tokens=8192,
                timeout_s=180,
            )
            ai_response = result["text"]
        else:
            # Groq path (unchanged): keep the rate-limit retry loop
            messages = [{"role": "system", "content": s} for s in system_messages]
            messages.append({"role": "user", "content": prompt})
            for attempt in range(4):
                try:
                    completion = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
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

        # ── Audit log: success ────────────────────────────────────────────────
        request_id = audit.log_request(
            endpoint="/analyze",
            client_ip=client_ip,
            user_agent=user_agent,
            story=client_story,
            sources=sources,
            status="ok",
            duration_ms=int((time.monotonic() - t_start) * 1000),
            response_chars=len(ai_response or ""),
            pdf_filename=pdf_filename,
            extra=_audit_extra,
        )

        # Day 15: fire the analysis.completed webhook (fire-and-forget)
        try:
            webhooks_module.emit("analysis.completed", {
                "request_id": request_id,
                "language":   language,
                "pdf_filename": pdf_filename,
                "sources":    [s.get("id") for s in sources],
                "duration_ms": int((time.monotonic() - t_start) * 1000),
            })
        except Exception:
            pass  # webhooks must not affect the user response

        return jsonify({
            "sections":          sections,
            "client_statement":  client_story,
            "pdf_filename":      pdf_filename,
            "generated":         sections.get("generated", datetime.now().strftime("%d %B %Y, %H:%M:%S")),
            "sources":           sources,
            "language":          language,
            "request_id":        request_id,
            "error":             None,
        })

    except Exception as e:
        # ── Audit log: error path — preserves the failure for forensics ───────
        request_id = audit.log_request(
            endpoint="/analyze",
            client_ip=client_ip,
            user_agent=user_agent,
            story=client_story,
            status="error",
            duration_ms=int((time.monotonic() - t_start) * 1000),
            error=str(e),
            extra=_audit_extra,
        )
        return jsonify({
            "error": f"Analysis failed: {str(e)[:300]}",
            "request_id": request_id,
        }), 500


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


def _retrieve_for_chat(user_msg: str, n_results: int = 4):
    """
    Run a RAG query against the same BNS collection /analyze uses, but tuned for
    short Q&A: fewer hits, formatted compactly.

    Returns: (context_string, sources_list) — sources are surfaced to the chat
    UI so the user can see which KB entries LEXI consulted.
    """
    return retrieve_relevant_sections_structured(rag_collection, user_msg, n_results)


@app.route("/chat", methods=["POST"])
def chat():
    """
    Help Assistant endpoint — RAG-grounded.
    Accepts: { "message": "What is BNS 85?" }
    Returns: { "reply": "...", "suggest_intake": true/false, "request_id": "..." }
    """
    t_start    = time.monotonic()
    client_ip  = (request.headers.get("X-Forwarded-For") or request.remote_addr or "")
    user_agent = request.headers.get("User-Agent", "")

    data = request.get_json()
    user_msg = (data or {}).get("message", "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type a question.", "suggest_intake": False})

    try:
        retrieved_context, sources = _retrieve_for_chat(user_msg, n_results=4)

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

        request_id = audit.log_request(
            endpoint="/chat",
            client_ip=client_ip,
            user_agent=user_agent,
            story=user_msg,
            sources=sources,
            status="ok",
            duration_ms=int((time.monotonic() - t_start) * 1000),
            response_chars=len(reply or ""),
        )

        return jsonify({
            "reply": reply,
            "suggest_intake": suggest_intake,
            "sources": sources,
            "request_id": request_id,
        })

    except Exception as e:
        request_id = audit.log_request(
            endpoint="/chat",
            client_ip=client_ip,
            user_agent=user_agent,
            story=user_msg,
            status="error",
            duration_ms=int((time.monotonic() - t_start) * 1000),
            error=str(e),
        )
        return jsonify({
            "reply": f"Sorry, I couldn't process that right now. ({str(e)[:80]})",
            "suggest_intake": False,
            "sources": [],
            "request_id": request_id,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Lead capture (/try).  Shown to prospects who hit the demo URL
# without context.  3-field form → outputs/leads/leads.json + webhook.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/try")
def try_page():
    return render_template("try.html")


@app.route("/try/submit", methods=["POST"])
def try_submit():
    data = request.get_json() or {}
    ok, err = leads_module.validate(data)
    if not ok:
        return jsonify({"error": err}), 400
    try:
        lead = leads_module.capture(
            data,
            referrer=request.headers.get("Referer", ""),
            user_agent=request.headers.get("User-Agent", ""),
        )
    except Exception as e:
        return jsonify({"error": f"Could not save: {str(e)[:200]}"}), 500
    # Fire webhook so the operator can pipe leads to Slack / Notion / CRM
    try:
        webhooks_module.emit("lead.captured", {
            "lead_id":     lead.id,
            "email":       lead.email,
            "firm_or_org": lead.firm_or_org,
            "role":        lead.role,
            "interests":   lead.interests,
        })
    except Exception:
        pass
    # Day 17: also email the operator if LEAD_NOTIFY_EMAIL is configured
    try:
        op = os.getenv("LEAD_NOTIFY_EMAIL", "")
        if op:
            import mailer as _mailer
            from dataclasses import asdict
            _mailer.send_lead_notification(op, asdict(lead))
    except Exception:
        pass
    return jsonify({"lead": {"id": lead.id, "full_name": lead.full_name}})


@app.route("/try/api/leads")
def try_leads():
    """List leads — admin-gated."""
    guard = _require_admin()
    if guard: return guard
    return jsonify({"leads": leads_module.list_all(), "stats": leads_module.stats()})


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Public status page + JSON (Day-15).
# A firm IT team opens /status to verify the deployment is healthy without
# asking us for a demo.  Audited endpoints, real-time KB count, SOC 2 view.
# ═══════════════════════════════════════════════════════════════════════════════
_SERVER_STARTED_AT = datetime.now(timezone.utc)


def _read_recent_audit(n: int = 5) -> list[dict]:
    """Best-effort: read last N records from today's audit log."""
    audit_dir = Path("outputs/audit")
    if not audit_dir.exists():
        return []
    files = sorted(audit_dir.glob("audit-*.log"), reverse=True)[:2]
    records = []
    for f in files:
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            continue
    return list(reversed(records))[:n]


import urllib.request as _urllib_req


def _self_probe(paths: list[tuple[str, int]]) -> list[dict]:
    """Probe a list of internal paths over loopback and report status/latency.
    Errors are caught — the status page must never crash."""
    results = []
    for path, expected in paths:
        start = time.monotonic()
        try:
            req = _urllib_req.Request(f"http://127.0.0.1:{_LISTEN_PORT}{path}")
            with _urllib_req.urlopen(req, timeout=2.5) as resp:
                ok = (resp.status == expected)
                results.append({
                    "path": path, "status": resp.status, "ok": ok,
                    "latency_ms": int((time.monotonic() - start) * 1000),
                })
        except Exception as e:
            results.append({
                "path": path, "status": 0, "ok": False,
                "latency_ms": int((time.monotonic() - start) * 1000),
                "error": str(e)[:80],
            })
    return results


@app.route("/status")
def status_page():
    return render_template("status.html")


@app.route("/status.json")
def status_json():
    # KB sizes
    try:
        kb_total = rag_collection.count()
    except Exception:
        kb_total = 0
    # Count by kind by looking at metadata in a small sample
    bns_n, bnss_bsa_n, corpus_n = 0, 0, 0
    try:
        ids = rag_collection.get(include=[])["ids"]
        for did in ids:
            if did.startswith("bnss_") or did.startswith("bsa_"):
                bnss_bsa_n += 1
            elif did.startswith("bns_"):
                bns_n += 1
            else:
                corpus_n += 1
    except Exception:
        pass

    # Audit summary (last 24h)
    recent = _read_recent_audit(50)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    recent_24h = [r for r in recent if r.get("ts", "") >= cutoff.isoformat(timespec="seconds")]
    errors_24h = sum(1 for r in recent_24h if r.get("status") == "error")

    # SOC 2 — best effort, soc2 module may not be importable
    soc2_data = {"total": 0, "passed": 0, "failed": 0}
    try:
        s = soc2_module.summary()
        soc2_data = {"total": s["total"], "passed": s["passed"], "failed": s["failed"]}
    except Exception:
        pass

    # Endpoints to probe (read-only, no side-effects)
    endpoints = _self_probe([
        ("/", 200),
        ("/app", 200),
        ("/i18n/strings.json", 200),
        ("/monitors", 200),
        ("/llm/status", 200),
        ("/trust/posture.json", 200),
    ])
    failed = sum(1 for e in endpoints if not e["ok"])

    # Git SHA — best effort
    git_sha = ""
    try:
        import subprocess
        git_sha = subprocess.run(
            ["git", "-C", str(Path(__file__).parent), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
    except Exception:
        pass

    uptime_s = (now - _SERVER_STARTED_AT).total_seconds()

    return jsonify({
        "version":  "v1.4",
        "git_sha":  git_sha,
        "uptime": {
            "seconds": int(uptime_s),
            "hours":   uptime_s / 3600.0,
            "started_at": _SERVER_STARTED_AT.isoformat(timespec="seconds"),
        },
        "kb": {
            "total":    kb_total,
            "bns":      bns_n,
            "bnss_bsa": bnss_bsa_n,
            "corpus":   corpus_n,
        },
        "llm": llm_provider_module.status(),
        "audit": {
            "requests_24h": len(recent_24h),
            "errors_24h":   errors_24h,
            "recent":       recent_24h[-10:][::-1],
        },
        "soc2": soc2_data,
        "endpoints": endpoints,
        "health": {
            "checked_at":         now.isoformat(timespec="seconds"),
            "total_endpoints":    len(endpoints),
            "failed_endpoints":   failed,
        },
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Webhooks (Day-15).
# Outbound HTTP POSTs to subscriber URLs when events happen.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/webhooks/api/subscriptions", methods=["GET", "POST"])
def webhooks_subscriptions():
    if request.method == "GET":
        return jsonify({"subscriptions": webhooks_module.list_subs()})
    data = request.get_json() or {}
    try:
        sub = webhooks_module.add_sub(
            url=data.get("url", ""),
            events=data.get("events", []),
            description=data.get("description", ""),
        )
        return jsonify({"subscription": sub})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/webhooks/api/subscriptions/<sub_id>", methods=["DELETE"])
def webhooks_remove(sub_id):
    if not re.match(r"^wh_[a-z0-9]+$", sub_id):
        return jsonify({"error": "Invalid subscription id."}), 400
    if not webhooks_module.remove_sub(sub_id):
        return jsonify({"error": "Not found."}), 404
    return jsonify({"ok": True})


@app.route("/webhooks/api/deliveries")
def webhooks_deliveries():
    return jsonify({
        "deliveries":    webhooks_module.recent_deliveries(20),
        "retry_queue":   webhooks_module.retry_queue_stats(),   # Day 22
    })


# Need this for the self-probe latency measurement; track the port we boot on.
_LISTEN_PORT = 8080


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Operator dashboard (Day 19).
# Aggregates KPIs from audit log + leads + matters + monitors into one
# admin-gated dashboard at /dashboard.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/dashboard")
def dashboard_page():
    guard = _require_admin()
    if guard: return guard
    return render_template("dashboard.html")


@app.route("/db/health")
def db_health():
    """Postgres health probe (Day 20). Returns ok+latency+row-counts when
    DATABASE_URL is configured; otherwise reports it's unset.  Admin-gated."""
    guard = _require_admin()
    if guard: return guard
    try:
        import db as db_module
        return jsonify(db_module.health_check())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/dashboard/data.json")
def dashboard_data():
    guard = _require_admin()
    if guard: return guard

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d  = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)

    # ── Read audit records across the last 14 days ─────────────────────────
    audit_dir = Path("outputs/audit")
    records = []
    if audit_dir.exists():
        for f in sorted(audit_dir.glob("audit-*.log"))[-15:]:   # 15 files = enough
            try:
                for line in f.read_text(encoding="utf-8").splitlines():
                    if not line.strip(): continue
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue
            except Exception:
                continue
    # Newest first
    records.sort(key=lambda r: r.get("ts", ""), reverse=True)

    def in_window(r, cutoff):
        ts = r.get("ts", "")
        return ts >= cutoff.isoformat(timespec="seconds")

    # ── KPIs ───────────────────────────────────────────────────────────────
    analyses_all = [r for r in records if r.get("endpoint") in ("/analyze", "/api/v1/analyze")]
    analyses_24h = [r for r in analyses_all if in_window(r, cutoff_24h)]
    analyses_7d  = [r for r in analyses_all if in_window(r, cutoff_7d)]
    errors_24h   = [r for r in analyses_24h if r.get("status") == "error"]

    leads_all = leads_module.list_all()
    leads_7d = [l for l in leads_all if l.get("captured_at", "") >= cutoff_7d.isoformat(timespec="seconds")]

    matters_all = matters_module.list_matters()
    matters_open = [m for m in matters_all if m.get("status") == "open"]

    monitors_data = monitors_module.run_digest()
    monitor_hits_24h = monitors_data.get("totals", {}).get("total_hits", 0)
    matters_watched = monitors_data.get("totals", {}).get("matters_count", 0)

    users_count = auth_module.stats().get("total_users", 0)
    api_keys_active = len([k for k in api_keys_module.list_keys() if not k.get("revoked_at")])

    kpis = {
        "leads_total":     len(leads_all),
        "leads_7d":        len(leads_7d),
        "analyses_total":  len(analyses_all),
        "analyses_24h":    len(analyses_24h),
        "analyses_7d":     len(analyses_7d),
        "matters_total":   len(matters_all),
        "matters_open":    len(matters_open),
        "monitor_hits_24h": monitor_hits_24h,
        "matters_watched": matters_watched,
        "users_total":     users_count,
        "api_keys_active": api_keys_active,
        "errors_24h":      len(errors_24h),
    }

    # ── Funnel (7d) — distinct client_ips across each stage ───────────────
    # Heuristic: an "ip" set per endpoint.  Real conversion tracking would
    # need cookies/sessions, but ip-distinct is good enough for a first pass.
    landing_ips = {r.get("client_ip","") for r in records
                   if in_window(r, cutoff_7d) and r.get("endpoint") == "/"}
    app_ips = {r.get("client_ip","") for r in records
               if in_window(r, cutoff_7d) and r.get("endpoint") == "/app"}
    analyze_ips = {r.get("client_ip","") for r in records
                   if in_window(r, cutoff_7d) and r.get("endpoint") in ("/analyze", "/api/v1/analyze")
                   and r.get("status") == "ok"}
    # /try submissions aren't endpoints — count from leads captured_at
    try_submits_ip = {l.get("captured_at", "") for l in leads_7d}  # placeholder
    # Use the lead count as a reasonable proxy (we don't log /try/submit hits in audit currently)

    funnel = {
        "landing":        max(len(landing_ips), len(app_ips), len(analyze_ips)),
        "try_submitted":  len(leads_7d),
        "app_opened":     len(app_ips),
        "analyzed":       len(analyze_ips),
    }

    # ── Daily analysis volume (last 14 days) ──────────────────────────────
    daily = {}
    for r in analyses_all:
        ts = r.get("ts", "")
        if ts >= cutoff_14d.isoformat(timespec="seconds"):
            d = ts[:10]
            daily[d] = daily.get(d, 0) + 1
    # Build a full 14-day window including zero-days
    dates = []
    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        dates.append({"date": d, "count": daily.get(d, 0)})

    # ── Top retrieved sources (7d) ────────────────────────────────────────
    source_counts = {}
    for r in analyses_7d:
        for sid in (r.get("sources") or []):
            source_counts[sid] = source_counts.get(sid, 0) + 1
    top_sources = [{"id": k, "count": v} for k, v in
                   sorted(source_counts.items(), key=lambda x: -x[1])[:10]]

    # ── Recent analyses (last 8) ──────────────────────────────────────────
    recent_analyses = []
    for r in records[:30]:
        if r.get("endpoint") not in ("/analyze", "/api/v1/analyze"): continue
        recent_analyses.append({
            "ts":           r.get("ts", ""),
            "status":       r.get("status", ""),
            "language":     (r.get("extra") or {}).get("language") or
                            ("hi" if "hi" in str(r.get("extra",{})) else "en"),
            "source_count": len(r.get("sources") or []),
            "duration_ms":  r.get("duration_ms", 0),
            "request_id":   r.get("request_id", ""),
        })
        if len(recent_analyses) >= 8: break

    # ── Recent leads (last 8) ─────────────────────────────────────────────
    recent_leads = leads_all[-8:][::-1] if leads_all else []

    # ── Storage backend indicators (Day 21) ──────────────────────────────────
    storage_backends = {
        "matters":   matters_module.backend(),
        "monitors":  monitors_module.backend(),
        "leads":     leads_module.backend(),
        "nalsa":     nalsa_module.backend(),
        "webhooks":  webhooks_module.backend(),
    }
    # summarise: if any module is on postgres/sqlite, show that; else "json"
    unique = set(storage_backends.values())
    storage_summary = "json" if unique == {"json"} else next(
        (v for v in ("postgres", "sqlite") if v in unique), "mixed"
    )

    return jsonify({
        "generated_at":      now.isoformat(timespec="seconds"),
        "kpis":              kpis,
        "funnel":            funnel,
        "daily_analyses":    dates,
        "top_sources":       top_sources,
        "recent_analyses":   recent_analyses,
        "recent_leads":      recent_leads,
        "storage":           {"backends": storage_backends, "summary": storage_summary},
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — REST API v1 (Day 16).
# Same engines as the UI routes, but wrapped in API-key auth + rate limiting.
# OpenAPI spec at /api/v1/openapi.json; Swagger UI at /api/v1/docs.
# ═══════════════════════════════════════════════════════════════════════════════
def _require_api_key():
    """Verify X-Api-Key header, enforce rate limit. Returns (key_record, error_response)."""
    raw = request.headers.get("X-Api-Key", "")
    if not raw:
        return None, (jsonify({"error": "Missing X-Api-Key header."}), 401)
    key = api_keys_module.verify_key(raw)
    if not key:
        return None, (jsonify({"error": "Invalid or revoked API key."}), 401)
    ok, remaining = api_keys_module.check_rate_limit(key["key_id"], key["rate_per_min"])
    if not ok:
        return None, (jsonify({"error": f"Rate limit exceeded ({key['rate_per_min']}/min)."}), 429)
    return key, None


@app.route("/api/v1/openapi.json")
def api_openapi_json():
    return jsonify(openapi_spec_module.spec())


@app.route("/api/v1/docs")
def api_docs():
    """Swagger UI page — pure HTML, loads swagger-ui from CDN."""
    return """<!DOCTYPE html>
<html><head>
  <meta charset="UTF-8"><title>Lex-Indic API — Swagger UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head><body>
  <div id="swagger"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => SwaggerUIBundle({
      url: "/api/v1/openapi.json",
      dom_id: "#swagger",
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
    });
  </script>
</body></html>"""


@app.route("/api/v1/health")
def api_health():
    """No auth required — for k8s liveness, monitoring, etc."""
    import time as _t
    return jsonify({
        "ok": True,
        "version": "1.0.0",
        "uptime_s": int((datetime.now(timezone.utc) - _SERVER_STARTED_AT).total_seconds()),
    })


@app.route("/api/v1/analyze", methods=["POST"])
def api_analyze():
    key, err = _require_api_key()
    if err: return err
    # Delegate to the existing /analyze handler logic — just call the function.
    # Simplest path: forward the JSON to the existing route via test client?
    # No — duplicate the minimum logic so we don't lose request context.
    data = request.get_json() or {}
    story = (data.get("client_story") or "").strip()
    if not story or len(story) < 30:
        return jsonify({"error": "client_story must be ≥30 chars"}), 400

    # Reuse the existing retrieval + Groq pipeline directly
    try:
        retrieved_context, sources = retrieve_relevant_sections_structured(
            rag_collection, story, n_results=8,
        )
        prompt = build_legal_prompt(story, retrieved_context)
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": LEXI_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2, max_tokens=8192,
        )
        ai_response = completion.choices[0].message.content
        txt_path = save_raw_output(story, ai_response)
        pdf_path = generate_pdf(txt_path)
        with open(txt_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        sections = parse_sections(raw_text)
        for k in sections:
            if isinstance(sections[k], str):
                sections[k] = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", sections[k])
        request_id = audit.log_request(
            endpoint="/api/v1/analyze",
            client_ip=request.remote_addr or "",
            user_agent=f"api-key:{key['key_id']}",
            story=story, sources=sources, status="ok",
            duration_ms=0, response_chars=len(ai_response or ""),
            pdf_filename=Path(pdf_path).name,
            extra={"user_id": key["user_id"], "firm_id": key.get("firm_id") or None,
                   "api_key_id": key["key_id"]},
        )
        return jsonify({
            "sections": sections, "client_statement": story,
            "pdf_filename": Path(pdf_path).name, "sources": sources,
            "language": "en", "request_id": request_id,
        })
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)[:200]}"}), 500


@app.route("/api/v1/convert/text", methods=["POST"])
def api_convert_text():
    key, err = _require_api_key()
    if err: return err
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    if len(text) > 200_000:
        return jsonify({"error": "text too large (>200,000 chars)"}), 400
    annotated, summary = convert_text(text)
    return jsonify({"annotated": annotated, "summary": summary.to_dict()})


@app.route("/api/v1/ecourts/lookup/<cnr>")
def api_ecourts_lookup(cnr):
    key, err = _require_api_key()
    if err: return err
    cnr_norm = ecourts_module.normalize_cnr(cnr)
    if not ecourts_module.is_valid_cnr(cnr_norm):
        return jsonify({"error": "invalid CNR format"}), 400
    result = ecourts_module.fetch_cnr_status(cnr_norm)
    if not result:
        return jsonify({"error": "CNR not found"}), 404
    return jsonify(result)


@app.route("/api/v1/monitors/digest")
def api_monitors_digest():
    key, err = _require_api_key()
    if err: return err
    since = request.args.get("since")
    return jsonify(monitors_module.run_digest(since=since))


@app.route("/api/v1/sections")
def api_sections():
    key, err = _require_api_key()
    if err: return err
    kind = (request.args.get("kind") or "all").lower()
    out = []
    # BNS
    if kind in ("bns", "all"):
        import data.bns_knowledge_base as bns_kb
        for s in bns_kb.BNS_SECTIONS:
            out.append({"id": s["id"], "kind": "bns", **{
                k: s[k] for k in ("section", "old_ipc", "title", "punishment",
                                  "bailable", "cognizable", "transition_note")
            }})
    # BNSS + BSA
    if kind in ("bnss", "bsa", "all"):
        try:
            import data.bnss_bsa_knowledge_base as b_kb
            for s in b_kb.BNSS_SECTIONS + b_kb.BSA_SECTIONS:
                k = "bnss" if s["id"].startswith("bnss_") else "bsa"
                if kind in (k, "all"):
                    out.append({"id": s["id"], "kind": k, **{
                        x: s[x] for x in ("section", "old_ipc", "title", "punishment",
                                          "bailable", "cognizable", "transition_note")
                    }})
        except ImportError:
            pass
    return jsonify({"sections": out, "count": len(out)})


@app.route("/api/v1/leads", methods=["POST"])
def api_leads():
    key, err = _require_api_key()
    if err: return err
    data = request.get_json() or {}
    ok, msg = leads_module.validate(data)
    if not ok:
        return jsonify({"error": msg}), 400
    lead = leads_module.capture(data, referrer="api-key:"+key["key_id"],
                                user_agent=request.headers.get("User-Agent", ""))
    try:
        webhooks_module.emit("lead.captured", {
            "lead_id": lead.id, "email": lead.email,
            "firm_or_org": lead.firm_or_org, "via": "api",
        })
    except Exception:
        pass
    return jsonify({"lead": {"id": lead.id, "full_name": lead.full_name}})


# ─── Admin endpoints to manage API keys ────────────────────────────────────
@app.route("/admin/api-keys", methods=["GET", "POST"])
def admin_api_keys():
    """Sign-in-required: list / issue API keys for the current user."""
    user = _current_user()
    if not user:
        # Allow ADMIN_TOKEN to act as a superuser for ops
        guard = _require_admin()
        if guard: return guard
        if request.method == "GET":
            return jsonify({"keys": api_keys_module.list_keys()})
        # POST without user — must specify user_id
        data = request.get_json() or {}
        if not data.get("user_id"):
            return jsonify({"error": "user_id required when calling as admin"}), 400
        try:
            key = api_keys_module.issue_key(
                user_id=data["user_id"], firm_id=data.get("firm_id", ""),
                label=data.get("label", "admin-issued"),
                rate_per_min=int(data.get("rate_per_min", 60)),
            )
            return jsonify({"key": key})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    if request.method == "GET":
        return jsonify({"keys": api_keys_module.list_keys(user_id=user["id"])})
    data = request.get_json() or {}
    try:
        key = api_keys_module.issue_key(
            user_id=user["id"],
            firm_id=user.get("firm_id") or "",
            label=data.get("label", ""),
            rate_per_min=int(data.get("rate_per_min", 60)),
        )
        return jsonify({"key": key})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/admin/api-keys/<key_id>", methods=["DELETE"])
def admin_api_key_revoke(key_id):
    user = _current_user()
    if not user:
        guard = _require_admin()
        if guard: return guard
    if not re.match(r"^lex_live_[a-f0-9]+$", key_id):
        return jsonify({"error": "invalid key id"}), 400
    if not api_keys_module.revoke_key(key_id):
        return jsonify({"error": "key not found or already revoked"}), 404
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="lex-indic",
        description="Lex-Indic — BNS Transition Engine. Run with --https for the Word add-in.",
    )
    parser.add_argument(
        "--https",
        action="store_true",
        help="Run with TLS on port 8443 using certs/dev-cert.pem (required for "
             "the Microsoft Word add-in, which only loads HTTPS URLs).",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Bind host (default 0.0.0.0; use 127.0.0.1 for air-gapped).",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Port to listen on (defaults to 8080 for HTTP, 8443 for HTTPS).",
    )
    args = parser.parse_args()

    if args.https:
        cert = Path("certs/dev-cert.pem")
        key = Path("certs/dev-key.pem")
        if not (cert.exists() and key.exists()):
            print(
                "ERROR: certs/dev-cert.pem or certs/dev-key.pem not found.\n"
                "Generate them with:\n"
                "  openssl req -x509 -newkey rsa:2048 -nodes \\\n"
                "    -keyout certs/dev-key.pem -out certs/dev-cert.pem \\\n"
                '    -days 365 -subj "/CN=localhost" \\\n'
                '    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"\n'
            )
            sys.exit(1)

        port = args.port or 8443
        print(f"  Open your browser at: https://localhost:{port}")
        print(f"  Word add-in install:  https://localhost:{port}/addin/install\n")
        app.run(
            debug=False, host=args.host, port=port,
            ssl_context=(str(cert), str(key)),
        )
    else:
        port = args.port or 8080
        print(f"  Open your browser at: http://localhost:{port}\n")
        app.run(debug=False, host=args.host, port=port)
