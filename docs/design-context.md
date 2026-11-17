# Design context: Company Scraper (interface + user journey)

Use this file to redesign the **interface and the user journey** of the Company Scraper web page.
It describes what the tool does today, every screen state, the data the page receives, and the
rules a new design must keep. All example data is made up (fake-co.com, "Pat Lee").

---

## 1. What the product is

A small internal research tool for a **Growth Lead** doing cold-outreach research (B2B SaaS companies,
mostly Indian). It is Step 1 of a larger pipeline: it only **collects facts**, it never decides or sends anything.

For each company domain typed in, it:
1. **Scrapes the company's own website** and keeps the plain text of up to 7 key pages:
   homepage, pricing, about, careers, security, customers, press.
2. **Saves** the result (so it can be reopened later from "Recent runs").
3. Optionally **finds ONE contact person** with Hunter.io, on a button click, under a strict daily limit.

The user is **not technical**. Plain words, no jargon, clear next steps.

**Nobody is ever emailed from this tool.** A found contact is research only.

---

## 2. Who uses it and why

- **Primary user:** the Growth Lead (one person). Runs a few companies at a time, reads what was found,
  decides whether a company is worth a closer look, and sometimes looks up who to contact.
- **Secondary viewer:** an instructor or teammate opening the link to see how it works.
- There is **no login**. Anyone with the link can use it (accepted risk). The design must not assume
  accounts, profiles or per-user history.

What the user wants to get out of a session:
- "Which of these companies have a security / pricing / careers page, and what do they say?"
- "Is there anything here worth using?" (reading page text quickly)
- "Who is the right person at this company?" (one Hunter lookup, with evidence)
- "Get back to something I ran yesterday." (Recent runs)

---

## 3. The journey today (as built)

1. **Open the page.** Top of page shows: title, one-line description, and a usage line
   `Hunter lookups today: 0 of 2 (India time)`.
2. **Type domains** (1 to 5) in a text box, one per line or comma-separated. Duplicates are removed.
   More than 5 shows an error and nothing runs.
3. **Press "Scrape".** Domains run **one after another** (not in parallel). For each: a spinner line
   `Scraping 2 of 5: fake-co.com …`. Each domain takes **about 15–25 seconds** (worst case ~100 s).
   A full run of 5 takes 1.5–2 minutes. Each result card appears as soon as its domain finishes.
4. **Read a result card** per domain (see section 4).
5. **(Optional) Press "Find contact with Hunter (uses 1 daily lookup)"** on a card. Takes a few seconds.
   The card then shows the person, or "No contact found", or an error (e.g. daily limit reached).
6. **(Optional) "Download JSON"** saves all results shown on screen as one file.
7. **Recent runs** (bottom of page): a table of the 20 newest saved scrapes from everyone.
   "Open" loads that saved scrape (and its contact, if any) into the results area, replacing what was there.

Known pain points in the current journey (good places to improve):
- Long waits with only a one-line spinner; no sense of progress inside a domain.
- Page text is dumped as long raw text blocks; hard to skim.
- Found/missing pages are small chips; it is not obvious *why* a page is missing.
- "Open" on a recent run silently replaces the current results.
- Recent runs is a plain table with no search/filter; the contact column is just text.
- The Hunter button's cost (1 of only 2 per day, shared by everyone) is easy to miss.
- No overview across domains (e.g. a summary table of 5 companies side by side).
- The run log is technical and mostly noise for this user.

---

## 4. Everything a result card can show

### 4.1 Card header
- Domain name.
- Status badge, one of:
  - **OK**: at least one page was read.
  - **PARTIAL (OUT OF TIME)**: OK, but stopped early because of the time limit (`ran_out_of_time: true`).
  - **UNREADABLE**: nothing readable (site down, blocked, or JavaScript-only).
  - **SKIPPED**: on the do-not-contact list; nothing was fetched (shows the reason).
  - **ERROR**: something failed (shows a short message).

### 4.2 Meta line
Seconds taken · number of fetches (step A / step B) · robots.txt note · saved time (India time),
or "not saved: <reason>" if the database was unavailable.

### 4.3 Pages
- Seven page types, each **found** or **missing**.
- For each found page: page type, URL, number of characters, **how it was found**
  (`homepage`, `common path`, `homepage link`, `sitemap`, `crawl`), and the **full plain text**
  (up to 20,000 characters, line breaks kept). A page can be "empty" (the site needs JavaScript).
- Missing pages: today the reason is only in the technical log; the data has per-attempt reasons
  (see `attempts` in section 6) that a design could surface in plain words
  (e.g. "No /pricing page (404)", "Blocked by the site's robots.txt", "Redirected to homepage").

### 4.4 Run log (technical)
Time-stamped lines of every fetch. Useful for debugging, not for the main user. Can be hidden away.

### 4.5 Contact (Hunter) area
Shown only if the scrape was saved.
- **Not looked up yet:** button "Find contact with Hunter (uses 1 daily lookup)".
- **Looking up:** button disabled, spinner "Asking Hunter…".
- **Found:**
  - Name · exact job title as Hunter lists it
  - Email · confidence (0–100) · email verification status (`valid`, `accept_all`, `unknown`, …)
  - **LOW CONFIDENCE** badge when confidence is under 80 (must stay clearly visible)
  - "Picked by rule N (label) from X people Hunter returned." Rules, in order:
    1 security / CISO / compliance / GRC → 2 CTO / head of engineering → 3 founder
  - Hunter source links (evidence). Often weak, e.g. a Google search link. Keep them visible.
  - "Do not email from here. This is research only."
  - When reopened from Recent runs: "Looked up <date, India time>".
- **None found:** "No contact found. Hunter returned N people; none had a matching title with a name."
- **Errors (each needs a clear state):**
  - Daily limit reached (2 per day for everyone, resets at midnight India time).
  - Hunter could not be reached / returned an error (the lookup is NOT counted; user can try again).
  - A lookup for this scrape is already running.
  - Company is on the do-not-contact list.
  - Hunter or database not set up.
- A scrape can only ever have **one** lookup. Pressing again just shows the saved contact.

---

## 5. Hard rules the design must keep

These are decisions by the owner. A redesign may change how they look, not whether they apply.

1. **Max 5 domains per run.** Domains run one at a time.
2. **Never email anyone.** No "send", "compose", "copy email to outreach", or mailto: actions.
   The contact is shown as research only, with the "do not email from here" note.
3. **Hunter costs are explicit.** Show the daily usage (`x of 2`, India time) and that each lookup
   uses one. Lookup only on an explicit click, one company at a time. Never automatic, never "look up all".
4. **One lookup per saved scrape.** After it exists, show it; don't offer another.
5. **LOW CONFIDENCE stays visible** when confidence < 80. The exact title and the sources stay visible (they are the evidence).
6. **Do-not-contact companies** show as Skipped, with no Hunter button.
7. **Contacts are deleted after 30 days.** Say so somewhere visible.
8. **No login, no accounts.** Recent runs are shared by everyone who has the link.
9. **Plain language** for a non-technical user. Technical details (fetch counts, log) are secondary.
10. **Missing = unknown.** Never imply a page or fact exists when it was not found.
11. **LinkedIn is never visited by the scraper** (Hunter's own source links may still point there; show them as-is).

---

## 6. Technical facts the design must fit

- **One static HTML file**: `public/index.html` (HTML + CSS + plain JavaScript, no build step, no framework).
  It currently supports light and dark mode (`prefers-color-scheme`) and works on phones.
  Prefer no external scripts or fonts (if any, they must be loadable from a public CDN without keys).
- Hosted on **Vercel**. The page talks to 4 small server functions (Python). These stay as they are:

| Call | Purpose | Notes |
|---|---|---|
| `POST /api/scrape` body `{"domain": "fake-co.com"}` | Scrape ONE domain, save it, return the result | 15–25 s typical, up to ~120 s. Call once per domain, in sequence. |
| `POST /api/contact` body `{"scrape_id": "<id>"}` | ONE Hunter lookup for a saved scrape | A few seconds. |
| `GET /api/runs` | 20 newest saved scrapes (no page text, no contact details) | |
| `GET /api/runs?id=<id>` | One saved scrape with pages + its contact | |
| `GET /api/usage` | Today's Hunter count, cap, whether database/Hunter are set up | |

- **Every POST must send the header `X-Requested-With: fetch`** and `Content-Type: application/json`,
  or the server refuses it (403).
- The page uses a 130-second timeout per call.
- Times from the server are ISO strings (UTC); the page shows them in **India time (IST)**.

### Example: `POST /api/scrape` result (shortened)
```json
{
  "domain": "fake-co.com",
  "status": "ok",                       // "ok" | "unreadable"   (skipped/error: see below)
  "seconds": 18.4,
  "robots": "robots.txt read",
  "fetches": {"step_a": 9, "step_b": 1},
  "found": ["homepage", "about", "careers", "customers"],
  "missing": ["pricing", "security", "press"],
  "ran_out_of_time": false,
  "pages": {
    "homepage": {"url": "https://fake-co.com/", "found_by": "homepage", "step": "A",
                 "chars": 13623, "empty": false, "text": "Fake Co\nWe help teams ..."},
    "pricing": null,
    "about": {"url": "https://fake-co.com/about-us", "found_by": "homepage link", "step": "A",
              "chars": 4332, "empty": false, "text": "..."}
  },
  "attempts": [
    {"url": "https://fake-co.com/pricing", "type": "pricing", "step": "A",
     "found_by": "common path", "status_code": 404, "result": "HTTP 404"},
    {"url": "https://fake-co.com/careers", "type": "careers", "step": "A",
     "found_by": "common path", "status_code": 200, "result": "kept"}
  ],
  "log": ["2026-11-17 10:41:12  fake-co.com  [A1] homepage  https://fake-co.com/ -> kept, 13,623 chars"],
  "saved": true,
  "scrape_id": "6f1c0c1e-1111-2222-3333-444455556666",
  "saved_at": "2026-11-17T10:41:30+00:00"
}
```
Possible `attempts[].result` texts: `kept`, `HTTP 404` (or other code), `error: ConnectionError`,
`redirected to the homepage (page does not exist)`, `same text as the homepage (page does not really exist)`,
`empty (no readable text; maybe JavaScript-only)`, `blocked by robots.txt`, `not a web page (...)`,
`redirected off the site to ...`.

Other shapes:
```json
{"domain": "whatfix.com", "status": "skipped", "reason": "on the do-not-contact list (nothing fetched)"}
{"error": "That is not a domain.", "input": "hello world"}
{"domain": "fake-co.com", "error": "Scrape failed (TimeoutError)", "log": ["..."]}
```
If saving failed: `"saved": false, "save_error": "could not save to the database (OperationalError)"` (no `scrape_id`; hide the Hunter button).

### Example: `POST /api/contact` result
```json
{
  "outcome": "found",                   // "found" | "none"
  "already": false,                     // true = this was looked up before; no new lookup was used
  "contact": {
    "name": "Pat Lee", "position": "Co-Founder and CTO", "email": "pat@fake-co.com",
    "confidence": 95, "low_confidence": false, "verification": "valid",
    "rule": 2, "rule_label": "CTO / head of engineering",
    "sources": ["https://fake-co.com/team"], "people_returned": 10
  },
  "usage": {"hunter_used": 1, "hunter_cap": 2}
}
```
None found: `{"outcome": "none", "contact": {"people_returned": 4}, "already": false, "usage": {...}}`
Errors (HTTP code → meaning): 429 daily limit reached · 502 Hunter error (not counted) ·
409 lookup already running · 403 do-not-contact · 404 scrape not found · 503 not set up.
All errors look like `{"error": "<plain sentence>", "usage": {...}}` (usage sometimes absent).

### Example: `GET /api/runs`
```json
{"runs": [
  {"id": "6f1c0c1e-...", "created_at": "2026-11-17T10:41:30+00:00", "domain": "fake-co.com",
   "status": "ok", "found": ["homepage", "about"], "missing": ["pricing"], "contact": "found"}
]}
```
`contact` is `null` (not looked up), `"pending"`, `"found"` or `"none"`.

### Example: `GET /api/runs?id=...`
```json
{"scrape": { ...same shape as the scrape result, plus "scrape_id" and "saved_at"... },
 "contact": {"outcome": "found", "contact": { ...as above... }, "looked_up_at": "2026-11-17T10:45:02+00:00"}}
```
`contact` is `null` if no lookup was done.

### Example: `GET /api/usage`
```json
{"database": true, "hunter_ready": true, "hunter_used": 1, "hunter_cap": 2}
```
If `database` is false: results are not saved, Recent runs and Hunter are unavailable; the page should say so plainly.

---

## 7. What to deliver

- A redesigned **interface and journey** for `public/index.html`: layout, states (empty, running,
  each result status, each Hunter state, each error), and copy (plain English).
- Ideally the **working HTML/CSS/JS** for `public/index.html` that calls the same endpoints with the
  same headers. It must drop in without server changes.
- If something in the design needs a server change (new data or a new endpoint), list it separately
  so it can be decided and built on purpose.
