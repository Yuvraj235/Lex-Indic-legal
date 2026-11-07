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
import html as _html
import hashlib
import hmac
import secrets
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
import envmode
envmode.check_production_config()   # no signing secret → refuse to boot
app = Flask(__name__)

# Behind a reverse proxy (Fly, Render, nginx), trust exactly TRUST_PROXY_HOPS
# hops of X-Forwarded-For/-Proto: remote_addr becomes the address the proxy
# saw and request.scheme the client's real scheme (so the session cookie gets
# Secure). Unset = no proxy trusted; a client-sent X-Forwarded-For is ignored.
from werkzeug.middleware.proxy_fix import ProxyFix
_PROXY_HOPS = int(os.getenv("TRUST_PROXY_HOPS", "0") or 0)
if _PROXY_HOPS > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_PROXY_HOPS, x_proto=_PROXY_HOPS)


def _section_html(text: str) -> str:
    """Model output → safe HTML for the browser. The text echoes the client's
    story, uploaded documents and WhatsApp messages, so it's escaped first;
    only **bold** is then turned back into markup."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _html.escape(text, quote=False))


def _client_ip() -> str:
    """The caller's address for quotas and the audit log. Never read
    X-Forwarded-For directly — anyone can send one."""
    return request.remote_addr or ""


def _per_ip_limit(bucket: str, per_minute: int):
    """429 response when this IP exceeds `per_minute` calls to `bucket`, else
    None. For public endpoints that spend LLM credits on every call."""
    allowed, _ = api_keys_module.check_rate_limit(f"{bucket}:{_client_ip()}", per_minute)
    if allowed:
        return None
    return jsonify({"error": "Too many requests. Wait a minute and try again."}), 429
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True


# ─── Polish: request_id middleware ──────────────────────────────────────────
import uuid as _uuid_mod
@app.before_request
def _attach_request_id():
    # Reuse a caller's X-Request-Id only if it looks like an id: it's echoed
    # into logs and response headers.
    supplied = request.headers.get("X-Request-Id", "")
    request.request_id = (
        supplied if re.fullmatch(r"[A-Za-z0-9_.\-]{1,64}", supplied)
        else f"req_{_uuid_mod.uuid4().hex[:14]}"
    )


# Whole-request cap, checked before Flask reads the body into memory: without
# it one oversized upload to /analyze, /convert or /tabular could exhaust RAM.
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_REQUEST_MB", "25")) * 1024 * 1024

# Endpoints called by other services, not browsers: no Origin check.
_ORIGIN_EXEMPT = ("/wa/inbound", "/billing/stripe-webhook", "/api/v1/")


@app.before_request
def _reject_cross_site_writes():
    """Defence in depth on top of SameSite=Lax cookies: a state-changing
    request that carries a browser Origin must come from this site (or a
    CORS-allowlisted origin). Requests without Origin (curl, servers) pass —
    they carry no ambient browser cookies to abuse."""
    if request.method in ("GET", "HEAD", "OPTIONS") or request.path.startswith(_ORIGIN_EXEMPT):
        return None
    origin = request.headers.get("Origin")
    if not origin:
        return None
    if origin.rstrip("/") == request.host_url.rstrip("/") or _cors_allowed_origin():
        return None
    return jsonify({"error": "Cross-site request refused."}), 403


@app.errorhandler(413)
def _too_large(e):
    return jsonify({"error": "Upload too large. "
                             f"The limit is {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB."}), 413


@app.after_request
def _security_headers(response):
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "camera=(), geolocation=(self), microphone=(self), payment=()")
    if request.path.startswith("/addin/"):
        # Word frames the task pane; everything else may not be framed at all.
        h.setdefault("Content-Security-Policy",
                     "object-src 'none'; base-uri 'self'; frame-ancestors 'self' "
                     "https://*.office.com https://*.officeapps.live.com https://*.microsoft.com")
    else:
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Content-Security-Policy",
                     "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
    if request.is_secure:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.after_request
def _emit_request_id(response):
    """Set X-Request-Id header on every response so the user can quote it
    when filing a bug report."""
    if hasattr(request, "request_id"):
        response.headers["X-Request-Id"] = request.request_id
    return response


# ─── Friendly error pages (polish sprint) ───────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html",
        code=404,
        title="Page not found",
        message="The URL you requested doesn't exist. Try one of the links below."
    ), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template("error.html",
        code=500,
        title="Something broke",
        message="An internal error occurred. The team has been notified. Try again in a moment."
    ), 500


@app.errorhandler(429)
def rate_limited(e):
    return render_template("error.html",
        code=429,
        title="Rate limit hit",
        message="You're going too fast. Wait a moment and try again, or upgrade your tier at /pricing."
    ), 429

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
from ipc_bns_converter import convert_text, convert_docx, convert_text_multi_summary


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

    # v1.9: multi-statute pass — IPC→BNS plus CrPC→BNSS and Evidence Act→BSA
    # (previously only the migration audit used the multi maps).
    annotated, summary = convert_text_multi_summary(text)
    return jsonify({
        "annotated": annotated,
        "summary": summary,
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
    # The download link is the only access control for a converted pleading,
    # so the name carries 64 random bits instead of being guessable.
    out_name = f"{safe}_{ts}_{secrets.token_hex(8)}.bns.docx"
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
    if not re.match(r"^[A-Za-z0-9_\-]+_\d{8}_\d{6}_[0-9a-f]{16}\.bns\.docx$", filename):
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
import pricing as pricing_module   # Day 23
import cron as cron_module          # Day 24
import sms as sms_module            # Day 25
import erasure as erasure_module    # Day 28 (DPDP)
import billing as billing_module    # Day 31 (Stripe)
import prefs as prefs_module         # Day 34 (notification preferences)
import uploads as uploads_module     # Day 35 (per-matter document storage)
import verifier as verifier_module   # v1.9 — runtime citation verification
import case_access                   # who may read a generated case file
import statute_lookup                # table answers: IPC→BNS, bailable, punishment
import mailer as mailer_module       # pluggable email (stdout / SMTP / SES)


@app.route("/monitors")
def monitors_page():
    return render_template("monitors.html")


def _monitor_owner():
    """(owner, None) for whoever's watching: "*" for the operator (all
    monitors), else the caller's firm — or their user id if they have none."""
    if _is_admin_request():
        return "*", None
    u = _current_user()
    if not u:
        return None, (jsonify({"error": "Sign in to manage your watchlist."}), 401)
    return (u.get("firm_id") or u["id"]), None


def _scope(owner: str):
    return None if owner == "*" else owner


@app.route("/monitors/api/matters", methods=["GET"])
def monitors_list_matters():
    owner, err = _monitor_owner()
    if err:
        return err
    return jsonify({"matters": monitors_module.list_matters(_scope(owner))})


@app.route("/monitors/api/matters", methods=["POST"])
def monitors_add_matter():
    owner, err = _monitor_owner()
    if err:
        return err
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
    saved = monitors_module.add_matter(label, keywords=keywords, sections=sections,
                                       owner=owner)
    return jsonify({"matter": saved})


@app.route("/monitors/api/matters/<matter_id>", methods=["DELETE"])
def monitors_remove_matter(matter_id):
    owner, err = _monitor_owner()
    if err:
        return err
    if not re.match(r"^m_\d+(?:_[0-9a-f]{6})?$", matter_id):
        return jsonify({"error": "Invalid matter id."}), 400
    ok = monitors_module.remove_matter(matter_id, _scope(owner))
    if not ok:
        return jsonify({"error": "Matter not found."}), 404
    return jsonify({"ok": True})


@app.route("/monitors/api/digest", methods=["GET"])
def monitors_digest():
    owner, err = _monitor_owner()
    if err:
        return err
    since = request.args.get("since")  # optional YYYY-MM-DD
    d = monitors_module.run_digest(since=since, owner=_scope(owner))
    if request.args.get("save") == "1":
        monitors_module.save_digest(d)
    return jsonify(d)


@app.route("/monitors/digest.txt")
def monitors_digest_text():
    """Plain-text digest — pipe-friendly for cron + email."""
    owner, err = _monitor_owner()
    if err:
        return err
    d = monitors_module.run_digest(owner=_scope(owner))
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

    # Day 25 — WhatsApp welcome message (fire-and-forget on a thread)
    if reg.phone:
        import threading, sms as sms_module
        threading.Thread(
            target=sms_module.send_nalsa_welcome,
            kwargs={"phone": reg.phone, "panel_id": reg.panel_id},
            daemon=True,
        ).start()

    return jsonify({"registration": reg.to_dict()})


@app.route("/nalsa/api/stats")
def nalsa_stats():
    return jsonify(nalsa_module.stats())


@app.route("/nalsa/api/export.csv")
def nalsa_export_csv():
    """SLSA spot-check CSV of registered advocates (names, phones, Bar Council
    numbers). Needs the SLSA's NALSA_EXPORT_TOKEN in X-Export-Token, or the
    operator's admin token — never open by default."""
    export_token = os.getenv("NALSA_EXPORT_TOKEN", "")
    provided = request.headers.get("X-Export-Token", "")
    if not (export_token and provided
            and hmac.compare_digest(provided.encode(), export_token.encode())):
        guard = _require_admin()
        if guard:
            return guard
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
    """Multi-tenant rules (sign-in required):
      GET  — the caller's own firm only ([] until they create or join one).
      POST — create a firm; the creator becomes its 'partner'. A user who
             already belongs to a firm can't create another; colleagues join
             through a partner's invite (/auth/invites → /auth/bind-firm).
      Polish: stricter input validation (no HTML/JS/null bytes, length caps)."""
    import response_helpers as _rh
    u = _current_user()
    if not u:
        return jsonify({"error": "Sign in to manage your firm."}), 401
    if request.method == "GET":
        firms = [f for f in matters_module.list_firms()
                 if u.get("firm_id") and f["id"] == u["firm_id"]]
        return jsonify({"firms": firms})
    if u.get("firm_id"):
        return _rh.error("You already belong to a firm.", status=409, code="already_bound")

    data = request.get_json(silent=True) or {}
    # Validate inputs
    name, err = _rh.require_string(data, "name", min_len=2, max_len=120)
    if err:
        return _rh.error(err, status=422, code="validation_failed")
    address = (data.get("address") or "").strip()[:200]
    # Reject HTML-shaped inputs (basic XSS guard)
    if "<" in name or ">" in name or "<" in address or ">" in address:
        return _rh.error("Firm name and address cannot contain '<' or '>'.",
                          status=422, code="invalid_characters")

    try:
        firm = matters_module.add_firm(name, address)
        auth_module.bind_user_to_firm(u["id"], firm["id"], role="partner")
        return jsonify({"ok": True, "firm": firm})
    except ValueError as e:
        return _rh.error(str(e), status=409, code="duplicate")


def _require_firm_user():
    """(user, None) for a signed-in user who belongs to a firm, else
    (None, error_response). Every matters endpoint is scoped by this firm_id —
    never by a firm_id the caller sends."""
    u = _current_user()
    if not u:
        return None, (jsonify({"error": "Sign in to use matters."}), 401)
    if not u.get("firm_id"):
        return None, (jsonify({"error": "Create your firm or redeem an invite first."}), 403)
    return u, None


@app.route("/matters/api/lawyers", methods=["GET", "POST"])
def matters_lawyers():
    u, err = _require_firm_user()
    if err:
        return err
    if request.method == "GET":
        return jsonify({"lawyers": matters_module.list_lawyers_for_firm(u["firm_id"])})
    data = request.get_json() or {}
    firm_id = u["firm_id"]
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
    u, err = _require_firm_user()
    if err:
        return err
    if request.method == "GET":
        return jsonify({"matters": matters_module.list_matters(firm_id=u["firm_id"])})
    data = request.get_json() or {}
    firm_id = u["firm_id"]
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
            }, firm_id=m["firm_id"])
        except Exception:  # noqa: BLE001 — never fail the user's request
            app.logger.exception("webhook emit failed")
        return jsonify({"matter": m, "conflicts": conflicts})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


def _matter_or_403(matter_id: str):
    """Tenant guard for per-matter routes. Returns (matter, None) if the caller
    may touch this matter, else (None, error_response). Only a signed-in member
    of the matter's firm gets through; a cross-tenant matter id returns 404 so
    its existence isn't even revealed."""
    u, err = _require_firm_user()
    if err:
        return None, err
    m = matters_module.get_matter_for_firm(matter_id, u["firm_id"])
    if not m:
        return None, (jsonify({"error": "Matter not found."}), 404)
    return m, None


@app.route("/matters/api/conflict-check", methods=["POST"])
def matters_conflict_check():
    """Pre-create conflict check — call before adding a matter. Runs only
    within the caller's own firm: never probe another firm's client /
    opposing-party graph."""
    u, err = _require_firm_user()
    if err:
        return err
    data = request.get_json() or {}
    hits = matters_module.check_conflict(
        firm_id=u["firm_id"],
        client_name=data.get("client_name", ""),
        opposing_party=data.get("opposing_party", ""),
    )
    return jsonify({"conflicts": hits})


@app.route("/matters/api/<path:matter_id>/status", methods=["PATCH"])
def matters_status(matter_id):
    if not re.match(r"^[A-Z]+/\d{4}/\d{4}$", matter_id):
        return jsonify({"error": "Invalid matter ID."}), 400
    _, err = _matter_or_403(matter_id)   # block cross-tenant status writes
    if err:
        return err
    data = request.get_json() or {}
    ok = matters_module.update_matter_status(matter_id, data.get("status", ""))
    if not ok:
        return jsonify({"error": "Matter not found or invalid status."}), 400
    return jsonify({"ok": True})


@app.route("/matters/api/<path:matter_id>/soft-delete", methods=["POST"])
def matters_soft_delete(matter_id):
    """Day 26: Admin-only soft-delete (the matter stays in DB; hidden from lists)."""
    guard = _require_admin()
    if guard: return guard
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    ok = matters_module.soft_delete_matter(matter_id, reason=reason)
    return (jsonify({"ok": True, "matter_id": matter_id, "reason": reason}) if ok
            else (jsonify({"error": "Matter not found."}), 404))


@app.route("/matters/api/<path:matter_id>/restore", methods=["POST"])
def matters_restore(matter_id):
    """Day 26: Admin-only restore — undoes soft-delete."""
    guard = _require_admin()
    if guard: return guard
    ok = matters_module.restore_matter(matter_id)
    return (jsonify({"ok": True, "matter_id": matter_id}) if ok
            else (jsonify({"error": "Matter not found."}), 404))


# ─── Day 35: per-matter file storage ────────────────────────────────────────
@app.route("/matters/api/<path:matter_id>/files", methods=["GET", "POST"])
def matters_files(matter_id):
    """GET = list files for matter. POST = upload one (multipart/form-data)."""
    matter, err = _matter_or_403(matter_id)   # tenant-scoped: no cross-firm file access
    if err:
        return err

    if request.method == "GET":
        return jsonify({"matter_id": matter_id,
                         "files": uploads_module.list_files(matter_id)})

    # POST — multipart upload
    if "file" not in request.files:
        return jsonify({"error": "Provide a file in the 'file' field."}), 400
    f = request.files["file"]
    user = _current_user() or {}
    try:
        meta = uploads_module.add_file(
            matter_id=matter_id,
            original_name=f.filename or "untitled",
            file_bytes=f.read(),
            content_type=f.content_type or "application/octet-stream",
            uploaded_by=user.get("email", ""),
            description=request.form.get("description", ""),
        )
        return jsonify({"file": meta}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/matters/api/<path:matter_id>/files/<file_id>", methods=["GET", "DELETE"])
def matters_file_detail(matter_id, file_id):
    """GET = download file. DELETE = remove (admin only)."""
    if request.method == "DELETE":
        guard = _require_admin()
        if guard: return guard
        ok = uploads_module.delete_file(matter_id, file_id)
        return (jsonify({"ok": True}) if ok
                else (jsonify({"error": "File not found."}), 404))
    # GET — serve the file (tenant-scoped: a firm can't download another's files)
    _, err = _matter_or_403(matter_id)
    if err:
        return err
    path = uploads_module.get_file_path(matter_id, file_id)
    if not path or not path.exists():
        return ("File not found.", 404)
    meta = uploads_module.get_file_meta(matter_id, file_id)
    return send_from_directory(path.parent, path.name,
                                  as_attachment=True,
                                  download_name=(meta or {}).get("original_name", path.name))


@app.route("/admin/uploads/stats")
def admin_uploads_stats():
    guard = _require_admin()
    if guard: return guard
    return jsonify(uploads_module.total_storage_used())


@app.route("/admin/readiness")
def admin_readiness():
    """Operator go-live checklist: which subsystems are demo (stub) vs live,
    and what's left to flip before launch. Drives the demo/live UI badges too."""
    guard = _require_admin()
    if guard: return guard
    import readiness
    return jsonify(readiness.gather_readiness())


@app.route("/audit")
def audit_page():
    """Statute Migration Audit — scan a document set for outdated IPC/CrPC/IEA refs."""
    return render_template("audit.html")


@app.route("/audit/api/scan", methods=["POST"])
def audit_scan():
    """Scan uploaded docs (multipart 'files') OR JSON {"docs":[{name,text}]} →
    aggregate migration-audit report. Reuses migration_audit; unmapped refs are
    reported honestly, never guessed."""
    import migration_audit as ma
    if request.is_json:
        data = request.get_json(silent=True) or {}
        docs = [ma.audit_text(d.get("name", "doc"), d.get("text", ""))
                for d in (data.get("docs") or [])]
        return jsonify(ma.aggregate(docs).to_dict())
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Upload files in the 'files' field, or POST JSON "
                                 "{\"docs\": [{\"name\", \"text\"}]}."}), 400
    import tempfile
    from werkzeug.utils import secure_filename
    docs = []
    with tempfile.TemporaryDirectory() as td:
        for f in files:
            if not f.filename:
                continue
            name = secure_filename(f.filename) or "doc"
            if Path(name).suffix.lower() not in ma.SUPPORTED_SUFFIXES:
                continue
            p = Path(td) / name
            f.save(str(p))
            try:
                docs.append(ma.audit_text(f.filename, ma.extract_text(p)))
            except Exception:  # noqa: BLE001 — one bad upload shouldn't fail the scan
                continue
    return jsonify(ma.aggregate(docs).to_dict())


# ─── WhatsApp inbound intake → draft → file ─────────────────────────────────
def _wa_draft(story: str) -> str:
    """Generate a draft from an intake story, reusing the warm RAG + Groq path."""
    from main import LEXI_SYSTEM_PROMPT
    ctx, _sources = retrieve_relevant_sections_structured(
        rag_collection, story, n_results=6)
    prompt = build_legal_prompt(story, ctx)
    return llm_provider_module.groq_complete(
        groq_client,
        [{"role": "system", "content": LEXI_SYSTEM_PROMPT},
         {"role": "user", "content": prompt}],
        temperature=0.2, max_tokens=4096)


def _wa_file_draft(sender: str, story: str, draft: str) -> str:
    """File the intake story + draft into a per-sender folder. Returns the ref.

    v1.9: drafts are filed as PENDING ADVOCATE REVIEW — the verifier verdict is
    stored alongside so the reviewing advocate sees the citation check first.
    """
    import re as _re
    from datetime import datetime
    safe = _re.sub(r"[^0-9A-Za-z]", "_", sender)
    folder = Path("outputs/wa_intake") / f"{safe}_{datetime.now():%Y%m%d_%H%M%S}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "intake_story.txt").write_text(story, encoding="utf-8")
    try:
        verification = verifier_module.verify_analysis(parse_sections(draft))
        stamp = verifier_module.verification_stamp(verification)
    except Exception:  # noqa: BLE001 — verification must never block filing
        verification, stamp = None, "CITATION CHECK: could not run."
    header = ("STATUS: PENDING ADVOCATE REVIEW — AI-generated draft, "
              "not approved for filing.\n" + stamp + "\n"
              + "═" * 70 + "\n\n")
    (folder / "draft.txt").write_text(header + draft, encoding="utf-8")
    (folder / "status.json").write_text(json.dumps({
        "status": "pending_review",
        "verification": verification,
        "filed_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(folder.relative_to(Path("outputs")))


def _wa_inbound_authorised(is_twilio: bool) -> bool:
    """Only the messaging provider may call /wa/inbound — otherwise anyone could
    speak as any client's phone number and trigger drafting.
      Twilio: X-Twilio-Signature = base64(HMAC-SHA1(TWILIO_AUTH_TOKEN,
              URL + sorted form name/value pairs)). Set WA_PUBLIC_URL if the
              URL Twilio calls differs from what this server sees.
      MSG91 / n8n (can't sign): WA_INBOUND_TOKEN in the X-Lex-Inbound-Token
              header or ?token= on the webhook URL.
    With neither configured it's closed, except under LEX_ENV=development."""
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    shared = os.getenv("WA_INBOUND_TOKEN", "")
    if is_twilio and twilio_token:
        url = os.getenv("WA_PUBLIC_URL") or request.url
        signed = url + "".join(k + v for k, v in sorted(request.form.items(multi=True)))
        expected = base64.b64encode(
            hmac.new(twilio_token.encode(), signed.encode(), hashlib.sha1).digest()).decode()
        return hmac.compare_digest(expected, request.headers.get("X-Twilio-Signature", ""))
    if shared:
        provided = request.headers.get("X-Lex-Inbound-Token") or request.args.get("token", "")
        return bool(provided) and hmac.compare_digest(provided.encode(), shared.encode())
    return envmode.is_dev()


@app.route("/wa/inbound", methods=["POST"])
def wa_inbound():
    """Inbound WhatsApp webhook (Twilio form OR MSG91/generic JSON). Runs a
    multi-turn intake; on completion drafts via the analysis pipeline, files it,
    and replies (TwiML for Twilio, JSON otherwise)."""
    import intake as intake_module
    is_twilio = bool(request.form.get("From") or request.form.get("Body"))
    if not _wa_inbound_authorised(is_twilio):
        return jsonify({"error": "Unauthorised inbound webhook."}), 403
    form = request.form.to_dict() if request.form else {}
    body = request.get_json(silent=True) if request.is_json else None
    sender, text = intake_module.parse_inbound(form, body)
    if not sender:
        return jsonify({"error": "Could not determine sender."}), 400

    session = intake_module.load_session(sender)
    session, reply = intake_module.handle_message(session, text or "")

    draft_ref = None
    if session.done:
        story = intake_module.compose_story(session)
        try:
            draft_ref = _wa_file_draft(sender, story, _wa_draft(story))
            reply += f"\n\n(Draft filed: {draft_ref})"
        except Exception as e:  # noqa: BLE001 — reply even if drafting fails
            print(f"[wa] draft failed for {sender}: {e}")
        intake_module.clear_session(sender)
    else:
        intake_module.save_session(session)

    if is_twilio:
        from xml.sax.saxutils import escape
        twiml = (f"<?xml version='1.0' encoding='UTF-8'?>"
                 f"<Response><Message>{escape(reply)}</Message></Response>")
        return app.response_class(twiml, mimetype="application/xml")
    return jsonify({"reply": reply, "done": session.done, "draft": draft_ref})


# ─── Day 36: per-matter analysis history (read audit log filtered by matter_id) ─
@app.route("/matters/api/<path:matter_id>/history", methods=["GET"])
def matters_history(matter_id):
    """Returns every /analyze + /chat call ever made with matter_id=<id>.
    Reads from outputs/audit/audit-*.log."""
    matter, err = _matter_or_403(matter_id)   # tenant-scoped analysis history
    if err:
        return err

    audit_dir = Path("outputs/audit")
    entries: list[dict] = []
    if audit_dir.exists():
        for log_file in sorted(audit_dir.glob("audit-*.log"))[-30:]:  # last 30 days
            try:
                for line in log_file.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if (rec.get("extra") or {}).get("matter_id") == matter_id:
                        entries.append({
                            "request_id":   rec.get("request_id"),
                            "ts":           rec.get("ts"),
                            "endpoint":     rec.get("endpoint"),
                            "status":       rec.get("status"),
                            "duration_ms":  rec.get("duration_ms"),
                            "pdf_filename": rec.get("pdf_filename"),
                            "story_hash":   rec.get("story_hash"),
                            "sources":      len(rec.get("sources") or []),
                            "tier":         (rec.get("extra") or {}).get("pricing_tier"),
                        })
            except Exception:
                continue
    entries.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return jsonify({
        "matter_id":     matter_id,
        "client_name":   matter.get("client_name"),
        "history_count": len(entries),
        "history":       entries[:100],   # cap at 100 most recent
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Multi-tenant auth (Day-10).
# Magic-link login: POST /auth/code, POST /auth/verify, GET /auth/me, /auth/logout.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/login")
def login_page():
    return render_template("login.html", dev_mode=envmode.is_dev())


@app.route("/auth/code", methods=["POST"])
def auth_code():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    limited = _per_ip_limit("auth-code", 10)
    if limited:
        return limited
    try:
        code = auth_module.issue_code(email)
    except auth_module.RateLimited as e:
        return jsonify({"error": str(e)}), 429
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    # Only an explicit LEX_ENV=development echoes the code back; everywhere
    # else the mail provider delivers it.
    resp = {"ok": True}
    if envmode.is_dev():
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
    """Signs this user out everywhere: the cookie is cleared here and every
    token issued before now stops working, including a copied one."""
    user_id = auth_module.verify_session_token(request.cookies.get("lex_session", ""))
    if user_id:
        auth_module.revoke_sessions(user_id)
    response = make_response(jsonify({"ok": True}))
    response.set_cookie("lex_session", "", expires=0)
    return response


@app.route("/auth/invites", methods=["POST"])
def auth_create_invite():
    """A partner mints a single-use invite code for their own firm."""
    u, err = _require_firm_user()
    if err:
        return err
    if u.get("role") != "partner":
        return jsonify({"error": "Only a partner can invite people to the firm."}), 403
    data = request.get_json(silent=True) or {}
    try:
        invite = auth_module.create_invite(
            u["firm_id"], role=(data.get("role") or "associate").strip(),
            created_by=u["id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(invite)


@app.route("/auth/bind-firm", methods=["POST"])
def auth_bind_firm():
    """Join a firm by redeeming a partner's invite code. The firm and the
    role both come from the invite — never from the caller."""
    u = _current_user()
    if not u:
        return jsonify({"error": "Not signed in."}), 401
    if u.get("firm_id"):
        return jsonify({"error": "You already belong to a firm."}), 409
    data = request.get_json(silent=True) or {}
    code = (data.get("invite_code") or "").strip()
    if not code:
        return jsonify({"error": "invite_code is required."}), 400
    firm_id = auth_module.redeem_invite(code, u["id"])
    if not firm_id:
        return jsonify({"error": "Invalid, used or expired invite."}), 400
    return jsonify({"ok": True, "firm_id": firm_id})


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
    limited = _per_ip_limit("tabular", 5)
    if limited:
        return limited
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
        return llm_provider_module.groq_complete(
            groq_client,
            [{"role": "system", "content": system_prompt},
             {"role": "user",   "content": user_prompt}],
            temperature=0.0, max_tokens=2048)

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


def _is_admin_request() -> bool:
    """True iff the request carries the operator's ADMIN_TOKEN in the
    X-Admin-Token header. Header only: a ?token= query string ends up in
    server logs, proxies and browser history."""
    expected = os.getenv("ADMIN_TOKEN", "")
    provided = request.headers.get("X-Admin-Token", "")
    return bool(expected and provided) and hmac.compare_digest(
        provided.encode(), expected.encode())


def _require_admin():
    """Token gate for the operator surface. Fails closed: with ADMIN_TOKEN
    unset the admin API is disabled, unless LEX_ENV=development."""
    if not os.getenv("ADMIN_TOKEN"):
        if envmode.is_dev():
            return None
        return (jsonify({"error": "Admin API disabled: set ADMIN_TOKEN."}), 503)
    if not _is_admin_request():
        return (jsonify({"error": "Unauthorised. Send ADMIN_TOKEN in the X-Admin-Token header."}), 401)
    return None


@app.route("/admin/soc2")
def admin_soc2_page():
    # Data-free shell: a browser navigation can't send X-Admin-Token, so the
    # page asks for the token and its JSON calls (below) are what's gated.
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
    return response


@app.route("/addin/taskpane")
def addin_taskpane():
    """The iframe HTML Word loads inside its task pane."""
    response = make_response(render_template("addin/taskpane.html"))
    # Office frames this page from its own origin, but the page itself is
    # served from here, so its calls back to /convert/* are same-origin.
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


# ─── CORS for /convert/* and /addin/*. The Word task pane is served from this
#     server (BACKEND = window.location.origin), so it needs none. A front-end
#     on another origin must be listed in CORS_ALLOWED_ORIGINS (comma-separated);
#     there is no "*".
def _cors_allowed_origin() -> str | None:
    origin = request.headers.get("Origin", "").rstrip("/")
    allowed = {o.strip().rstrip("/")
               for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    return origin if origin and origin in allowed else None


@app.after_request
def _allow_addin_xhr(response):
    if request.path.startswith(("/convert/", "/addin/")):
        origin = _cors_allowed_origin()
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers.add("Vary", "Origin")
    return response


@app.route("/convert/text", methods=["OPTIONS"])
@app.route("/convert/upload", methods=["OPTIONS"])
def _convert_preflight():
    """Handle CORS preflight for the task pane's XHR calls."""
    return ("", 204)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 2: Run legal triage — the core API endpoint
# ═══════════════════════════════════════════════════════════════════════════════
class _ProviderBusy(Exception):
    """The hosted LLM is rate-limiting us; the caller should retry later."""


def _repair_prompt(prompt: str, draft: str, feedback: list[str]) -> str:
    return (prompt
            + "\n\n=== YOUR PREVIOUS DRAFT ===\n" + draft
            + "\n\n=== REVIEW FINDINGS — fix every one ===\n"
            + "\n".join(f"- {line}" for line in feedback)
            + "\n\nRewrite the COMPLETE analysis with all six sections under the exact "
              "headings given above. Change only what the findings require, and cite "
              "only sections from the retrieved law above.")


def _check_and_repair(draft: str, prompt: str, generate) -> tuple[str, dict]:
    """Verify a draft and, if the verifier finds problems (missing sections,
    sections outside the knowledge base, IPC→BNS pairings that contradict the
    concordance, foreign law), give the model ONE correction pass listing
    exactly those problems. The draft with the lower issue score wins, so a
    worse rewrite can never replace a better first draft."""
    sections = parse_sections(draft)
    check = verifier_module.verify_analysis(sections)
    feedback = verifier_module.repair_feedback(sections, check)
    info = {"attempted": False, "issues_before": len(feedback), "issues_after": len(feedback)}
    if not feedback:
        return draft, info
    info["attempted"] = True
    try:
        fixed = generate(_repair_prompt(prompt, draft, feedback))
    except Exception as e:  # noqa: BLE001 — keep the first draft; it is still verified
        app.logger.warning("self-correction pass failed: %s", e)
        info["error"] = type(e).__name__
        return draft, info
    fixed_sections = parse_sections(fixed or "")
    fixed_check = verifier_module.verify_analysis(fixed_sections)
    if (fixed and verifier_module.issue_score(fixed_sections, fixed_check)
            < verifier_module.issue_score(sections, check)):
        info["issues_after"] = len(verifier_module.repair_feedback(fixed_sections, fixed_check))
        info["accepted"] = True
        return fixed, info
    info["accepted"] = False
    return draft, info


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
    client_ip  = _client_ip()
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

    # Day 23 — pricing / quota check
    _user_email = ((_u or {}).get("email") or "").strip().lower()
    _price_result = pricing_module.check(
        client_ip=client_ip,
        user_email=_user_email,
        api_key_id="",
        api_key_tier="",
    )
    _audit_extra["pricing_tier"] = _price_result["tier"]
    _audit_extra["user_email"]   = _user_email or None
    if not _price_result["allowed"]:
        rid = audit.log_request(
            endpoint="/analyze", client_ip=client_ip, user_agent=user_agent,
            story=client_story, status="rate_limited",
            duration_ms=int((time.monotonic() - t_start) * 1000),
            error="rate_limited", extra=_audit_extra,
        )
        return jsonify({
            "error":      _price_result["reason"],
            "tier":       _price_result["tier"],
            "used":       _price_result["used"],
            "limit":      _price_result["limit"],
            "request_id": rid,
            "upgrade_url": "/nalsa",
        }), 429

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

        def generate(user_message: str) -> str:
            # Day-13: route through llm_provider so Ollama users get local
            # generation. Groq remains the default; ollama users set
            # LLM_PROVIDER=ollama (and EMBEDDINGS_PROVIDER=ollama for retrieval).
            if llm_provider_module.get_provider() == "ollama":
                return llm_provider_module.complete(
                    system_messages=system_messages,
                    user_message=user_message,
                    temperature=0.2,
                    max_tokens=8192,
                    timeout_s=180,
                )["text"]
            # Groq path: brief retries on a rate limit, then give up with a 503.
            # The wait blocks this worker, so it stays short (≤ 6 s total)
            # instead of the minutes a long backoff would hold it.
            messages = [{"role": "system", "content": s} for s in system_messages]
            messages.append({"role": "user", "content": user_message})
            for attempt in range(3):
                try:
                    return llm_provider_module.groq_complete(
                        groq_client, messages, temperature=0.2, max_tokens=8192)
                except Exception as e:
                    err = str(e)
                    if not ("429" in err or "rate_limit" in err.lower()):
                        raise
                    if attempt == 2:
                        raise _ProviderBusy("The AI provider is rate-limiting requests.") from e
                    time.sleep(2 * (attempt + 1))
            return ""

        ai_response = generate(prompt)
        if not ai_response:
            return jsonify({"error": "AI model did not return a response. Try again."}), 500

        # ── Step 2b: check the draft; one targeted correction pass if needed ──
        ai_response, repair = _check_and_repair(ai_response, prompt, generate)
        _audit_extra["self_correction"] = repair

        # ── Step 3: Save text output ──────────────────────────────────────────
        txt_path = save_raw_output(client_story, ai_response)

        # ── Step 4: Parse sections + runtime citation verification ────────────
        # Verification runs BEFORE the PDF so the verdict is stamped into it.
        with open(txt_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        sections = parse_sections(raw_text)
        verification = verifier_module.verify_analysis(sections)

        # ── Step 5: Generate PDF (carries the verification panel) ─────────────
        pdf_path = generate_pdf(txt_path, verification=verification)
        pdf_filename = Path(pdf_path).name
        case_access.record(Path(txt_path).name, pdf_filename,
                           user_id=_audit_extra["user_id"],
                           firm_id=_audit_extra["firm_id"])

        # Escape + bold for web display (the PDF was built from the raw text)
        for key in sections:
            if isinstance(sections[key], str):
                sections[key] = _section_html(sections[key])

        # ── Audit log: success ────────────────────────────────────────────────
        _audit_extra["ungrounded_citations"] = verification["ungrounded"] or None
        _audit_extra["citation_check"] = (
            "passed" if verification["all_verified"] else "attention"
        )
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
            }, firm_id=_audit_extra["firm_id"])
        except Exception:  # noqa: BLE001 — never fail the user's request
            app.logger.exception("webhook emit failed")

        return jsonify({
            "sections":          sections,
            "client_statement":  client_story,
            "pdf_filename":      pdf_filename,
            # Lets whoever ran this analysis (even anonymously) fetch the PDF.
            "download_token":    case_access.make_download_token(pdf_filename),
            "generated":         sections.get("generated", datetime.now().strftime("%d %B %Y, %H:%M:%S")),
            "sources":           sources,
            "verification":      verification,
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
        if isinstance(e, _ProviderBusy):
            return jsonify({
                "error": f"{e} Please try again in a minute.",
                "request_id": request_id,
            }), 503
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
    The signed-in user's past cases (their own + their firm's), newest first.
    Each entry: { "txt_file": "case_analysis_...", "pdf_file": "CaseBrief_...",
                  "date": "04 March 2026, 20:52", "snippet": "Client is a 28..." }
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Sign in to see your saved cases."}), 401

    output_dir = Path("outputs")
    cases = []
    for rec in case_access.files_for(user):
        txt = output_dir / rec["txt_file"]
        try:
            content = txt.read_text(encoding="utf-8")
        except OSError:
            continue

        date_match = re.search(r"Generated:\s*(.+)", content)
        date_str = date_match.group(1).strip() if date_match else txt.stem

        cs_match = re.search(
            r"CLIENT'S STATEMENT:\s*\n(.*?)(?:={10,}|SECTION 1)",
            content, re.DOTALL
        )
        snippet = ""
        if cs_match:
            snippet = " ".join(cs_match.group(1).strip().split())[:100]

        pdf_name = rec["pdf_file"]
        cases.append({
            "txt_file":  txt.name,
            "pdf_file":  pdf_name if pdf_name and (output_dir / pdf_name).exists() else None,
            "date":      date_str,
            "snippet":   snippet or "No preview available",
        })

    return jsonify(cases)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 4: Load a past case (returns parsed sections from a saved .txt file)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/load/<filename>")
def load_case(filename):
    """Load a previously saved case analysis the caller is allowed to read."""
    # Security: only allow reading files from outputs/ with expected name pattern
    if not re.match(r"^case_analysis_\d{8}_\d{6}(?:_[0-9a-f]{8})?\.txt$", filename):
        return jsonify({"error": "Invalid filename."}), 400
    user = _current_user()
    if not user:
        return jsonify({"error": "Sign in to open saved cases."}), 401

    txt_path = Path("outputs") / filename
    # Someone else's file answers exactly like a missing one.
    if not case_access.can_access(user, filename) or not txt_path.exists():
        return jsonify({"error": "Case file not found."}), 404

    try:
        content = txt_path.read_text(encoding="utf-8")
        sections = parse_sections(content)

        for key in sections:
            if isinstance(sections[key], str):
                sections[key] = _section_html(sections[key])

        rec = case_access.lookup(filename) or {}
        pdf_filename = rec.get("pdf_file")

        return jsonify({
            "sections":         sections,
            "client_statement": sections.get("client_statement", ""),
            "pdf_filename":     pdf_filename,
            "generated":        sections.get("generated", ""),
            "error":            None,
        })
    except Exception as e:
        app.logger.exception("load_case failed for %s", filename)
        return jsonify({"error": "Could not read this case file."}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE 5: PDF download
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/download/<filename>")
def download(filename):
    """Serve a PDF file from the outputs/ folder.

    Human-in-the-loop gate (v1.9): the export requires ?approved=1, which the
    UI only sets after the advocate ticks the review-confirmation checkbox.
    Every approved export is audit-logged with the approver's identity.

    Access: the owner (or their firm) via the session cookie, or whoever ran
    the analysis via the signed ?t= token /analyze returned.
    """
    if not re.match(r"^CaseBrief_\d{8}_\d{6}(?:_[0-9a-f]{8})?\.pdf$", filename):
        return "Invalid filename.", 400
    if request.args.get("approved") != "1":
        return jsonify({
            "error": ("This AI-generated draft must be reviewed and approved "
                      "by an advocate before download. Tick the review "
                      "confirmation to enable the export."),
        }), 403
    _u = _current_user()
    if not (case_access.verify_download_token(filename, request.args.get("t", ""))
            or case_access.can_access(_u, filename)):
        if not _u:
            return jsonify({"error": "This download link has expired. Sign in to "
                                     "download your saved cases."}), 401
        return jsonify({"error": "File not found."}), 404
    audit.log_request(
        endpoint="/download",
        client_ip=_client_ip(),
        user_agent=request.headers.get("User-Agent", ""),
        status="ok",
        pdf_filename=filename,
        extra={
            "approved_by": ((_u or {}).get("email") or "anonymous"),
            "user_id":     (_u or {}).get("id") or None,
            "firm_id":     (_u or {}).get("firm_id") or None,
        },
    )
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
    limited = _per_ip_limit("chat", 20)
    if limited:
        return limited
    t_start    = time.monotonic()
    client_ip  = _client_ip()
    user_agent = request.headers.get("User-Agent", "")

    data = request.get_json()
    user_msg = (data or {}).get("message", "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type a question.", "suggest_intake": False})

    # Questions with one right answer in our tables (IPC→BNS, bailable,
    # punishment) are answered from the tables — no model, nothing to invent.
    direct = statute_lookup.answer(user_msg)
    if direct:
        request_id = audit.log_request(
            endpoint="/chat", client_ip=client_ip, user_agent=user_agent,
            story=user_msg, status="ok", response_chars=len(direct["answer"]),
            duration_ms=int((time.monotonic() - t_start) * 1000),
            extra={"answered_by": "statute_lookup"},
        )
        return jsonify({
            "reply": f"{direct['answer']}\n\nSource: {direct['source']}.",
            "suggest_intake": False,
            "sources": [],
            "deterministic": True,
            "request_id": request_id,
        })

    try:
        retrieved_context, sources = _retrieve_for_chat(user_msg, n_results=4)

        reply = llm_provider_module.groq_complete(
            groq_client,
            [{"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
             {"role": "system", "content": retrieved_context},
             {"role": "user",   "content": user_msg}],
            temperature=0.2, max_tokens=400).strip()

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
    except Exception:  # noqa: BLE001 — never fail the user's request
        app.logger.exception("webhook emit failed")
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


def _self_probe(paths: list[tuple[str, int]]) -> list[dict]:
    """Probe a list of internal paths in-process and report status/latency.
    In-process (Flask test client), not over loopback HTTP: no guessing the
    port we're served on, and a single-worker server can't stall waiting on
    itself. Errors are caught — the status page must never crash."""
    results = []
    probe = app.test_client()
    for path, expected in paths:
        start = time.monotonic()
        try:
            resp = probe.get(path)
            results.append({
                "path": path, "status": resp.status_code,
                "ok": resp.status_code == expected,
                "latency_ms": int((time.monotonic() - start) * 1000),
            })
        except Exception as e:  # noqa: BLE001 — report, never crash the page
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
def _webhook_owner():
    """(firm_id, None) for whoever is managing webhooks: "*" for the operator
    (admin token), the caller's own firm for a firm member."""
    if _is_admin_request():
        return "*", None
    u, err = _require_firm_user()
    if err:
        return None, err
    return u["firm_id"], None


@app.route("/webhooks/api/subscriptions", methods=["GET", "POST"])
def webhooks_subscriptions():
    owner, err = _webhook_owner()
    if err:
        return err
    if request.method == "GET":
        return jsonify({"subscriptions": webhooks_module.list_subs(
            None if owner == "*" else owner)})
    data = request.get_json() or {}
    try:
        sub = webhooks_module.add_sub(
            url=data.get("url", ""),
            events=data.get("events", []),
            description=data.get("description", ""),
            firm_id=owner,
        )
        # The signing secret is in this response only — it's never listed again.
        return jsonify({"subscription": sub})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/webhooks/api/subscriptions/<sub_id>", methods=["DELETE"])
def webhooks_remove(sub_id):
    owner, err = _webhook_owner()
    if err:
        return err
    if not re.match(r"^wh_[a-z0-9]+$", sub_id):
        return jsonify({"error": "Invalid subscription id."}), 400
    if not webhooks_module.remove_sub(sub_id, None if owner == "*" else owner):
        return jsonify({"error": "Not found."}), 404
    return jsonify({"ok": True})


@app.route("/webhooks/api/deliveries")
def webhooks_deliveries():
    owner, err = _webhook_owner()
    if err:
        return err
    if owner == "*":
        return jsonify({
            "deliveries":    webhooks_module.recent_deliveries(20),
            "retry_queue":   webhooks_module.retry_queue_stats(),   # Day 22
        })
    return jsonify({"deliveries": webhooks_module.recent_deliveries(20, firm_id=owner)})


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Operator dashboard (Day 19).
# Aggregates KPIs from audit log + leads + matters + monitors into one
# admin-gated dashboard at /dashboard.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/dashboard")
def dashboard_page():
    # Data-free shell; /dashboard/data.json is the gated part.
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

    # Cron jobs last-run status (gap fix)
    try:
        cron_status = cron_module.last_run_status()
    except Exception:
        cron_status = {}

    # Incidents (gap fix)
    try:
        import incidents as _inc
        incident_summary = {
            "overall":   _inc.overall_status(),
            "open_count": len(_inc.list_open()),
            "recent":    _inc.list_recent(5),
        }
    except Exception:
        incident_summary = {"overall": {"label": "Operational", "color": "green",
                                         "open_count": 0}, "open_count": 0, "recent": []}

    # Day 33: billing KPIs
    try:
        billing_summary = billing_module.billing_kpis()
    except Exception:
        billing_summary = {"mrr_inr": 0, "active_total": 0, "by_tier": {},
                            "activations_30d": 0, "churn_30d": 0, "churn_rate_pct": 0,
                            "recent": []}

    return jsonify({
        "generated_at":      now.isoformat(timespec="seconds"),
        "kpis":              kpis,
        "funnel":            funnel,
        "daily_analyses":    dates,
        "top_sources":       top_sources,
        "recent_analyses":   recent_analyses,
        "recent_leads":      recent_leads,
        "storage":           {"backends": storage_backends, "summary": storage_summary},
        "cron":              cron_status,           # gap fix
        "incidents":         incident_summary,     # gap fix
        "billing":           billing_summary,      # Day 33
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Cron / scheduled jobs (Day 24).
# Admin-gated endpoints to trigger scheduled jobs on demand (useful for testing
# and for Render / Fly.io cron-job integrations that use HTTP callbacks).
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/cron/digest_email", methods=["POST"])
def cron_digest_email():
    guard = _require_admin()
    if guard: return guard
    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes")
    result = cron_module.digest_email(dry_run=dry_run)
    return jsonify(result)


@app.route("/cron/nalsa_csv", methods=["POST"])
def cron_nalsa_csv():
    guard = _require_admin()
    if guard: return guard
    result = cron_module.nalsa_csv_export()
    return jsonify(result)


@app.route("/cron/cleanup", methods=["POST"])
def cron_cleanup():
    guard = _require_admin()
    if guard: return guard
    result = cron_module.cleanup_audit()
    return jsonify(result)


@app.route("/cron/sc_scrape", methods=["POST"])
def cron_sc_scrape():
    """Day 27: trigger SC ruling scraper (defaults to stub provider)."""
    guard = _require_admin()
    if guard: return guard
    import sc_scraper
    provider = request.args.get("provider")  # 'livelaw' / 'indiankanoon' / 'stub'
    result = sc_scraper.run_daily_scrape(provider=provider)
    return jsonify(result)


@app.route("/cron/erasure_sweep", methods=["POST"])
def cron_erasure_sweep():
    """Day 28: hard-delete users whose 7-day grace has expired."""
    guard = _require_admin()
    if guard: return guard
    return jsonify(erasure_module.hard_delete_due())


# ─── DPDP §13(2)(d) right-to-erasure endpoints ──────────────────────────────
@app.route("/profile")
def profile_page():
    """Day 30: User profile page (login + tier + usage + delete account)."""
    return render_template("profile.html")


# ─── Day 34: notification preferences API ───────────────────────────────────
@app.route("/profile/prefs", methods=["GET", "POST"])
def profile_prefs():
    """GET = current prefs. POST = update them."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Not logged in."}), 401
    email = user.get("email", "")
    if request.method == "GET":
        return jsonify(prefs_module.get_prefs(email))
    data = request.get_json(silent=True) or {}
    try:
        updated = prefs_module.set_prefs(email, **data)
        return jsonify(updated)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/admin/prefs/stats")
def admin_prefs_stats():
    """Operator view of how users have set their preferences."""
    guard = _require_admin()
    if guard: return guard
    return jsonify(prefs_module.stats())


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — Stripe self-serve billing (Day 31).
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/pricing")
def pricing_page():
    """Public pricing page with the 4 tiers."""
    return render_template("pricing.html",
                           tiers=billing_module.tier_catalogue(),
                           is_live=billing_module.is_live(),
                           mode=billing_module.get_mode())


@app.route("/billing/checkout", methods=["POST"])
def billing_checkout():
    """Create a Stripe Checkout session for the signed-in user."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Sign in to subscribe."}), 401
    if not billing_module.is_live() and not envmode.is_dev():
        # Stub checkout activates a plan without payment: development only.
        return jsonify({"error": "Billing isn't configured on this server yet."}), 503
    data = request.get_json(silent=True) or {}
    tier = (data.get("tier") or request.form.get("tier") or "firm").lower()
    user_id, user_email = user["id"], user.get("email", "")
    try:
        cs = billing_module.create_checkout_session(
            user_id=user_id, user_email=user_email, tier=tier,
            success_url=request.url_root + "billing/success",
            cancel_url=request.url_root + "pricing",
        )
        return jsonify({"checkout_url": cs.checkout_url, "session_id": cs.id, "mode": cs.mode})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/billing/stub-confirm")
def billing_stub_confirm():
    """Stub-mode landing — pretends the signed-in user paid and activates
    them. Development only (LEX_ENV=development, STRIPE_MODE != live): it hands
    out a paid tier for free, so it must never be reachable in production."""
    if billing_module.is_live():
        return ("Stub flow disabled in live mode.", 400)
    if not envmode.is_dev():
        return ("Stub billing is available only with LEX_ENV=development.", 403)
    current = _current_user()
    if not current:
        return ("Sign in first.", 401)
    tier = (request.args.get("tier") or "firm").strip().lower()
    try:
        sub = billing_module.activate_subscription(
            user_id=current["id"], user_email=current.get("email", ""), tier=tier,
            stripe_session_id=request.args.get("session", ""),
        )
    except ValueError as e:
        return (str(e), 400)
    return render_template("billing_success.html", subscription=sub,
                           mode="stub", tier=tier)


@app.route("/billing/success")
def billing_success():
    """Real Stripe success-redirect target."""
    return render_template("billing_success.html", subscription=None,
                           mode=billing_module.get_mode(),
                           tier=request.args.get("tier", "firm"))


@app.route("/billing/stripe-webhook", methods=["POST"])
def billing_stripe_webhook():
    """Stripe sends events here on every payment/cancellation."""
    payload = request.get_data() or b""
    sig = request.headers.get("Stripe-Signature", "")
    if not billing_module.verify_webhook_signature(payload, sig):
        return ("Bad signature.", 400)
    event = billing_module.parse_webhook_event(payload)
    if not event.get("handled"):
        return ("", 204)
    try:
        if event["type"] == "checkout.session.completed":
            billing_module.activate_subscription(
                user_id=event["user_id"],
                user_email=event["user_email"],
                tier=event["tier"] or "firm",
                stripe_session_id=event["stripe_session_id"],
            )
        elif event["type"] == "customer.subscription.deleted":
            billing_module.cancel_subscription(
                user_id=event["user_id"], reason="stripe_subscription_deleted"
            )
        elif event["type"] == "invoice.payment_failed":
            billing_module.record_payment_failure(
                user_id=event["user_id"], reason="stripe_invoice_payment_failed"
            )
    except Exception as exc:
        return (f"Webhook handler error: {exc}", 500)
    return ("", 204)


@app.route("/billing/cancel", methods=["POST"])
def billing_cancel():
    """User-facing: cancel my active subscription."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Not logged in."}), 401
    data = request.get_json(silent=True) or {}
    cancelled = billing_module.cancel_subscription(
        user_id=user["id"], reason=data.get("reason", "user_requested"),
    )
    return jsonify({"ok": bool(cancelled), "cancelled": cancelled})


@app.route("/billing/api/subscriptions")
def billing_list_subscriptions():
    """Admin-only: list every subscription on the system."""
    guard = _require_admin()
    if guard: return guard
    return jsonify({"subscriptions": billing_module.all_subscriptions()})


@app.route("/profile/delete", methods=["POST"])
def profile_delete():
    """User-facing: request account deletion (7-day grace period)."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Not logged in."}), 401
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    try:
        req = erasure_module.request_deletion(
            user_id=user["id"],
            user_email=user.get("email", ""),
            reason=reason,
        )
        # Confirmation email. mailer.send never raises; a failure is logged,
        # not fatal — the erasure is already scheduled.
        sent = mailer_module.send(
            to=user["email"],
            subject="Lex-Indic — account deletion scheduled",
            text=(
                f"Your Lex-Indic account is scheduled for permanent deletion "
                f"on {req['scheduled_for']} ({erasure_module.GRACE_DAYS}-day grace period).\n\n"
                f"You can cancel within the grace period via /profile/delete/cancel.\n\n"
                f"After deletion, the salted hash that links your past audit-log "
                f"entries to your account will be rotated, making historical entries "
                f"un-correlatable. Matters (case files) are soft-preserved per Bar "
                f"Council records-retention rules but become unlinked from your "
                f"identity.\n\nIf this was a mistake, cancel immediately."
            ),
        )
        if not sent.ok:
            app.logger.warning("erasure confirmation email to %s failed: %s",
                               user["id"], sent.error)
        return jsonify(req)
    except Exception as exc:
        return jsonify({"error": f"Could not schedule erasure: {str(exc)[:200]}"}), 500


@app.route("/profile/delete/cancel", methods=["POST"])
def profile_delete_cancel():
    """User-facing: cancel a pending deletion within the grace period."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Not logged in."}), 401
    ok = erasure_module.cancel_deletion(user_id=user["id"])
    return jsonify({"ok": ok, "cancelled": ok})


@app.route("/profile/export", methods=["GET"])
def profile_export():
    """DPDP §11(1) right-to-access — download all your data as JSON."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Not logged in."}), 401
    data = erasure_module.export_user_data(
        user_id=user["id"],
        user_email=user.get("email", ""),
    )
    resp = make_response(json.dumps(data, indent=2, ensure_ascii=False))
    resp.headers["Content-Type"] = "application/json"
    resp.headers["Content-Disposition"] = 'attachment; filename="my-lex-indic-data.json"'
    return resp


@app.route("/admin/erasure/pending")
def admin_erasure_pending():
    """Operator view of all pending erasure requests in their grace period."""
    guard = _require_admin()
    if guard: return guard
    return jsonify({
        "pending": erasure_module.pending_requests(),
        "grace_days": erasure_module.GRACE_DAYS,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — SMS / WhatsApp (Day 25).
# Admin-gated test endpoint + provider status check.
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/sms/test", methods=["POST"])
def sms_test():
    """Admin-only: send a test SMS/WhatsApp to verify provider config."""
    guard = _require_admin()
    if guard: return guard
    data    = request.get_json() or {}
    phone   = (data.get("phone") or "").strip()
    channel = (data.get("channel") or "sms").lower()
    if not phone:
        return jsonify({"error": "phone is required"}), 400
    result = sms_module.send(
        to=phone, template="magic_link", channel=channel,
        variables={"code": "123456", "ttl": "10"},
    )
    return jsonify({
        "ok":         result.ok,
        "provider":   result.provider,
        "message_id": result.message_id,
        "error":      result.error,
    }), 200 if result.ok else 502


@app.route("/sms/status")
def sms_status():
    """Returns the configured SMS provider and which env vars are set."""
    import os as _os
    provider = _os.getenv("SMS_PROVIDER", "stdout")
    config = {
        "provider": provider,
        "msg91_configured":   bool(_os.getenv("MSG91_AUTH_KEY")),
        "twilio_configured":  bool(_os.getenv("TWILIO_ACCOUNT_SID") and _os.getenv("TWILIO_AUTH_TOKEN")),
        "templates": list(sms_module.TEMPLATES.keys()),
    }
    return jsonify(config)


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

    # Day 23 — pricing check for API key
    _price = pricing_module.check(
        client_ip=_client_ip(),
        api_key_id=key["key_id"],
        api_key_tier=key.get("tier", "firm"),
    )
    if not _price["allowed"]:
        return jsonify({
            "error": _price["reason"],
            "tier": _price["tier"],
            "used": _price["used"],
            "limit": _price["limit"],
        }), 429

    # Reuse the existing retrieval + Groq pipeline directly
    try:
        retrieved_context, sources = retrieve_relevant_sections_structured(
            rag_collection, story, n_results=8,
        )
        prompt = build_legal_prompt(story, retrieved_context)

        def generate(user_message: str) -> str:
            return llm_provider_module.groq_complete(
                groq_client,
                [{"role": "system", "content": LEXI_SYSTEM_PROMPT},
                 {"role": "user", "content": user_message}],
                temperature=0.2, max_tokens=8192)

        ai_response, repair = _check_and_repair(generate(prompt), prompt, generate)
        txt_path = save_raw_output(story, ai_response)
        with open(txt_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        sections = parse_sections(raw_text)
        verification = verifier_module.verify_analysis(sections)
        pdf_path = generate_pdf(txt_path, verification=verification)
        for k in sections:
            if isinstance(sections[k], str):
                sections[k] = _section_html(sections[k])
        case_access.record(Path(txt_path).name, Path(pdf_path).name,
                           user_id=key["user_id"], firm_id=key.get("firm_id") or None)
        request_id = audit.log_request(
            endpoint="/api/v1/analyze",
            client_ip=_client_ip(),
            user_agent=f"api-key:{key['key_id']}",
            story=story, sources=sources, status="ok",
            duration_ms=0, response_chars=len(ai_response or ""),
            pdf_filename=Path(pdf_path).name,
            extra={"user_id": key["user_id"], "firm_id": key.get("firm_id") or None,
                   "api_key_id": key["key_id"], "self_correction": repair,
                   "citation_check": "passed" if verification["all_verified"] else "attention"},
        )
        return jsonify({
            "sections": sections, "client_statement": story,
            "pdf_filename": Path(pdf_path).name, "sources": sources,
            "download_token": case_access.make_download_token(Path(pdf_path).name),
            "verification": verification,
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
    owner = key.get("firm_id") or key.get("user_id") or ""
    return jsonify(monitors_module.run_digest(since=since, owner=owner))


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
    except Exception:  # noqa: BLE001 — never fail the user's request
        app.logger.exception("webhook emit failed")
    return jsonify({"lead": {"id": lead.id, "full_name": lead.full_name}})


# ─── Newly-exposed endpoints (gap-fix sprint) ───────────────────────────────
@app.route("/api/v1/tabular/review", methods=["POST"])
def api_tabular_review():
    """Run tabular contract review on a chunk of text or uploaded contract."""
    key, err = _require_api_key()
    if err: return err
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    contract_type = (data.get("contract_type") or "general").strip().lower()
    if not text:
        return jsonify({"error": "text is required (at least 100 chars)"}), 400
    if len(text) < 100:
        return jsonify({"error": "text must be at least 100 characters"}), 400
    try:
        result = tabular_module.review(text=text, contract_type=contract_type)
        return jsonify({"clauses": result})
    except AttributeError:
        # tabular_module may use a different function name; degrade gracefully
        return jsonify({"error": "tabular review temporarily unavailable"}), 503
    except Exception as exc:
        return jsonify({"error": f"tabular review failed: {str(exc)[:200]}"}), 500


@app.route("/api/v1/matters", methods=["GET"])
def api_matters_list():
    """The key's firm's matters. A key with no firm sees none — matters are
    tenant data, never listed across firms."""
    key, err = _require_api_key()
    if err: return err
    firm_id = key.get("firm_id") or ""
    matters = matters_module.list_matters(firm_id=firm_id) if firm_id else []
    return jsonify({"matters": matters, "count": len(matters)})


@app.route("/api/v1/me/usage", methods=["GET"])
def api_me_usage():
    """Day 26: Return the current API key's tier, daily limit, used today, percent.
    Used by the user profile / billing page (Day 30 prep)."""
    key, err = _require_api_key()
    if err: return err
    tier = key.get("tier", "firm")
    # Re-run pricing.check() to get used + limit without actually consuming
    res = pricing_module.check(
        client_ip=_client_ip(),
        api_key_id=key["key_id"],
        api_key_tier=tier,
    )
    used  = res.get("used", 0)
    limit = res.get("limit")
    pct   = (used / limit * 100) if limit and limit > 0 else 0
    return jsonify({
        "key_id":          key["key_id"],
        "tier":            tier,
        "tier_label":      pricing_module.tier_label(tier),
        "used_today":      used,
        "daily_limit":     limit,
        "percent_used":    round(pct, 1),
        "allowed":         res.get("allowed", True),
        "rate_per_min":    key.get("rate_per_min", 60),
        "upgrade_url":     "/nalsa" if tier == "free" else None,
    })


@app.route("/api/v1/nalsa/check", methods=["GET"])
def api_nalsa_check():
    """Check if an email is in the NALSA registry (used by pricing logic)."""
    key, err = _require_api_key()
    if err: return err
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email query parameter required"}), 400
    is_reg = nalsa_module.is_registered(email)
    return jsonify({"email": email, "is_registered": is_reg,
                    "tier": "nalsa" if is_reg else "free"})


@app.route("/api/v1/status")
def api_status():
    """Public status feed — incidents + overall state."""
    import incidents as incidents_module
    return jsonify({
        "overall":  incidents_module.overall_status(),
        "open":     incidents_module.list_open(),
        "recent":   incidents_module.list_recent(10),
    })


# ─── Admin endpoints to manage API keys ────────────────────────────────────
_SELF_SERVICE_RATE_PER_MIN = 60


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
        # Self-service keys get the standard rate; only the operator sets others.
        rate = max(1, min(int(data.get("rate_per_min", 60)), _SELF_SERVICE_RATE_PER_MIN))
        key = api_keys_module.issue_key(
            user_id=user["id"],
            firm_id=user.get("firm_id") or "",
            label=data.get("label", ""),
            rate_per_min=rate,
        )
        return jsonify({"key": key})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/admin/api-keys/<key_id>", methods=["DELETE"])
def admin_api_key_revoke(key_id):
    """A user revokes their own keys; the operator (admin token) any key."""
    owner = None
    if not _is_admin_request():
        user = _current_user()
        if not user:
            guard = _require_admin()
            if guard: return guard
        else:
            owner = user["id"]
    if not re.match(r"^lex_live_[a-f0-9]+$", key_id):
        return jsonify({"error": "invalid key id"}), 400
    # ?immediate=1 for a leaked key; otherwise a 60-min grace for rotation.
    grace = 0 if request.args.get("immediate") == "1" else 60
    if not api_keys_module.revoke_key(key_id, grace_period_min=grace, user_id=owner):
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
        "--host", default="127.0.0.1",
        help="Bind host (default 127.0.0.1 — this machine only; pass 0.0.0.0 "
             "deliberately to expose the dev server to your network).",
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
