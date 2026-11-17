# Company Scraper

Reads a company's own website and saves the plain text of its key pages:
homepage, pricing, about, careers, security, customers and press.

Step 1 of a cold-outreach research pipeline. It only collects text; it decides nothing.

## Rules it follows
- **Step A:** at most 10 page fetches. Common paths first (`/pricing`, `/about`, ...), then links on the homepage.
- **Step B:** at most 10 more, only for pages still missing. The sitemap first, then links on pages already fetched.
- A URL counts as a page type only if its **last** path part is an exact match
  (so `/blog/pricing-guide` is not the pricing page, and `/press/some-post` is not the press page).
- 1-2 s pause between requests, 10 s timeout, robots.txt respected, LinkedIn never visited.
- Only public internet addresses are fetched (every redirect is checked too).
- Companies in `docs/do-not-contact.txt` are skipped before anything is fetched.

## Web page (Vercel)
`public/index.html` + `api/scrape.py`. Type up to 5 domains; the page asks the server for one domain
at a time and shows what was found. Nothing is saved on the server; use "Download JSON" to keep results.
There is no login: anyone with the link can use it.

### Hunter contact + Neon storage
- Every scrape is saved in Neon (project `company-scraper`) and listed under **Recent runs**.
- Each scraped domain has a **Find contact** button: ONE Hunter lookup, at most one per scrape and
  **2 per day for everyone** (India time). Role order: 1 security / CISO / compliance / GRC,
  2 CTO / head of engineering, 3 founder. Confidence under 80 is flagged LOW CONFIDENCE.
  Nobody is ever emailed. Saved contacts are deleted after 30 days.
- Settings: `HUNTER_API_KEY` and `DATABASE_URL` (see `.env.example`). On Vercel they are project
  Environment Variables; on the owner's Mac they live in the login Keychain, never in a file.
- Tables: `schema.sql`. Database tests (`test_web.py`) use a throw-away `test_...` schema only.

Local test: `.venv/bin/python tools/dev_server.py`, then open http://localhost:8780

## Command line
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scraper.py example.com another.io   # or no arguments to read domains.txt
.venv/bin/python -m unittest test_scraper test_web -v  # checks, made-up data only
```
Results go to `output/scrape/<domain>.json` and `output/scrape/run_log.txt` (not committed).
Domains already scraped are skipped unless the saved result was "unreadable".
