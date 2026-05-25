# Deploy Lex-Indic to Hugging Face Spaces (Free, 24/7)

This is the **fastest, free way to get a shareable Lex-Indic URL** that runs
24/7 and auto-redeploys every time you `git push`.

## Why Hugging Face Spaces

| Feature | HF Spaces (free) |
|---|---|
| Cost | Free forever |
| Custom URL | `https://huggingface.co/spaces/<you>/lex-indic` |
| HTTPS | Auto-provisioned |
| Auto-deploy on git push | Yes (via the GitHub Action in `.github/workflows/`) |
| Always-on | Yes, but free Spaces sleep after 48h idle (wake in ~30 sec) |
| Memory | 16 GB RAM, 2 CPU cores |
| Docker support | Native — uses our existing Dockerfile |

## One-time setup (15 minutes)

### Step 1 — Create your Hugging Face account
1. Go to https://huggingface.co/join
2. Sign up (free, just email + password)
3. Pick a username — this becomes part of your Space URL.
   Suggestion: use the same as your GitHub: `yuvraj235`

### Step 2 — Create the Space
1. Go to https://huggingface.co/new-space
2. Fill the form:
   - **Owner:** your username
   - **Space name:** `lex-indic`
   - **License:** Other
   - **Select the SDK:** **Docker** → **Blank**
   - **Hardware:** CPU basic (free)
   - **Visibility:** Public (anyone with the link can try it)
3. Click **Create Space**

Your Space URL is now `https://huggingface.co/spaces/<your-username>/lex-indic`.

### Step 3 — Generate a write-access token
1. Go to https://huggingface.co/settings/tokens
2. Click **New token**
   - Name: `github-actions-deploy`
   - Type: **Write**
3. Click **Generate**
4. **Copy the token** (starts with `hf_...`) — you'll only see it once.

### Step 4 — Add the token to GitHub
1. Go to https://github.com/Yuvraj235/Lex-Indic-legal/settings/secrets/actions
2. Click **New repository secret**
3. Fill:
   - **Name:** `HF_TOKEN`
   - **Secret:** paste the `hf_...` token from Step 3
4. Click **Add secret**

### Step 5 — Set the Lex-Indic secrets in the HF Space
The Space needs `GEMINI_API_KEY` to actually generate analyses.

1. Go to your Space settings:
   `https://huggingface.co/spaces/<your-username>/lex-indic/settings`
2. Scroll to **Variables and secrets** → **New secret**
3. Add these secrets:

| Name | Value | Required? |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini key | **Yes** (analyses won't work without it) |
| `AUDIT_HASH_SALT` | Any random string (e.g. `lex-indic-prod-salt-7382`) | **Yes** for audit privacy |
| `ADMIN_TOKEN` | Any random string (used for /dashboard) | Recommended |
| `DISABLE_RATE_LIMITS` | `1` | Optional — set for the demo, remove for production |
| `MAIL_PROVIDER` | `stdout` for demo | Optional |
| `SMS_PROVIDER` | `stdout` for demo | Optional |

### Step 6 — Verify the username in the workflow file
Open `.github/workflows/sync-to-huggingface.yml` and check:
```yaml
HF_USERNAME: yuvraj235          # ← change to your HF username if different
HF_SPACE_NAME: lex-indic        # ← change to your Space name if different
```

If your HF username is different, update and commit.

### Step 7 — Push to trigger first deploy
```bash
git push origin main
```

Within 30 seconds, the GitHub Action fires and pushes your repo to the HF Space.
HF then builds the Docker image (~5-7 minutes on first deploy).

**Watch the build:**
- GitHub side: `https://github.com/Yuvraj235/Lex-Indic-legal/actions`
- HF side: `https://huggingface.co/spaces/<you>/lex-indic` → **Logs** tab

When it finishes, the Space shows your Lex-Indic homepage.

## After setup — what auto-runs from now on

Every `git push origin main` triggers:
1. **GitHub Actions** runs the sync workflow → pushes to HF
2. **HF Spaces** rebuilds the Docker image → restarts the Space
3. Total time from push to live: **~2-5 minutes**

You can also trigger a manual deploy from the Actions tab on GitHub
(`workflow_dispatch`) without needing to push anything.

## The link to share

After Step 7 completes, share this URL with Hrishita or anyone:

```
https://huggingface.co/spaces/<your-username>/lex-indic
```

This URL:
- ✅ Works 24/7 (sleeps after 48h idle, wakes in ~30 sec on first visit)
- ✅ HTTPS-secured automatically
- ✅ Mobile-friendly
- ✅ No login required to view (Public Space)
- ✅ Updates automatically every time you commit to GitHub

## Troubleshooting

**"GitHub Action failed — HF_TOKEN secret not set"**
→ Step 4 wasn't completed. Add the secret in GitHub Settings.

**"Space build failed — pip install error"**
→ Check the HF Space Logs tab. Usually a dependency conflict.
Run `pip install -r requirements.txt` locally to reproduce.

**"Space loads but /analyze returns 'API key missing'"**
→ Step 5 wasn't completed. Add `GEMINI_API_KEY` as a Space secret.

**"Space is sleeping — taking 30s to wake"**
→ Free tier feature. Either accept it, or upgrade to a paid Space
(~$9/month for always-on). Or, ping the URL every 30 min with a cron
job to keep it warm.

**"I want a custom domain like app.lex-indic.in"**
→ HF Spaces does support custom domains, but only on **paid** tiers.
For free, you stay on the `huggingface.co/spaces/...` URL.

## Alternative: Render.com

If HF Spaces doesn't fit, the repo also has `render.yaml` ready for
[Render.com](https://render.com). Connect GitHub repo → Render → it auto-
deploys on every push. Same auto-deploy story. Free tier sleeps after
15 min idle.

## The clean-stop-and-restart pattern

If anything ever breaks and the Space is in a bad state:
1. Go to the Space settings page
2. Click **Factory Reboot**
3. Wait for rebuild

That nukes any state and rebuilds from the latest GitHub commit.
