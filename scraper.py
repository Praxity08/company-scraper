#!/usr/bin/env python3
"""Step 1: scrape a company's own website and save the plain text of its key pages.

Page types looked for: homepage, pricing, about, careers, security, customers, press.

Rules (rebuilt from CONTEXT.md):
- Step A: at most 10 page fetches. Common paths first (/pricing, /about, ...),
  then links found on the homepage.
- Step B: at most 10 extra fetches, only for page types still missing.
  The sitemap first, then links found on pages already fetched ("crawl").
- 1-2 s pause between requests, 10 s timeout, robots.txt respected, never LinkedIn.
- Domains listed in docs/do-not-contact.txt are skipped before any fetch.
- Domains already scraped are skipped, unless the saved result was "unreadable".
  Before a file is overwritten, the old one moves to output/history/ with date and time.
- Press = the press index page only, never the individual posts.
- A URL counts as a page type only if its LAST path segment is one of that type's
  words (so /blog/pricing-guide is NOT a pricing page, /press/some-post is NOT press).
- Pages with no charset in the header are decoded as UTF-8.

Output: output/scrape/<domain>.json and output/scrape/run_log.txt

Usage:
    .venv/bin/python scraper.py a.com b.com
    .venv/bin/python scraper.py            # reads domains.txt
"""
import argparse
import ipaddress
import json
import random
import re
import shutil
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output" / "scrape"
HISTORY_DIR = ROOT / "output" / "history"
LOG_FILE = OUT_DIR / "run_log.txt"
DNC_FILE = ROOT / "docs" / "do-not-contact.txt"
DOMAINS_FILE = ROOT / "domains.txt"

USER_AGENT = "Mozilla/5.0 (compatible; company-research-scraper/1.0)"
TIMEOUT = 10            # seconds per request
STEP_A_MAX = 10         # page fetches in Step A
STEP_B_MAX = 10         # extra fetches in Step B (sitemap files count)
PAUSE = (1.0, 2.0)      # seconds between requests
MAX_TEXT = 20000        # characters kept per page
MAX_CHILD_SITEMAPS = 3  # sitemap index -> follow at most this many child sitemaps
MAX_REDIRECTS = 5       # redirect hops followed per request (each hop is safety-checked)

PAGE_TYPES = ["homepage", "pricing", "about", "careers", "security", "customers", "press"]
COMMON_PATHS = {
    "pricing": "/pricing",
    "about": "/about",
    "careers": "/careers",
    "security": "/security",
    "customers": "/customers",
    "press": "/press",
}
# Words allowed as the LAST path segment for each page type.
ALIASES = {
    "pricing": {"pricing", "plans", "price", "prices"},
    "about": {"about", "about-us", "aboutus", "company", "who-we-are"},
    "careers": {"careers", "career", "jobs", "join-us", "work-with-us"},
    # "compliance" alone is NOT here: on compliance-software sites it is a product page.
    "security": {"security", "trust", "trust-center", "trustcenter",
                 "security-and-compliance", "trust-and-security", "security-and-trust"},
    "customers": {"customers", "customer-stories", "case-studies", "case-study",
                  "success-stories", "clients"},
    "press": {"press", "newsroom", "news", "media", "press-releases", "in-the-news"},
}
# File URLs are never pages (this also stops sitemap .xml files being treated as pages).
FILE_EXT = re.compile(
    r"\.(xml|gz|pdf|jpe?g|png|gif|svg|webp|ico|zip|mp4|mp3|css|js|json|txt|csv|docx?|xlsx?|pptx?)$",
    re.I,
)
PAGE_EXT = re.compile(r"\.(html?|php|aspx?)$", re.I)
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")


# ---------------------------------------------------------------- small helpers

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    """Print a line and append it to output/scrape/run_log.txt."""
    line = f"{now()}  {msg}"
    print(line, flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def normalize_domain(raw):
    """'https://www.Example.com/about' -> 'example.com'. Returns None if not a domain."""
    d = raw.strip().lower()
    d = re.sub(r"^[a-z]+://", "", d)
    d = d.split("/")[0].split("?")[0].split("#")[0].split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d if DOMAIN_RE.match(d) else None


def load_do_not_contact(path=DNC_FILE):
    """Names (e.g. 'Whatfix') or domains (e.g. 'whatfix.com'), one per line."""
    if not path.exists():
        return set()
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip().lower()
        if line:
            entries.add(line.replace(" ", ""))
    return entries


def is_do_not_contact(domain, entries):
    """True if the domain itself, or its first label (whatfix.com -> whatfix), is listed."""
    return domain in entries or domain.split(".")[0] in entries


def is_linkedin(url):
    host = (urlparse(url).hostname or "").lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com") or host.startswith("lnkd.")


class UnsafeURL(requests.RequestException):
    """Raised instead of fetching a URL that is not a public web address."""


def is_public_host(host):
    """False if the host name points at a private / internal / loopback address."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # unknown name: let the normal request fail with a connection error
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            return False
    return True


def check_url_safe(url):
    """Only plain http(s) on the normal ports, never LinkedIn, only public addresses."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise UnsafeURL(f"not http(s): {url}")
    if p.port not in (None, 80, 443):
        raise UnsafeURL(f"unusual port: {url}")
    if not p.hostname or is_linkedin(url):
        raise UnsafeURL(f"not allowed: {url}")
    if not is_public_host(p.hostname):
        raise UnsafeURL(f"not a public address: {p.hostname}")


def same_site(url, domain):
    host = (urlparse(url).hostname or "").lower()
    return host == domain or host.endswith("." + domain)


def classify(url):
    """Which page type a URL is, judged ONLY by its last path segment. None if no match."""
    path = urlparse(url).path.lower()
    if FILE_EXT.search(path):
        return None
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None  # the homepage is handled on its own
    last = PAGE_EXT.sub("", segments[-1])
    for ptype, words in ALIASES.items():
        if last in words:
            return ptype
    return None


def decode(resp):
    """Use the charset the server states; if it states none, decode as UTF-8."""
    ctype = resp.headers.get("Content-Type", "").lower()
    if "charset=" in ctype:
        return resp.text
    return resp.content.decode("utf-8", errors="replace")


def parse_html(html, base_url):
    """Return (plain text, list of absolute links) for a page."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        links.append(urljoin(base_url, href).split("#")[0])
    for tag in soup(["script", "style", "noscript", "svg", "template", "iframe"]):
        tag.decompose()
    lines = (re.sub(r"\s+", " ", l).strip() for l in soup.get_text("\n").splitlines())
    text = "\n".join(l for l in lines if l)
    return text[:MAX_TEXT], links


def url_key(url):
    p = urlparse(url)
    return (p.hostname or "").lower().removeprefix("www.") + (p.path.rstrip("/") or "/")


# ---------------------------------------------------------------- fetching

class Fetcher:
    """One per domain. Pauses between requests, checks robots.txt, never visits LinkedIn."""

    def __init__(self, domain):
        self.domain = domain
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.last_request = 0.0
        self.robots = robotparser.RobotFileParser()
        self.robots_note = ""

    def _get(self, url):
        """GET with the 1-2 s pause. Redirects are followed by hand so every hop is checked."""
        if self.last_request:
            wait = random.uniform(*PAUSE) - (time.time() - self.last_request)
            if wait > 0:
                time.sleep(wait)
        for _ in range(MAX_REDIRECTS + 1):
            check_url_safe(url)
            try:
                r = self.session.get(url, timeout=TIMEOUT, allow_redirects=False)
            finally:
                self.last_request = time.time()
            if r.is_redirect and r.headers.get("Location"):
                url = urljoin(r.url, r.headers["Location"])
                continue
            return r
        raise requests.TooManyRedirects(f"more than {MAX_REDIRECTS} redirects")

    def load_robots(self):
        """Read robots.txt (not counted as a page fetch)."""
        url = f"https://{self.domain}/robots.txt"
        try:
            r = self._get(url)
        except requests.RequestException as e:
            self.robots.parse([])
            self.robots_note = f"robots.txt not reachable ({type(e).__name__}); no rules applied"
            return
        if r.status_code in (401, 403):
            self.robots.disallow_all = True
            self.robots_note = f"robots.txt returned {r.status_code}: treated as 'disallow everything'"
        elif r.status_code >= 400:
            self.robots.parse([])
            self.robots_note = f"no robots.txt ({r.status_code}): no rules"
        else:
            self.robots.parse(decode(r).splitlines())
            self.robots_note = "robots.txt read"

    def allowed(self, url):
        return self.robots.can_fetch(USER_AGENT, url)

    def sitemaps_from_robots(self):
        return list(self.robots.site_maps() or [])

    def get(self, url):
        return self._get(url)


# ---------------------------------------------------------------- one domain

class DomainScrape:
    def __init__(self, domain, logger=None, deadline=None):
        """logger: function that takes one line of text (default: print + run_log.txt).
        deadline: time.time() value after which no new fetch starts (web version)."""
        self.domain = domain
        self.log = logger or log
        self.deadline = deadline
        self.timed_out = False
        self.f = Fetcher(domain)
        self.used = {"A": 0, "B": 0}
        self.limit = {"A": STEP_A_MAX, "B": STEP_B_MAX}
        self.seen = set()
        self.pages = {t: None for t in PAGE_TYPES}
        self.attempts = []     # every fetch: url, step, result
        self.link_pool = []    # links found on fetched pages (for the crawl)
        self.base = f"https://{domain}"
        self.home_text = None

    def missing(self):
        return [t for t in PAGE_TYPES if self.pages[t] is None]

    def budget_left(self, step):
        if self.deadline and time.time() + TIMEOUT + PAUSE[1] > self.deadline:
            if not self.timed_out:
                self.timed_out = True
                self.log(f"{self.domain}  ran out of time: no more fetches")
            return False
        return self.used[step] < self.limit[step]

    def try_page(self, ptype, url, step, found_by):
        """Fetch one candidate URL for a page type. Returns True if the page was kept."""
        if not self.budget_left(step) or self.pages[ptype] is not None:
            return False
        if is_linkedin(url) or not same_site(url, self.domain):
            return False
        key = url_key(url)
        if key in self.seen:
            return False
        self.seen.add(key)
        if not self.f.allowed(url):
            self.attempts.append({"url": url, "type": ptype, "step": step, "result": "blocked by robots.txt"})
            self.log(f"{self.domain}  robots.txt blocks {url} (not fetched)")
            return False

        self.used[step] += 1
        record = {"url": url, "type": ptype, "step": step, "found_by": found_by}
        self.attempts.append(record)
        try:
            r = self.f.get(url)
        except requests.RequestException as e:
            record["result"] = f"error: {type(e).__name__}"
            self.log(f"{self.domain}  [{step}{self.used[step]}] {ptype:9} {url} -> {record['result']}")
            return False

        final = r.url
        record["status_code"] = r.status_code
        ctype = r.headers.get("Content-Type", "").lower()
        reason = None
        if r.status_code != 200:
            reason = f"HTTP {r.status_code}"
        elif "html" not in ctype:
            reason = f"not a web page ({ctype or 'no content type'})"
        elif is_linkedin(final) or not same_site(final, self.domain):
            reason = f"redirected off the site to {final}"
        elif ptype != "homepage" and urlparse(final).path.strip("/") == "":
            reason = "redirected to the homepage (page does not exist)"

        if reason:
            record["result"] = reason
            self.log(f"{self.domain}  [{step}{self.used[step]}] {ptype:9} {url} -> {reason}")
            return False

        text, links = parse_html(decode(r), final)
        self.link_pool.extend(links)

        if ptype != "homepage":
            if not text:
                reason = "empty (no readable text; maybe JavaScript-only)"
            elif self.home_text and text == self.home_text:
                reason = "same text as the homepage (page does not really exist)"
            if reason:
                record["result"] = reason
                self.log(f"{self.domain}  [{step}{self.used[step]}] {ptype:9} {url} -> {reason}")
                return False

        record["result"] = "kept"
        self.pages[ptype] = {
            "url": final,
            "requested_url": url,
            "found_by": found_by,
            "step": step,
            "chars": len(text),
            "empty": not text,
            "text": text,
        }
        note = " (EMPTY: maybe JavaScript-only)" if not text else ""
        self.log(f"{self.domain}  [{step}{self.used[step]}] {ptype:9} {final} -> kept, {len(text):,} chars{note}")
        if ptype == "homepage":
            self.home_text = text
            p = urlparse(final)
            self.base = f"{p.scheme}://{p.netloc}"   # e.g. follow a redirect to www.
        return True

    def candidates(self, urls):
        """From a list of URLs, the best candidate per missing type (shortest path wins)."""
        best = {}
        for u in urls:
            if is_linkedin(u) or not same_site(u, self.domain):
                continue
            t = classify(u)
            if t and self.pages[t] is None and url_key(u) not in self.seen:
                if t not in best or len(urlparse(u).path) < len(urlparse(best[t]).path):
                    best[t] = u
        return best

    # ---- Step A
    def step_a(self):
        if not self.try_page("homepage", f"https://{self.domain}/", "A", "homepage"):
            self.try_page("homepage", f"https://www.{self.domain}/", "A", "homepage (www)")
        for t in PAGE_TYPES[1:]:
            self.try_page(t, self.base + COMMON_PATHS[t], "A", "common path")
        home_links = list(self.link_pool) if self.pages["homepage"] else []
        for t, u in self.candidates(home_links).items():
            self.try_page(t, u, "A", "homepage link")

    # ---- Step B
    def sitemap_urls(self):
        """Read the sitemap(s); every sitemap file fetched counts as a Step B fetch."""
        to_read = self.f.sitemaps_from_robots() or [self.base + "/sitemap.xml"]
        to_read = [u for u in to_read if same_site(u, self.domain)]
        found, children_read = [], 0
        while to_read and self.budget_left("B"):
            sm = to_read.pop(0)
            if sm.endswith(".gz") or url_key(sm) in self.seen:
                continue
            self.seen.add(url_key(sm))
            if not self.f.allowed(sm):
                continue
            self.used["B"] += 1
            try:
                r = self.f.get(sm)
            except requests.RequestException as e:
                self.log(f"{self.domain}  [B{self.used['B']}] sitemap   {sm} -> error: {type(e).__name__}")
                continue
            if r.status_code != 200:
                self.log(f"{self.domain}  [B{self.used['B']}] sitemap   {sm} -> HTTP {r.status_code}")
                continue
            body = decode(r)
            locs = re.findall(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^<\s\]]+)", body)
            if "<sitemapindex" in body:
                kids = [u for u in locs if same_site(u, self.domain)]
                take = kids[: max(0, MAX_CHILD_SITEMAPS - children_read)]
                children_read += len(take)
                to_read.extend(take)
                self.log(f"{self.domain}  [B{self.used['B']}] sitemap   {sm} -> index of {len(kids)} sitemaps")
            else:
                pages = [u for u in locs if not FILE_EXT.search(urlparse(u).path)]
                found.extend(pages)
                self.log(f"{self.domain}  [B{self.used['B']}] sitemap   {sm} -> {len(pages)} page URLs")
        return found

    def step_b(self):
        if not self.missing():
            return
        for t, u in self.candidates(self.sitemap_urls()).items():
            self.try_page(t, u, "B", "sitemap")
        if self.missing() and self.budget_left("B"):
            for t, u in self.candidates(self.link_pool).items():
                self.try_page(t, u, "B", "crawl")

    def run(self):
        started = time.time()
        self.f.load_robots()
        self.log(f"{self.domain}  {self.f.robots_note}")
        self.step_a()
        self.step_b()
        kept_text = [p for p in self.pages.values() if p and p["chars"] > 0]
        status = "ok" if kept_text else "unreadable"
        return {
            "domain": self.domain,
            "scraped_at": now(),
            "status": status,
            "seconds": round(time.time() - started, 1),
            "robots": self.f.robots_note,
            "fetches": {"step_a": self.used["A"], "step_b": self.used["B"]},
            "found": [t for t in PAGE_TYPES if self.pages[t]],
            "missing": self.missing(),
            "ran_out_of_time": self.timed_out,
            "pages": self.pages,
            "attempts": self.attempts,
        }


# ---------------------------------------------------------------- main

def save(domain, result):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{domain}.json"
    if out.exists():
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(out), str(HISTORY_DIR / f"scrape_{domain}_{stamp}.json"))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def already_scraped(domain):
    out = OUT_DIR / f"{domain}.json"
    if not out.exists():
        return False
    try:
        return json.loads(out.read_text(encoding="utf-8")).get("status") != "unreadable"
    except (ValueError, OSError):
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Step 1: scrape company websites.")
    ap.add_argument("domains", nargs="*", help="domains to scrape (default: domains.txt)")
    args = ap.parse_args(argv)

    raw = args.domains
    if not raw:
        if not DOMAINS_FILE.exists():
            print("No domains given and no domains.txt found.")
            return 1
        raw = [l.split("#")[0] for l in DOMAINS_FILE.read_text(encoding="utf-8").splitlines()]
        raw = [l for l in raw if l.strip()]

    dnc = load_do_not_contact()
    log(f"=== run started: {len(raw)} domain(s)")
    summary = []
    for item in raw:
        domain = normalize_domain(item)
        if not domain:
            log(f"{item!r}  skipped: not a domain")
            summary.append((item, "skipped: not a domain"))
            continue
        if is_do_not_contact(domain, dnc):
            log(f"{domain}  skipped: on the do-not-contact list (nothing fetched)")
            summary.append((domain, "skipped: do-not-contact"))
            continue
        if already_scraped(domain):
            log(f"{domain}  skipped: already scraped (see output/scrape/{domain}.json)")
            summary.append((domain, "skipped: already scraped"))
            continue
        log(f"{domain}  --- scraping")
        result = DomainScrape(domain).run()
        out = save(domain, result)
        line = (f"{result['status']}, found {', '.join(result['found']) or 'nothing'}"
                f"; missing {', '.join(result['missing']) or 'nothing'}"
                f"; fetches A={result['fetches']['step_a']} B={result['fetches']['step_b']}"
                f"; {result['seconds']} s")
        log(f"{domain}  done: {line}")
        summary.append((domain, line))
    log("=== run finished")
    print("\nSummary")
    for d, s in summary:
        print(f"  {d:28} {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
