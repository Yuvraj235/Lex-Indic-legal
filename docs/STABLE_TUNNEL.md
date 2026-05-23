# Stable demo URL via a named Cloudflare tunnel

The quick `cloudflared tunnel --url http://localhost:8080` URL is great for
the first 30 minutes — but it dies the moment cloudflared restarts (laptop
sleep, network change, etc.) and you have to email a new URL to every
prospect.

This doc walks through the **named-tunnel** setup that gives you a
stable URL like `https://demo.lexindic.in` (or your own domain) that
survives reboots and is the same every time you start it.

Time: ~25 minutes the first time, 0 minutes after.

---

## Prerequisites

- A Cloudflare account (free tier is fine)
- A domain on Cloudflare (cheapest path: register `lexindic.in` directly
  via Cloudflare Registrar — wholesale pricing, ~$8/year)
- The `cloudflared` binary (`brew install cloudflared`)

---

## One-time setup

### 1. Authenticate cloudflared with your Cloudflare account

```bash
cloudflared tunnel login
```

A browser opens. Pick your zone (the domain you'll use). cloudflared saves
a cert at `~/.cloudflared/cert.pem`.

### 2. Create a named tunnel

```bash
cloudflared tunnel create lex-indic-demo
```

You'll see:

```
Tunnel credentials written to /Users/you/.cloudflared/UUID.json.
Created tunnel lex-indic-demo with id UUID.
```

Note the UUID — you'll need it.

### 3. Map a DNS hostname to the tunnel

```bash
cloudflared tunnel route dns lex-indic-demo demo.lexindic.in
```

This creates a CNAME from `demo.lexindic.in` → `UUID.cfargotunnel.com`
in your Cloudflare DNS.

### 4. Write a config file

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: UUID                            # the UUID from step 2
credentials-file: /Users/you/.cloudflared/UUID.json

ingress:
  - hostname: demo.lexindic.in
    service: http://localhost:8080
  - service: http_status:404            # catch-all
```

### 5. Test it

```bash
cloudflared tunnel run lex-indic-demo
```

In another shell:

```bash
curl https://demo.lexindic.in/status.json
```

Should return 200 with the live status payload.

---

## Daily use

Once the setup above is done, starting the demo for a prospect is one
command in a terminal you leave open:

```bash
# Terminal 1 — Flask app
python3 app.py

# Terminal 2 — Cloudflare tunnel
cloudflared tunnel run lex-indic-demo
```

Send `https://demo.lexindic.in` to anyone. URL never changes.

---

## Run as a launchd service (mac) — survives reboots

```bash
sudo cloudflared service install
sudo launchctl enable system/com.cloudflare.cloudflared
sudo launchctl start system/com.cloudflare.cloudflared
```

The tunnel now starts automatically at boot. To stop:

```bash
sudo launchctl stop system/com.cloudflare.cloudflared
```

Logs: `tail -f /var/log/cloudflared.log`

---

## Security checklist before sharing the stable URL

1. **Set `ADMIN_TOKEN`** in `.env` (a 32-char hex string). This
   gates `/admin/*` and `/try/api/leads`.

2. **Set `AUDIT_HASH_SALT`** to a 32+ char random string. This
   makes the audit log's PII hashes deployment-unique.

3. **Set `LLM_PROVIDER=ollama`** if you don't want client stories
   transiting Groq's US servers during this demo.

4. **Review `outputs/leads/leads.json`** weekly — it's where
   `/try` submissions land.  Pipe via webhook to your CRM instead
   of relying on filesystem checking.

5. **Subscribe a webhook** to `lead.captured` so you're notified
   in Slack / WhatsApp / email the moment a prospect signs up.

```bash
curl -X POST https://demo.lexindic.in/webhooks/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://hooks.slack.com/services/T.../B.../...",
    "events": ["lead.captured", "analysis.completed"],
    "description": "Sales Slack channel"
  }'
```

---

## Troubleshooting

**`cloudflared tunnel run` exits with "404 origin"**
→ Flask isn't listening on `:8080`. Start `python3 app.py` first.

**HTTPS cert warning in the browser**
→ Won't happen with named tunnels — Cloudflare gives you a real
Let's-Encrypt cert automatically. Only the `trycloudflare.com`
ephemeral URLs use a self-signed cert.

**Tunnel reconnects every few minutes**
→ Cloudflare rate-limits free-tier ephemeral tunnels but **NOT**
named tunnels. If you're still on the ephemeral path, you've
skipped step 2 above.

**Latency is high for Indian prospects**
→ cloudflared picks the nearest edge automatically (`del05` from
Delhi-area users in our testing — ~30ms). Force a specific edge
with `--edge-region in` if needed.

---

## When you actually have customers

The named-tunnel path is for demos and pilots. Once a firm wants
their own deployment, the right answer is:

| Customer type | Deploy on |
|---|---|
| Solo lawyer, demo only | Stays on this tunnel |
| Tier-2/3 firm (2-10 seats) | A small DigitalOcean droplet in Mumbai (~₹500/mo) |
| NBFC / firm with DPDP-strict needs | Their own VPC, on-prem `LLM_PROVIDER=ollama` |
| NALSA SLSA pilot | An SLSA-managed server, free tier hosted by Lex-Indic |

The repo is small enough (~5MB excluding the embedding cache) to fit
on the cheapest tier of any of these providers.
