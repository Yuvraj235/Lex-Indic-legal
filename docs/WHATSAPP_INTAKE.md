# WhatsApp intake → draft → file

Automated client intake over WhatsApp: a client messages a number, a bot asks
what / when / where / who one question at a time, and once it has enough it
drafts via the analysis pipeline and files the draft for the advocate to review.

## Pieces (in this repo)
- `intake.py` — the multi-turn state machine + inbound-payload parsing (provider
  agnostic) + a per-sender session store under `outputs/intake/`.
- `POST /wa/inbound` (in `app.py`) — the webhook. Understands **Twilio** (form:
  `From` / `Body`) and **MSG91 / generic** (JSON) inbound payloads. Replies with
  TwiML for Twilio, JSON otherwise. On completion it drafts (reusing the warm RAG
  + Groq path) and files `intake_story.txt` + `draft.txt` under
  `outputs/wa_intake/<sender>_<ts>/`.

## Wiring a provider

### Option A — Twilio WhatsApp (fastest to test)
1. In the Twilio console, set the WhatsApp sandbox/number's **"When a message
   comes in"** webhook to `https://YOUR_HOST/wa/inbound` (HTTP POST).
2. Twilio posts `From` + `Body`; the route returns TwiML and Twilio relays the
   reply. No extra code.

### Option B — MSG91 (India, DLT)
1. Point the MSG91 inbound webhook at `https://YOUR_HOST/wa/inbound`.
2. MSG91 posts JSON; the route returns `{"reply": "..."}`. Forward that text back
   to the user via MSG91's outbound API (a 2-line n8n step, or `sms.py`).
   Remember MSG91 requires **DLT-approved templates** for outbound (TRAI).

### Option C — n8n (no-code orchestration)
WhatsApp Trigger → HTTP Request `POST /wa/inbound` (pass `mobile` + `message`) →
send the returned `reply` back via the WhatsApp node. For drafting only, n8n can
instead call the existing `POST /api/v1/analyze` with the composed story.

## Notes
- Linking the filed draft to a specific firm **matter** (vs the per-sender folder)
  is a deployment config step — map a sender to a `firm_id`/`matter_id`.
- Cannot be fully verified without a live WhatsApp number + (for MSG91) DLT
  approval — that's an ops step, not code. The intake logic itself is unit-tested.
