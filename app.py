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
    if request.method == "GET":
        return jsonify({"firms": matters_module.list_firms()})
    data = request.get_json() or {}
    try:
        firm = matters_module.add_firm(data.get("name", ""), data.get("address", ""))
        return jsonify({"firm": firm})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/matters/api/lawyers", methods=["GET", "POST"])
def matters_lawyers():
    if request.method == "GET":
        return jsonify({"lawyers": matters_module.list_lawyers()})
    data = request.get_json() or {}
    try:
        lwy = matters_module.add_lawyer(
            firm_id=data.get("firm_id", ""),
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
    if request.method == "GET":
        return jsonify({"matters": matters_module.list_matters()})
    data = request.get_json() or {}
    try:
        m = matters_module.add_matter(
            firm_id=data.get("firm_id", ""),
            lawyer_id=data.get("lawyer_id", ""),
            client_name=data.get("client_name", ""),
            opposing_party=data.get("opposing_party", ""),
            matter_type=data.get("matter_type", ""),
            description=data.get("description", ""),
        )
        # Conflict check is informational, not blocking
        conflicts = matters_module.check_conflict(
            firm_id=data.get("firm_id", ""),
            client_name=data.get("client_name", ""),
            opposing_party=data.get("opposing_party", ""),
        )
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

    # Accept multipart/form-data (with files) OR plain JSON
    ct = request.content_type or ""
    if "multipart" in ct or "form" in ct:
        client_story    = request.form.get("client_story", "").strip()
        additional_info = request.form.get("additional_info", "").strip()
        uploaded_files  = request.files.getlist("attachments")
        # Day-4: optional output-language flag.  Accepted values: 'en', 'hi'.
        # Anything else falls back to English silently.
        language        = (request.form.get("language") or "en").lower()
    else:
        data            = request.get_json() or {}
        client_story    = data.get("client_story", "").strip()
        additional_info = data.get("additional_info", "").strip()
        uploaded_files  = []
        language        = (data.get("language") or "en").lower()
    if language not in ("en", "hi"):
        language = "en"

    if not client_story:
        rid = audit.log_request(
            endpoint="/analyze", client_ip=client_ip, user_agent=user_agent,
            story="", status="error", duration_ms=int((time.monotonic() - t_start) * 1000),
            error="empty client_story",
        )
        return jsonify({"error": "Please enter the client's story.", "request_id": rid}), 400

    if len(client_story) < 30:
        rid = audit.log_request(
            endpoint="/analyze", client_ip=client_ip, user_agent=user_agent,
            story=client_story, status="error",
            duration_ms=int((time.monotonic() - t_start) * 1000),
            error="story too short",
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
        messages = [{"role": "system", "content": LEXI_SYSTEM_PROMPT}]
        if language == "hi":
            messages.append({"role": "system", "content": i18n_module.HINDI_SYSTEM_INSTRUCTION})
        messages.append({"role": "user", "content": prompt})

        ai_response = None
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
        )

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
