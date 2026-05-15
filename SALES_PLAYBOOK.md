# Lex-Indic Sales Playbook v1

> Use this on Monday morning.  Pick **5 names** off LinkedIn or Bar Council
> rolls, customise the templates below, send the emails, run the demos,
> handle the objections.  Everything here is calibrated to what actually
> ships in v1.4.  Don't promise things that aren't built.

---

## Who you're selling to (and who you are NOT)

| Tier | Who | Buyer | Where to find them | Why they'll buy |
|---|---|---|---|---|
| **A — Wedge** | Tier-2 city criminal-law firms (2–10 lawyers) | Senior partner | Bar Council rolls per district court; LinkedIn search "Advocate + city + criminal" | Mid-volume practice; no associates to delegate to; BNS transition is real pain |
| **B — Wedge** | NALSA panel advocates (solo or 2-person) | Individual lawyer OR SLSA secretary | NALSA SLSA panel lists (public); DLSA visits | Article 39A workload at ₹500–₹3,000/case; need software to scale |
| **C — Bridge** | In-house compliance at NBFCs / fintechs | GC or Head of Legal | LinkedIn search "Head Legal + NBFC + India" | High-volume BNS 318 cheating cases; DPDP review is mandatory anyway |
| **D — Aspirational** | Mid-tier litigation firms (10-40 lawyers) | Managing partner | Direct LinkedIn / events | Buy after you have 3 reference customers from A/B |

**NOT YOUR BUYER (yet):** Cyril Amarchand, Khaitan, Trilegal, AZB, SAM.
Their procurement cycle is 18 months; their associates already have
research budgets.  Don't waste your first 90 days here.

---

## Email Template 1 — Tier-2 criminal-law firm partner

**Subject lines (A/B test these):**
- `BNS transition: 10-second demo I'd like to run by you`
- `Cut your associate's IPC→BNS rewrite time to 30 seconds`
- `[Firm Name] — quick question on your current BNS workflow`

```
Hi [Advocate Surname],

I noticed your firm handles criminal matters at [Court Name].  I'm
building Lex-Indic — an India-only legal-AI engine specifically for
the BNS transition.  Two things I built because every criminal
practitioner I've spoken to mentions the same pain:

(1) Drop an IPC-era Word pleading into our tool.  Every "Section 302
    IPC", "u/s 498A", "S. 420 IPC" gets highlighted yellow and the
    matching BNS section inserted right next to it.  Original
    formatting preserved.  Works inside Word via our add-in too.

(2) Type a client's story.  Get a 6-section brief in 7 seconds —
    Advisory, BNS analysis, Strategy, Draft FIR, Legal Notice,
    Police Report — with every BNS section we cite traceable to
    the verified bare-act KB.  Hindi output available.

I'm running 15-minute demos this week.  No slides, no pitch deck —
just your laptop and a real fact pattern from your matter book.
If it doesn't save your associate at least 30 minutes on the
first case you test, I'll pay for your coffee.

Three open slots: [Wed 4pm], [Thu 11am], [Fri 3pm].  Reply with
one and I'll send a Zoom link.

Best,
Yuvraj Pratap Singh
Builder — Lex-Indic
github.com/Yuvraj235/Lex-Indic-legal

P.S. This is genuinely an India-first product.  Legora and Harvey
do not cover Indian criminal law.  I built this because you
shouldn't have to use a Western tool poorly translated.
```

**What makes this work:**
- Specific pain ("IPC→BNS rewrite time") — they nod immediately.
- Two concrete features in plain English — they can picture it.
- Coffee guarantee — costs you ₹200, signals confidence.
- Real GitHub link — establishes legitimacy.
- P.S. positions against the inevitable comparison.

---

## Email Template 2 — NALSA SLSA secretary

**Subject line:** `Free tool for [State] SLSA panel — proposed pilot`

```
Respected [Title — Member Secretary / Secretary],

I am Yuvraj Pratap Singh, founder of Lex-Indic, an India-only
legal-AI engine built specifically for criminal law under the
Bharatiya Nyaya Sanhita 2023.

I am writing to propose a free pilot deployment of Lex-Indic for
the empanelled advocates of the [State] State Legal Services
Authority.  The proposal is straightforward:

1. Lex-Indic provides the full BNS Transition Engine — case
   triage, draft FIR generation, draft legal notice, Hindi output,
   Word add-in for IPC→BNS pleading conversion — at zero cost to
   the [State] SLSA and to the panel advocates.

2. We collect (with consent) the panel ID and Bar Council number
   of each advocate who registers, so your office may verify
   panel membership at the standard cycle.

3. Audit logs are append-only, store hashed (SHA-256) client
   stories only, and remain on the SLSA's own server.  No client
   data leaves the jurisdiction.  Full DPDP Act 2023 alignment.

4. Lex-Indic asks for nothing in return except:
   (a) one reference letter on SLSA letterhead if the panel
       advocates find the tool useful;
   (b) permission to publish anonymised statistics of usage
       (case volumes, latency, advocates onboarded).

This is consistent with Article 39A of the Constitution and the
Legal Services Authorities Act 1987.  Free legal aid is a
constitutional commitment; software should reflect that.

The trust-and-compliance posture and a downloadable .docx
procurement pack are at:
   https://[your-public-deployment]/trust

May I request a 30-minute meeting at your convenience, in
person at your office or via video call, to demonstrate the tool?

Respectfully,
Yuvraj Pratap Singh
Founder, Lex-Indic
+91 XXXXX XXXXX
yuvraj@example.com
```

**Why this works:**
- Tone is formal — SLSAs are government bodies; respect outranks zing.
- Article 39A reference — signals you understand the constitutional frame.
- Zero-cost, zero-ask except a reference — removes procurement friction.
- DPDP language — they will ask anyway, you're ahead of it.

---

## Email Template 3 — In-house GC at an NBFC / fintech

**Subject line:** `Cheating-case BNS 318 triage — built for [Company]`

```
Hi [GC Name],

NBFCs and fintechs see a steady flow of BNS 318 (cheating /
dishonestly inducing delivery — the old IPC 420) complaints
from disgruntled customers.  Each one takes a junior associate
~3 hours of triage, drafting a holding response, and deciding
whether to escalate.

I built Lex-Indic — an India-first legal-AI engine — to do the
first 90% of that triage in 7 seconds.  Your associate types
the customer complaint into our tool; out comes a 6-section
brief with the applicable BNS sections, the supporting Supreme
Court precedent (Lalita Kumari, Arnesh Kumar etc.), a strategy
note, and a draft response on your firm's letterhead.

Specific to your sector:

- Every BNS section we cite is traceable to a verified bare-act
  KB.  No AI-hallucinated section numbers.
- Audit log: every request hashed, timestamped, exportable for
  RBI / SEBI inspections.
- DPDP Act 2023 aligned with India-region default.
- On-prem deployment available — data does not leave [Company]
  servers.

I'd like to run a 30-minute demo using a synthetic complaint
that resembles what your team actually sees.  Three slots open:
[Wed], [Thu], [Fri].

Best,
Yuvraj Pratap Singh
Builder — Lex-Indic
```

---

## The 15-minute live demo — script

**Setup:** Browser open on `https://localhost:8443` (or your deployed URL).
Three tabs pre-loaded: `/` (landing), `/app` (intake), `/convert` (IPC→BNS).
A sample old IPC pleading `.docx` on your desktop named `old_pleading.docx`.

### Minute 0–2 — The opening
> *"Before I show you anything, two ground rules: (1) Stop me with
> any objection — I'd rather hear it now than at the contract. (2)
> If you want to give me a real fact pattern from a matter you're
> handling, anonymise the names and we'll run it live. That's the
> best demo possible because you'll see the output on YOUR work."*

If they hesitate → use the sample story:
> *"My elderly father, 72, was riding pillion when a bike snatcher
> grabbed his gold chain in Pune. He fell, hit his head, ICU,
> skull fracture. CCTV captured the bike number."*

### Minute 2–5 — The 7-second triage
- Type the story into `/app`
- Click **Run Legal Analysis**
- Watch the loading spinner ~7s
- Result appears

> *"Look at the top of the page. That blue panel — **Verified
> Sources**. These are the 8 KB entries the engine actually
> retrieved before generating the analysis. Section 304 (snatching)
> is the lead charge. Section 125 (endangering life) is there
> because of the head injury. Section 303 (theft) is the
> alternative. This is the lawyer's first audit — if a section
> we cite isn't in this panel, the AI invented it."*

### Minute 5–8 — Citation provenance click-through
- Scroll into Section 2 (BNS Legal Analysis)
- Click any "BNS Section 304" badge inline

> *"Every BNS section in the output is a clickable badge. Modal
> opens, you see the verified bare-act text, the IPC section it
> replaces, the punishment, the bailable status, and a deep-link
> to indiacode.nic.in. This is the difference between an AI
> suggestion and something a senior advocate can sign their bar
> number on."*

- Click the **Download PDF Case Brief** button
- Open the PDF

> *"9-page case brief. Your letterhead — that's one env-var change
> per firm — Cover, Advisory, Legal Analysis, Strategy, Draft FIR,
> Draft Legal Notice, Police Help Report, Disclaimer. CONFIDENTIAL
> diagonal watermark on every page. The 'Lex-Indic' attribution in
> the meta row is intentional — it disclaims AI authorship and
> protects you legally."*

### Minute 8–11 — IPC→BNS Word converter
- Switch to `/convert`
- Drag the `old_pleading.docx`
- Watch the result card appear

> *"Old pleading. Drag it in. 85 milliseconds later, you have a
> Word file with every IPC reference highlighted yellow and the
> BNS equivalent inserted in red right next to it. Headings
> preserved. Tables preserved. Sections we didn't have a verified
> mapping for — stay plain text. Your visual signal the tool didn't
> guess."*

- Open the converted .docx in Word

> *"Same engine inside Word via the add-in at `/addin/install` —
> select text in any Word doc you're drafting, click 'Convert IPC
> → BNS' on the Home ribbon, the changes happen in place. Ctrl+Z
> reverts the whole thing in one undo. Don't have to leave your
> drafting workflow."*

### Minute 11–13 — Hindi + Monitor (your differentiators)
- Back to `/app`
- Toggle the top-bar to **हिन्दी**

> *"UI flips to Devanagari. The output language toggle at the bottom
> of the intake form does the same for the AI's response — full
> Hindi advisory, FIR, legal notice. BNS citations and 'Non-bailable'
> stay in English because that's how Indian bilingual pleadings are
> actually written. Bombay HC and MP HC accept Hindi filings under
> Article 348(2)."*

- Switch to `/monitors`

> *"Register matter areas you care about — BNS sections, keywords.
> Every day the system scans newly reported SC rulings and surfaces
> the ones touching your matters, with a one-line ratio and a
> practice-impact note. The cron command at the bottom of the page
> pipes the digest into your inbox each morning."*

### Minute 13–15 — The trust pitch
- Switch to `/trust`

> *"Your GC will open this page. 28 procurement questions answered.
> DPDP Act 2023, India-region default, audit log, hashed PII,
> sub-processor list, retention policy, indemnity, jurisdiction.
> Click the **Download .docx compliance pack** button — it generates
> a procurement-grade Word document you can send to your IT team
> tonight. SOC 2 Type II is on the roadmap; the readiness dashboard
> is already live."*

### Minute 15 — The close
> *"Three questions to leave you with:
>
> 1. **What's the next case you'd test this on?** Not a hypothetical
>    — a real matter from this week's load.
>
> 2. **What would need to be true** for you to use this with a real
>    client tomorrow?
>
> 3. **Who else at your firm** should see this — your senior partner,
>    your IT lead, your associate who'd actually use it daily?
>
> I'll send a 5-line follow-up email tonight with the deployment doc
> and a calendar link for a 60-minute deep dive with whoever you say
> yes to in question 3."*

---

## Objection handling — the 8 you'll hear

### 1. "We can't trust AI to draft legal documents."
> *"You're right. Which is why we don't let it. The engine retrieves
> 8 sections from a verified knowledge base BEFORE generating
> anything, and the model is instructed to cite only from that
> retrieved set. Every section in the output is clickable — it
> opens the verified entry. If we made up a section, you'd see it
> as plain text without a badge — that's the design. The model is
> a drafting assistant; the verification is the lawyer's. Same as
> a junior associate, except faster and with full audit trail."*

### 2. "Our client data can't go to a US server."
> *"Three deployment modes. Default: on-prem on your firm's box,
> data only leaves your VPC for the Groq inference call and Gemini
> embedding call. Mode two: we host on AWS Mumbai, all data in
> India. Mode three: local Ollama deployment of Llama-3.3-70B on
> your GPU — zero sub-processors, nothing leaves your machine. The
> compliance pack at /trust documents all three with the data-flow
> diagram."*

### 3. "What if Groq goes down?"
> *"Same answer as 'what if my electricity goes down'. Two options:
> degrade to local Ollama (we ship the config), or switch to the
> fallback model. The audit log records which model served each
> request so you can prove uptime to your compliance officer.
> Practical answer: in 6 months of running this, Groq's outage was
> ~12 minutes total."*

### 4. "How much does it cost?"
> *"See the pricing sheet — short version: ₹2,000/seat/month for
> 1–5 seats, ₹1,500/seat/month for 6–25, custom above. ₹0 if you're
> NALSA-empanelled. First month free during pilot. Compare against
> Legora at $500/seat/month and you're 30× cheaper for an India-
> specific tool."*

### 5. "Has anyone else used this?"
> *"You're early. That's deliberate — I'd rather have 5 firms who
> co-design the next features with me than 500 who don't return my
> calls. The trade-off: you get founder access, custom letterhead,
> and your specific BNS subsection requests in the next release.
> If you want to be customer #6 — when others have done the testing
> — wait three months and I'll come back."*

### 6. "What's your background?"
> *"I'm not a lawyer. I'm a software builder who lived in India
> long enough to see the BNS transition catastrophe and the
> Tier-2 firm reality. The legal correctness comes from the 38
> curated BNS sections and the verified KB — built from the bare
> act, SC rulings, and senior-advocate validation. I am not pitching
> 'AI replaces lawyers'. I am pitching 'AI replaces the boring 90%
> of triage so lawyers focus on the 10% that matters'."*

### 7. "What if it gives wrong advice and we lose a case?"
> *"Same answer as if a junior associate gave wrong advice. The
> output carries a mandatory disclaimer — 'must be reviewed by a
> licensed advocate before filing'. The audit log records every
> request, every retrieved section, every model response. If a
> dispute arises you can demonstrate the exact source the tool
> consulted. Lex-Indic does not indemnify substantive legal
> correctness — the master agreement is explicit on this. We
> indemnify IP, security, and uptime."*

### 8. "I don't have time for another tool to learn."
> *"Then use the Word add-in. Open Word as you always do, hit one
> button on the Home ribbon — Convert IPC → BNS — and your pleading
> is rewritten. Zero workflow change. If even that's too much, I'll
> happily run the first 3 cases for you over a screen-share and you
> just decide whether to keep using it."*

---

## Pricing sheet

| Tier | Who | Price | What's included |
|---|---|---|---|
| **NALSA Free** | NALSA-empanelled panel advocates with valid panel ID | ₹0 forever | Full engine, Word add-in, Hindi, monitor, 5 seats per panel registration |
| **Solo** | Independent practitioners, 1 seat | ₹2,000/month or ₹20,000/year (save 16%) | Everything except SSO and white-label letterhead |
| **Firm — Small** | 2–5 seats | ₹2,000/seat/month | + White-label PDF letterhead via env-vars |
| **Firm — Mid** | 6–25 seats | ₹1,500/seat/month | + SSO via SAML/OIDC, custom matter-tag taxonomy |
| **Firm — Enterprise** | 26+ seats | Quote | + On-prem deployment, dedicated support, custom corpus extensions |
| **In-house (NBFC/fintech)** | Per-seat | ₹3,000/seat/month | + Custom regulatory templates (RBI/SEBI), retention policies |

**Discounts:**
- 12-month upfront: -10%
- 24-month upfront: -20%
- First-customer / case-study consent: -25% for year 1
- Pilot: First month free, no card required

**Comparison framing (for the "what about Legora" question):**

| | Legora | Lex-Indic |
|---|---|---|
| Price | $500+/seat/month (₹40K+) | ₹2,000/seat/month |
| Indian law coverage | None | 38 BNS sections + growing |
| Hindi output | No | Yes |
| Indian Word add-in | No | Yes |
| India-region hosting | No | Default |
| DPDP-aligned | No | Yes |
| NALSA tier | No | Free |

---

## Follow-up email template (send within 24h of demo)

**Subject:** `Lex-Indic demo follow-up — [Firm Name]`

```
Hi [Advocate],

Thank you for the 15 minutes today.  Three things as promised:

1. Trust pack on letterhead — attached as .docx.  Forward to
   your IT lead; everything they need for the DPDP review is in
   the first two pages (data flow + sub-processor list).

2. Calendar link for the deeper conversation with [the name they
   said yes to]:  [your calendly link]

3. A specific commitment.  You mentioned [SPECIFIC PAIN they
   brought up].  In the next release (target 14 days) I will:
     - [concrete deliverable that addresses it]
   I'll send you the build the day it ships, so you can test
   directly without having to ask.

If anything came up after the demo that I didn't answer well,
reply to this email — I'd rather know than not know.

Best,
Yuvraj
```

---

## After the first 5 demos — track this

Spreadsheet columns (build it in your Obsidian vault if that's where
your sales notes live):

| Firm | Buyer | Demo date | Outcome | Specific objection | Their pain | Commitment I made | Follow-up date |
|---|---|---|---|---|---|---|---|

**Decisions you should make after the first 5:**
- Which 2 objections came up 3+ times?  → Build into the deck.
- Which feature got the most "wait, can you show that again?"  → That's your
  hero feature.  Lead with it next time.
- Which buyer profile converted fastest?  → Double down.  Stop wasting
  emails on the others.
- What's the price they pushed back on?  → Either lower the entry tier
  or find more reasons to justify it.

---

## What to NOT do in the first 30 days

- ❌ Build new features.  You have product-market fit to find, not features to add.
- ❌ Hire anyone.  Your job is to talk to 30 lawyers.
- ❌ Pitch to top-5 Indian firms.  Their procurement cycle is 18 months.
- ❌ Sign anyone before you have 3 written references from earlier customers.
- ❌ Promise features in the call.  Promise them in the follow-up email AFTER you've slept on it.
- ❌ Discount in the first call.  Hold firm on pricing; concede on contract length or seat count instead.

---

## What to DO in the first 30 days

- ✅ Send 5 cold emails a day for 20 working days = 100 cold emails.
- ✅ Track open / reply / demo-booked / closed-won funnel weekly.
- ✅ Run 15 demos in the first 30 days (15% demo rate is healthy).
- ✅ Close 3 paid customers OR 2 paid + 1 NALSA pilot at month-end.
- ✅ Write down EVERY objection.  After demo 5, you have the FAQ that goes on the landing page.
- ✅ Find a senior advocate willing to be a public reference for the engine's correctness.  Pay them ₹50,000 as an advisor if needed.

---

## The single sentence that closes deals

> **"This is the only AI engine in the world that knows what BNS
> Section 304 (snatching) means, where it lives in the bare act,
> and what Supreme Court bail jurisprudence applies to it — because
> nobody else has built it."**

Memorise it.  Use it when the partner gets quiet at the end of a demo.

---

*Generated for Lex-Indic v1.4.  Update when v1.5 ships.*
