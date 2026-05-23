"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — OpenAPI 3.0 spec for /api/v1/*                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Single source of truth for the JSON API contract.  Serves three purposes:
  1. Machine-readable spec at /api/v1/openapi.json — Postman / Insomnia
     can import directly; codegen tools (openapi-generator) can produce
     SDKs in any language from this.
  2. Human-readable Swagger UI at /api/v1/docs.
  3. Documentation that travels with the code — any new /api/v1/* route
     must add itself here or it doesn't ship.

Why hand-written instead of auto-generated: Flask doesn't ship with OpenAPI
introspection, and the alternative (flasgger, apispec, etc.) brings 3
dependencies and a sprinkle of decorators on every route.  Hand-writing
keeps the spec honest — when a route changes, you update one dict here,
not chase decorators across 1500 lines of app.py.
"""

from __future__ import annotations


def spec() -> dict:
    """Return the OpenAPI 3.0 spec as a JSON-serialisable dict."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title":       "Lex-Indic API",
            "version":     "1.0.0",
            "description": (
                "Lex-Indic v1 API.  Authenticate every request with the "
                "`X-Api-Key: lex_live_<id>:<secret>` header.  Get a key "
                "from /admin/api-keys after signing in at /login.  "
                "Default rate limit: 60 req/min/key.  All responses are "
                "JSON; all timestamps are UTC ISO-8601."
            ),
            "contact": {"name": "Yuvraj Pratap Singh",
                        "url":  "https://github.com/Yuvraj235/Lex-Indic-legal"},
            "license": {"name": "Educational"},
        },
        "servers": [
            {"url": "/api/v1", "description": "this instance"},
        ],
        "security": [{"ApiKeyAuth": []}],

        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in":   "header",
                    "name": "X-Api-Key",
                    "description":
                        "Format: `lex_live_<32-hex>:<48-hex>`.  Issued via "
                        "the admin UI at /admin/api-keys.",
                },
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "required": ["error"],
                    "properties": {
                        "error":      {"type": "string"},
                        "request_id": {"type": "string"},
                    },
                },
                "Source": {
                    "type": "object",
                    "description": "A retrieved KB entry — the model is "
                                   "instructed to cite ONLY from these.",
                    "properties": {
                        "rank":       {"type": "integer"},
                        "id":         {"type": "string", "example": "bns_304"},
                        "kind":       {"type": "string",
                                       "enum": ["bns_section", "bnss_section",
                                                "bsa_section", "case_summary",
                                                "circular", "ipc_bns_mapping"]},
                        "label":      {"type": "string"},
                        "section":    {"type": "string", "nullable": True},
                        "title":      {"type": "string", "nullable": True},
                        "punishment": {"type": "string", "nullable": True},
                        "bailable":   {"type": "string", "nullable": True},
                        "relevance":  {"type": "number", "format": "float"},
                        "raw_text":   {"type": "string"},
                        "deep_link":  {"type": "object", "nullable": True},
                    },
                },
                "AnalyzeRequest": {
                    "type": "object",
                    "required": ["client_story"],
                    "properties": {
                        "client_story":   {"type": "string", "minLength": 30,
                                           "description": "Plain-text client narrative; 30+ chars."},
                        "additional_info":{"type": "string"},
                        "language":       {"type": "string", "enum": ["en", "hi"], "default": "en"},
                        "matter_id":      {"type": "string", "nullable": True,
                                           "description": "Optional matter ID to file the analysis under."},
                    },
                },
                "AnalyzeResponse": {
                    "type": "object",
                    "properties": {
                        "sections":          {"type": "object"},
                        "client_statement":  {"type": "string"},
                        "pdf_filename":      {"type": "string"},
                        "generated":         {"type": "string"},
                        "sources":           {"type": "array", "items": {"$ref": "#/components/schemas/Source"}},
                        "language":          {"type": "string"},
                        "request_id":        {"type": "string"},
                    },
                },
                "ConvertTextRequest": {
                    "type": "object", "required": ["text"],
                    "properties": {"text": {"type": "string", "maxLength": 200000}},
                },
                "ConvertTextResponse": {
                    "type": "object",
                    "properties": {
                        "annotated": {"type": "string"},
                        "summary":   {"type": "object"},
                    },
                },
                "CnrStatus": {
                    "type": "object",
                    "properties": {
                        "cnr":               {"type": "string"},
                        "case_type":         {"type": "string"},
                        "case_number":       {"type": "string"},
                        "filing_date":       {"type": "string"},
                        "next_hearing_date": {"type": "string", "nullable": True},
                        "status":            {"type": "string"},
                        "court":             {"type": "string"},
                        "judge":             {"type": "string"},
                        "petitioner":        {"type": "string"},
                        "respondent":        {"type": "string"},
                        "sections":          {"type": "array", "items": {"type": "string"}},
                        "hearings":          {"type": "array", "items": {"type": "object"}},
                    },
                },
                "MonitorDigest": {
                    "type": "object",
                    "properties": {
                        "date":          {"type": "string"},
                        "totals":        {"type": "object"},
                        "matters":       {"type": "array", "items": {"type": "object"}},
                    },
                },
                "Lead": {
                    "type": "object", "required": ["full_name", "email"],
                    "properties": {
                        "full_name":   {"type": "string"},
                        "email":       {"type": "string", "format": "email"},
                        "firm_or_org": {"type": "string"},
                        "role":        {"type": "string"},
                        "interests":   {"type": "array", "items": {"type": "string"}},
                        "how_heard":   {"type": "string"},
                    },
                },
            },
            "responses": {
                "Unauthorized":  {"description": "Missing or invalid X-Api-Key header.",
                                  "content": {"application/json":
                                              {"schema": {"$ref": "#/components/schemas/Error"}}}},
                "RateLimited":   {"description": "Per-key rate limit exceeded.",
                                  "content": {"application/json":
                                              {"schema": {"$ref": "#/components/schemas/Error"}}}},
                "BadRequest":    {"description": "Validation failed.",
                                  "content": {"application/json":
                                              {"schema": {"$ref": "#/components/schemas/Error"}}}},
            },
        },

        "paths": {
            "/analyze": {
                "post": {
                    "summary": "Run a full legal analysis",
                    "description":
                        "Returns the six-section legal brief plus the citation-provenance "
                        "source list.  The model is instructed to cite ONLY from the "
                        "returned sources; out-of-source citations indicate model drift.",
                    "requestBody": {"required": True, "content": {"application/json":
                        {"schema": {"$ref": "#/components/schemas/AnalyzeRequest"}}}},
                    "responses": {
                        "200": {"description": "OK", "content": {"application/json":
                                {"schema": {"$ref": "#/components/schemas/AnalyzeResponse"}}}},
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "429": {"$ref": "#/components/responses/RateLimited"},
                    },
                },
            },
            "/convert/text": {
                "post": {
                    "summary": "Convert IPC references in plain text to BNS",
                    "requestBody": {"required": True, "content": {"application/json":
                        {"schema": {"$ref": "#/components/schemas/ConvertTextRequest"}}}},
                    "responses": {
                        "200": {"description": "OK", "content": {"application/json":
                                {"schema": {"$ref": "#/components/schemas/ConvertTextResponse"}}}},
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
            },
            "/ecourts/lookup/{cnr}": {
                "get": {
                    "summary": "Look up Indian case-status by CNR",
                    "parameters": [{
                        "name": "cnr", "in": "path", "required": True,
                        "schema": {"type": "string",
                                   "pattern": "^[A-Z]{4}\\d{14}$",
                                   "example": "MHCC010012342024"},
                    }],
                    "responses": {
                        "200": {"description": "OK", "content": {"application/json":
                                {"schema": {"$ref": "#/components/schemas/CnrStatus"}}}},
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "404": {"description": "CNR not found"},
                    },
                },
            },
            "/monitors/digest": {
                "get": {
                    "summary": "Today's SC precedent digest for the calling user's matters",
                    "parameters": [{
                        "name": "since", "in": "query", "required": False,
                        "schema": {"type": "string", "format": "date"},
                        "description": "Only include rulings dated on/after this YYYY-MM-DD.",
                    }],
                    "responses": {
                        "200": {"description": "OK", "content": {"application/json":
                                {"schema": {"$ref": "#/components/schemas/MonitorDigest"}}}},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
            },
            "/sections": {
                "get": {
                    "summary": "List all BNS / BNSS / BSA sections in the KB",
                    "parameters": [{
                        "name": "kind", "in": "query",
                        "schema": {"type": "string", "enum": ["bns", "bnss", "bsa", "all"], "default": "all"},
                    }],
                    "responses": {
                        "200": {"description": "Array of section metadata"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
            },
            "/leads": {
                "post": {
                    "summary": "Submit a lead from an external form",
                    "requestBody": {"required": True, "content": {"application/json":
                        {"schema": {"$ref": "#/components/schemas/Lead"}}}},
                    "responses": {
                        "200": {"description": "Lead captured"},
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
            },
            "/health": {
                "get": {
                    "summary": "Liveness probe — does NOT require auth",
                    "security": [],
                    "responses": {
                        "200": {"description": "Service is up",
                                "content": {"application/json": {"schema":
                                    {"type": "object", "properties": {
                                        "ok":        {"type": "boolean"},
                                        "version":   {"type": "string"},
                                        "uptime_s":  {"type": "integer"},
                                    }}}}},
                    },
                },
            },
        },
    }
