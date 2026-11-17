# Design context: Company Scraper (interface + user journey)

Use this file to redesign the **interface and the user journey** of the Company Scraper web page.
It describes what the tool does, every step and screen state, the data the page receives, and the
rules a new design must keep. All example data is made up (fake-co.com, "Pat Lee").

---

## 1. What the product is

An internal outreach-research tool for a **Growth Lead** at Sprinto (a compliance-automation company:
SOC 2, ISO 27001 and similar). It turns a company website into a **reviewed draft cold email**, one
careful step at a time. Target companies are B2B SaaS, mostly Indian.

The full journey, per company:

| # | Step | What happens | Who decides |
|---|---|---|---|
| 0 | **Scrape** | Reads the company's own website: up to 7 pages (homepage, pricing, about, careers, security, customers, press). Saved. | Code |
| 1 | **Company picture** | AI lists facts from those pages. Every fact has a source link and an exact quote, checked word for word. | AI suggests, code checks |
| 2 | **Checks and decision** | 4 checks (B2B SaaS? funding stage? audit need? enterprise pressure?). If something is unknown, at most 2 web searches. Result: **Go / Flag / No-Go**. | Code (fixed rules) |
| 2b | **Approve a Flag** | A Flag needs a human click before anything continues. | **The user** |
| 3 | **Contact** | Hunter.io finds ONE person (security lead > CTO > founder). Strict daily limit. | Code |
| 4 | **Pain points** | Picks up to 2 typical challenges for that person's role from an approved list. | Code (no AI) |
| 5 | **Email draft** | AI suggests opening quotes ("hooks") from the company's pages; code checks them and fills a fixed template. | AI suggests, code checks |
| 6 | **Send to my inbox** | Sends the draft ONLY to the user's own inbox for review, on an exact typed command. | **The user** |

Then the **campaign record** keeps everything: facts, checks, decision, contact, pain points, draft,
status and next steps.

The user is **not technical**. Plain words, no jargon, always show what to do next.

**No prospect is ever emailed by this tool.** The only email it sends goes to the user's own inbox.

---

## 2. Who uses it and why

- **Primary user:** the Growth Lead (one person). Runs a few companies at a time, reads the evidence,
  approves or stops each company, and reviews drafts in their own inbox.
- **Secondary viewer:** an instructor or teammate opening the link to see how it works.
- There is **no login**. Anyone with the link can use it (accepted risk). The design must not assume
  accounts, profiles or per-user history.

What the user wants from a session:
- "Which of these companies are worth contacting, and why?" (decision + evidence)
- "Can I trust this?" (every claim has a quote and a link)
- "Who is the right person, and what would I say?" (contact, pain points, draft)
- "Send me the draft so I can review it properly." (own inbox only)
- "Where was I with the company from yesterday?" (Recent runs + status + next steps)

---

## 3. The journey today (as built)

1. **Open the page.** Title, a one-line description, and a usage line
   `Hunter lookups today: 0 of 2 (India time)`.
2. **Type domains** (1 to 5), one per line or comma-separated. Duplicates removed. More than 5 = error.
3. **Optional: tick "TEST ONLY run"** before scraping. This is chosen once, at the start, and is locked
   to those companies (see rule 9 in section 6).
4. **Press "Scrape".** Domains run **one after another**. Spinner line `Scraping 2 of 5: fake-co.com …`.
   About **15–25 s per domain** (worst case ~120 s). Each result card appears as it finishes.
5. **Each card** shows the scrape result, then a **Status box**, then the numbered steps 1–6 underneath.
   Only the next step has an active button; later steps say what they are waiting for.
6. The user **presses each step's button in order**. Each AI step takes about 30 s to 2 min. After each
   step the whole card refreshes with the new state.
7. **Recent runs** (bottom): the 20 newest saved scrapes from everyone, with Decision, Contact and Email
   columns. "Open" loads that saved company, with everything done so far, into the results area.
8. **"Download JSON"** saves all results on screen as one file.

Known pain points in the current journey (good places to improve):
- The card is one very long column: pages, then 6 steps. Hard to see where a company stands at a glance.
- Long waits with only a spinner on the button; no sense of progress.
- Page text is dumped as long raw text blocks; hard to skim.
- Evidence (quotes + links) is everywhere but visually noisy; hard to tell strong from weak evidence.
- No overview across companies (e.g. a pipeline / board view of 5 companies by stage or decision).
- "Open" on a recent run silently replaces the current results.
- Recent runs has no search or filter.
- The cost of actions (Hunter: 2 per day for everyone; AI steps; sends: 3 per day) is easy to miss.
- The typed send command is safe but clunky; it needs to stay deliberate (see rules) but can be clearer.
- The run log is technical noise for this user.

---

## 4. Everything a card can show

### 4.1 Header and scrape result
- Domain name, a **TEST ONLY** badge if it is a test run, and a status badge:
  **OK** · **PARTIAL (OUT OF TIME)** · **UNREADABLE** (nothing readable) · **SKIPPED** (on the
  do-not-contact list; nothing fetched) · **ERROR** (short message).
- Meta line: seconds, fetch counts, robots.txt note, saved time (India time) or "not saved: <reason>".
- Seven page types, each **found** or **missing**. For found pages: URL, characters, how it was found
  (`homepage`, `common path`, `homepage link`, `sitemap`, `crawl`), and the full plain text (up to 20,000
  chars). Missing pages have per-attempt reasons in `attempts` that could be shown in plain words
  ("No /pricing page (404)", "Blocked by robots.txt", "Redirected to homepage").
- Run log: technical, can be hidden away.

### 4.2 Status box (campaign record)
One line of status plus a short "next steps" list, from the server. Statuses:
`Scraped` · `Picture built` · `Flag: waiting for your approval` · `Go: ready for Hunter` /
`Flag: ready for Hunter` · `No-Go` · `Contact found` · `No contact found` · `Pain points picked` ·
`Email drafted, ready for review` · `No hook found, so no email` ·
`Draft delivered to your inbox and logged` · `Send outcome unclear`.

### 4.3 Step 1 · Company picture
- Button: "Build company picture" (AI, ~30 s; uses 1 of 50 daily AI steps). Later: "Rebuild picture"
  (resets everything after it).
- Shows a list of facts. Each: field label, short value, the **exact quote** and a **source link**.
  Fields: Name, What they do, B2B SaaS?, Funding, Team size, Certification held, Certification in
  progress, Security / compliance job, Open role, Enterprise plan, Security reviews, Named customer,
  Country / market, Recent update.
- "N AI statements rejected (quote not word for word on the page)" and the AI model name.

### 4.4 Step 2 · Checks and decision
- Button: "Run checks" (up to ~2 min; may do up to 2 web searches). Later: "Re-run checks".
- **Decision badge**: Go (green) · Flag (amber) · No-Go (red), plus a one-line reason.
- Four rows, each with an answer badge **YES / NO / UNKNOWN**, a plain reason and its evidence quotes:
  - B2B SaaS (the gate)
  - Q1 Size: Series A–C = yes; Series D+ or public = no; seed / unclear = unknown
  - Q2 Audit prep: certification in progress, a security/compliance job, or breach news = yes;
    already holds BOTH SOC 2 and ISO 27001 = no
  - Q3 Client pressure: enterprise plan, security reviews, or a named customer (weak) = yes; never "no"
- Evidence from a web search is labelled "search result". Negative news is labelled
  "never used as an email hook".
- The searches done, e.g. `"Fake Co data breach" → no results`.
- **Flag**: "A Flag needs a human decision before Hunter can run." + button **"I approve this Flag"**.
  After: "Flag approved by a human."

### 4.5 Step 3 · Contact (Hunter)
- Blocked until allowed: "Run the checks first." / "Approve the Flag first." /
  "No-Go: Hunter will not run (only a TEST ONLY run overrides this)."
- Button: "Find contact with Hunter (uses 1 daily lookup)". Spinner "Asking Hunter…".
- **Found**: name · exact job title · email · confidence (0–100) · verification (`valid`, `accept_all`,
  `unknown` …) · **LOW CONFIDENCE** badge if confidence < 80 · "Picked by rule N (label) from X people
  Hunter returned" (rules: 1 security / CISO / compliance / GRC, 2 CTO / head of engineering, 3 founder) ·
  Hunter source links (often weak, keep visible) · "Looked up <date>" ·
  "Do not email from here. This is research only."
- **None found**: "No contact found. Hunter returned N people; none had a matching title with a name."
  The journey stops here.
- Errors: daily limit reached (2 per day for everyone, resets midnight India time) · Hunter error (not
  counted, can retry) · lookup already running · do-not-contact · not set up.
- One lookup per saved scrape, ever.

### 4.6 Step 4 · Pain points
- Button: "Pick pain points" (no AI, instant). Later: "Pick again".
- Shows the role group (security / compliance, CTO / engineering, founder) and up to 2 items:
  id (e.g. C4), the pain point, a note ("typical for the role; no company-specific evidence" or
  "backed by a quoted page fact") and, if backed, the quote + link.
- "(list is still a DRAFT)" while the owner hasn't approved the wording.

### 4.7 Step 5 · Email draft
- Button: "Draft email" (AI, ~30 s, uses 1 AI step). Later: "Draft again".
- Shows: **subject** (with "[TEST ONLY] " in front on test runs), **word count** (aim 80–100), which
  hook number is used, "wording is still a DRAFT" if so, and the **full plain-text body**.
- **Hooks that passed every rule**, numbered 1..n: the quote, a source link, its topics
  (customers, security, compliance, enterprise, hiring, countries, global). The user can pick any of
  these when sending.
- **Rejected hooks** (collapsed): the quote and why ("funding words are banned as hooks", "negative news
  is never a hook", "looks like menu or button text", "not word for word on that page", "3 words (must
  be 4 to 30)" …).
- **No hook found**: "No hook found, so no email." The journey stops here.

### 4.8 Step 6 · Send to my inbox
- Text: "Goes ONLY to your own inbox (never the contact), once, plain text. To send, type exactly:
  `send fake-co.com, hook 1` (or another hook number)."
- A text input + button "Send to my inbox". Wrong text → error "Type exactly: send fake-co.com, hook <number>".
- **Sent**: "delivered" badge, "Sent <time> to your own inbox with hook N. Logged."
- **Unclear** (Resend timed out): "unclear" badge + "Check your inbox before trying again." Locked.
- **Refused** (Resend said no, nothing sent): error shown, the user may try again.
- Other errors: already sent (never twice), daily send limit (3 per day), not set up.
- The email that arrives starts with a review header: "DRAFT FOR YOUR REVIEW. This went only to you,
  never to the contact.", who it is intended for (name, title, email, confidence), the decision, the
  hook source, the pain point ids. Then the draft.

---

## 5. Daily limits (India time, shared by everyone with the link)
- Hunter lookups: **2 per day**.
- AI steps (company picture + email drafts): **50 per day**.
- Sends to own inbox: **3 per day**.
Today only the Hunter count is shown on the page (`/api/usage`). Showing the others needs a small
server change (list it separately).

---

## 6. Hard rules the design must keep

These are the owner's decisions. A redesign may change how they look, not whether they apply.

1. **Max 5 domains per run.** Domains run one at a time.
2. **Steps run in order, one click each.** Never "run everything" or "do all companies" for AI, Hunter or send.
3. **Never email a prospect.** No mailto:, no "send to contact", no "copy to outreach tool". The only send
   goes to the user's own inbox, and needs the exact typed command `send <domain>, hook <n>`.
4. **Never twice.** One Hunter lookup per company; one send per company.
5. **Costs are explicit.** Show daily usage and what each button uses.
6. **A Flag needs a human approval** before Hunter. No-Go stops (except TEST ONLY).
7. **Every fact, answer and hook shows its exact quote and source link.** Missing = unknown; never imply
   something exists that wasn't found. LOW CONFIDENCE stays visible (< 80).
8. **Negative news can qualify a company but is never an email hook.** Keep the label visible.
9. **TEST ONLY** is chosen before scraping, locked to those companies, shown as a badge everywhere
   (card, recent runs), and puts "[TEST ONLY]" in the email subject.
10. **Do-not-contact companies** show as Skipped, with no further steps.
11. **Contacts are deleted after 30 days.** Say so somewhere visible.
12. **No login, no accounts.** Recent runs are shared by everyone with the link.
13. **Plain language** for a non-technical user. Technical details are secondary.
14. **LinkedIn is never visited by the scraper** (Hunter's source links may point there; show as-is).
15. The pain-point list and email wording are **owner-approved files**, not editable on the page.

---

## 7. Technical facts the design must fit

- **One static HTML file**: `public/index.html` (HTML + CSS + plain JavaScript, no build step, no framework).
  Supports light and dark mode (`prefers-color-scheme`) and works on phones. Prefer no external scripts
  or fonts (if any, from a public CDN, no keys).
- Hosted on **Vercel**. The page talks to 5 small server functions (Python). These stay as they are:

| Call | Purpose | Notes |
|---|---|---|
| `POST /api/scrape` `{"domain": "fake-co.com", "test_only": false}` | Scrape ONE domain, save it | 15–25 s typical, up to ~120 s. One call per domain, in sequence. |
| `POST /api/step` `{"scrape_id": "<id>", "step": "<step>"}` | Run ONE pipeline step, return the updated state | steps: `picture`, `check`, `approve`, `pain`, `draft`, `send`, `state`. `send` also needs `"command": "send fake-co.com, hook 1"`. Up to ~5 min. |
| `POST /api/contact` `{"scrape_id": "<id>"}` | ONE Hunter lookup | A few seconds. |
| `GET /api/runs` | 20 newest saved scrapes (summary only) | |
| `GET /api/runs?id=<id>` | One saved scrape with pages + its full state | |
| `GET /api/usage` | Today's Hunter count and cap; whether database / Hunter are set up | |

- **Every POST must send `X-Requested-With: fetch`** and `Content-Type: application/json`, or the server
  refuses it (403). Body max 2 KB.
- The page currently uses a 130-second timeout per call (the `check` step can need longer; a redesign
  may raise it to ~300 s for `/api/step`).
- Times are ISO strings (UTC); show them in **India time (IST)**.
- Errors always look like `{"error": "<plain sentence>"}` with an HTTP code:
  400 bad input · 403 not allowed (do-not-contact, No-Go, Flag not approved, wording still DRAFT) ·
  404 not found · 409 wrong order / already done · 429 daily limit · 502 outside service failed ·
  503 not set up.

### Example: `POST /api/scrape` result (shortened)
```json
{
  "domain": "fake-co.com", "status": "ok", "test_only": false,
  "seconds": 18.4, "robots": "robots.txt read", "fetches": {"step_a": 9, "step_b": 1},
  "found": ["homepage", "pricing"], "missing": ["about", "careers", "security", "customers", "press"],
  "ran_out_of_time": false,
  "pages": {
    "homepage": {"url": "https://fake-co.com/", "found_by": "homepage", "step": "A",
                 "chars": 13623, "empty": false, "text": "Fake Co is a B2B SaaS platform ..."},
    "pricing": {"url": "https://fake-co.com/pricing", "found_by": "common path", "step": "A",
                "chars": 2100, "empty": false, "text": "Starter\nGrowth\nEnterprise plan with SSO ..."},
    "about": null
  },
  "attempts": [{"url": "https://fake-co.com/about", "type": "about", "step": "A",
                "found_by": "common path", "status_code": 404, "result": "HTTP 404"}],
  "log": ["2026-11-17 10:41:12  fake-co.com  [A1] homepage  https://fake-co.com/ -> kept, 13,623 chars"],
  "saved": true, "scrape_id": "6f1c0c1e-1111-2222-3333-444455556666",
  "saved_at": "2026-11-17T10:41:30+00:00"
}
```
Other shapes: `{"domain": "whatfix.com", "status": "skipped", "reason": "on the do-not-contact list (nothing fetched)"}`
· `{"error": "That is not a domain.", "input": "hello world"}` · if saving failed: `"saved": false,
"save_error": "..."` and no `scrape_id` (hide all steps).

### Example: `POST /api/step` result (the "state", also returned by `GET /api/runs?id=`)
```json
{
  "next": "send",
  "status": "Email drafted, ready for review",
  "next_steps": ["Read the draft, then type: send fake-co.com, hook <number>"],
  "contact": {"outcome": "found", "looked_up_at": "2026-11-17T10:45:02+00:00",
              "contact": {"name": "Pat Lee", "position": "CTO", "email": "pat@fake-co.com",
                          "confidence": 92, "low_confidence": false, "verification": "valid",
                          "rule": 2, "rule_label": "CTO / head of engineering",
                          "sources": ["https://fake-co.com/team"], "people_returned": 3}},
  "campaign": {
    "domain": "fake-co.com", "updated_at": "...", "decision": "Flag", "flag_approved": true,
    "picture": {"facts": [{"field": "enterprise_plan", "value": "Enterprise plan",
                           "source_url": "https://fake-co.com/pricing", "quote": "Enterprise plan with SSO"}],
                "rejected": [{"field": "funding_stage", "quote": "...", "source_url": "...", "reason": "quote is not word for word on that page"}],
                "seconds": 21.0, "model": "gemini-2.5-flash"},
    "checks": {
      "company_name": "Fake Co", "decision": "Flag", "decision_reason": "Two checks YES, one unknown: needs a human decision.",
      "gate": {"answer": "yes", "why": "The site shows it is B2B SaaS.",
               "evidence": [{"source_url": "https://fake-co.com/", "quote": "Fake Co is a B2B SaaS platform",
                             "from": "page", "usable_as_hook": true, "note": ""}]},
      "q1": {"answer": "yes", "why": "Series B (A-C = YES).", "evidence": ["..."]},
      "q2": {"answer": "unknown", "why": "...", "evidence": []},
      "q3": {"answer": "yes", "why": "...", "evidence": ["..."]},
      "searches": [{"query": "Fake Co data breach", "result": "no results"}]
    },
    "pain": {"group": "C", "group_name": "CTO / engineering", "list_status": "DRAFT",
             "why": "2 picked for the CTO / engineering group.",
             "picked": [{"id": "C4", "pain": "As the team grows, access and device policies get harder to keep consistent.",
                         "phrase": "...", "note": "backed by a quoted page fact",
                         "evidence": [{"kind": "team_size", "source_url": "https://fake-co.com/about", "quote": "a team of 120 people"}]},
                        {"id": "C1", "pain": "Compliance work pulls engineers off the product roadmap.",
                         "phrase": "...", "note": "typical for the role; no company-specific evidence", "evidence": []}],
             "skipped": [{"id": "C2", "reason": "only 2 are used"}]},
    "email": {"hooks": [{"n": 1, "quote": "Enterprise plan with SSO and audit logs",
                         "source_url": "https://fake-co.com/pricing", "topics": ["security", "enterprise"]}],
              "rejected_hooks": [{"quote": "We raised our Series B in 2025.", "source_url": "https://fake-co.com/",
                                  "reason": "funding words are banned as hooks"}],
              "subject": "Fake Co and audit readiness", "body": "Hi Pat,\n\n...", "words": 88,
              "hook_n": 1, "hook_source": "https://fake-co.com/pricing", "chosen": 1,
              "test_only": false, "wording_status": "DRAFT", "pain_ids": ["C4", "C1"]},
    "sent_at": null,
    "send_result": null
  }
}
```
- `next` is one of: `picture`, `check`, `approve`, `contact`, `pain`, `draft`, `send`, `done`.
- Any part not done yet is `null` (e.g. `campaign` is `null` right after scraping).
- After sending: `sent_at` is set and `send_result` is `{"ok": true, "id": "...", "at": "...", "hook": 1,
  "to": "your own inbox", "subject": "...", "words": 88}`; `ok: false` = refused (can retry);
  `ok: null` = unclear (locked, "check your inbox").
- A No-hook draft has `"hooks": []` and `"note": "no hook found: ..."`.

### Example: `POST /api/contact` result
```json
{"outcome": "found", "already": false, "contact": { ...as in the state above... },
 "usage": {"hunter_used": 1, "hunter_cap": 2}}
```
None found: `{"outcome": "none", "contact": {"people_returned": 4}, ...}`. After a lookup, the page
calls `POST /api/step` with `"step": "state"` to refresh the card.

### Example: `GET /api/runs`
```json
{"runs": [{"id": "6f1c0c1e-...", "created_at": "2026-11-17T10:41:30+00:00", "domain": "fake-co.com",
           "status": "ok", "found": ["homepage", "pricing"], "missing": ["about"], "test_only": false,
           "contact": "found", "decision": "Flag", "drafted": true, "sent": false}]}
```
`contact`: `null` | `"pending"` | `"found"` | `"none"`. `decision`: `null` | `"Go"` | `"Flag"` | `"No-Go"`.

### Example: `GET /api/usage`
```json
{"database": true, "hunter_ready": true, "hunter_used": 1, "hunter_cap": 2}
```
If `database` is false: nothing is saved and every step after scraping is unavailable; say so plainly.

---

## 8. What to deliver

- A redesigned **interface and journey** for `public/index.html`: layout, every state (empty, running,
  each scrape status, each step's states, each error), and plain-English copy.
- Ideas worth exploring: a per-company **stage tracker** (Scraped → Picture → Decision → Contact →
  Pain → Draft → Sent), a compact **multi-company overview**, clearer evidence (quote + link) styling,
  progress feedback during long steps, and a deliberate but friendlier send confirmation (the exact typed
  command must stay).
- Ideally the **working HTML/CSS/JS** for `public/index.html`, calling the same endpoints with the same
  headers, so it drops in without server changes.
- If the design needs a server change (new data or endpoint, e.g. showing AI and send limits), list it
  separately so it can be decided and built on purpose.
