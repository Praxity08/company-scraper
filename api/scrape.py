"""POST /api/scrape  {"domain": "example.com"}

Scrapes ONE domain with exactly the same rules as scraper.py, saves the result in Neon
(if DATABASE_URL is set) and returns it. The page calls this once per domain.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import scraper  # noqa: E402
import webcommon  # noqa: E402

TIME_BUDGET = 90   # seconds of fetching per domain (vercel.json allows the function 120 s)


class handler(webcommon.BaseHandler):
    def do_GET(self):
        self.send_json(405, {"error": "Use POST with {\"domain\": \"example.com\"}."})

    def do_POST(self):
        if not self.from_page():
            return
        data = self.read_json()
        if data is None:
            return self.send_json(400, {"error": "Send a small JSON body like {\"domain\": \"example.com\"}."})
        raw = str(data.get("domain", ""))
        domain = scraper.normalize_domain(raw)
        if not domain:
            return self.send_json(400, {"error": "That is not a domain.", "input": raw[:100]})
        if scraper.is_do_not_contact(domain, scraper.load_do_not_contact()):
            return self.send_json(200, {"domain": domain, "status": "skipped",
                                        "reason": "on the do-not-contact list (nothing fetched)"})

        lines = []

        def logger(msg):
            lines.append(f"{scraper.now()}  {msg}")

        try:
            result = scraper.DomainScrape(domain, logger=logger,
                                          deadline=time.time() + TIME_BUDGET).run()
        except Exception as e:  # never show a raw traceback to the page
            return self.send_json(500, {"domain": domain, "error": f"Scrape failed ({type(e).__name__})",
                                        "log": lines})
        result["log"] = lines

        result["saved"] = False
        result["test_only"] = bool(data.get("test_only"))   # chosen at run start, locked to this scrape
        if db.configured():
            try:
                with db.connect() as conn:
                    result["scrape_id"], saved_at = db.save_scrape(conn, result, result["test_only"])
                result["saved"] = True
                result["saved_at"] = saved_at.isoformat()
            except Exception as e:
                result["save_error"] = f"could not save to the database ({type(e).__name__})"
        else:
            result["save_error"] = "no database set up (DATABASE_URL missing)"
        self.send_json(200, result)
