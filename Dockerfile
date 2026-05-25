# ════════════════════════════════════════════════════════════════════════════
#  Lex-Indic — multi-stage Dockerfile
#  Build: docker build -t lex-indic:latest .
#  Run:   docker run -p 8080:8080 --env-file .env lex-indic:latest
# ════════════════════════════════════════════════════════════════════════════

# ── Stage 1: build dependencies into a wheel cache ──────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

# System deps needed for some Python packages (pdfplumber needs poppler;
# python-docx is pure Python; chromadb pulls onnxruntime which needs gcc).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Stage 2: runtime image ──────────────────────────────────────────────────
FROM python:3.13-slim

# Runtime system deps only (no compilers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        libpangoft2-1.0-0 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

WORKDIR /app

# Copy only what the runtime needs (skip tests, docs, certs).
# .dockerignore handles the bulk; this is a belt-and-braces second pass.
COPY app.py main.py audit.py auth.py compliance.py ecourts.py i18n.py \
     ipc_bns_converter.py leads.py llm_provider.py mailer.py matters.py \
     monitors.py nalsa.py openapi_spec.py pdf_generator.py tabular.py \
     webhooks.py api_keys.py db.py pricing.py cron.py sms.py incidents.py ./
COPY data/ ./data/
COPY templates/ ./templates/
COPY static/ ./static/
COPY tools/ ./tools/

# Create the outputs/ tree as a volume mount-point.  Persisted state
# (cases, audit logs, sqlite DB, leads, etc.) lives here.
RUN mkdir -p outputs/audit outputs/converted outputs/monitors outputs/nalsa \
             outputs/matters outputs/leads outputs/webhooks outputs/mail \
             outputs/soc2_evidence
VOLUME ["/app/outputs"]

# Non-root user (UID 10001 — high enough to avoid host UID collisions).
RUN useradd --create-home --uid 10001 lex && \
    chown -R lex:lex /app
USER lex

EXPOSE 8080

# Liveness probe — hits /api/v1/health (no auth required)
HEALTHCHECK --interval=30s --timeout=4s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/api/v1/health || exit 1

# Use gunicorn in production (not Flask dev server).  Single worker is
# fine because we keep ChromaDB in-process; scale via more containers.
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app

CMD ["python", "-m", "gunicorn", "-w", "1", "-b", "0.0.0.0:8080", \
     "--timeout", "180", "--access-logfile", "-", "app:app"]
