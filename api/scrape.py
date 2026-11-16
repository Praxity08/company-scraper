"""Vercel function: POST /api/scrape with {"domain": "example.com"}.

Scrapes ONE domain with exactly the same rules as scraper.py and returns the result
as JSON. Nothing is saved on the server. The web page calls this once per domain.
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scraper  # noqa: E402

TIME_BUDGET = 90   # seconds of fetching per domain (vercel.json allows the function 120 s)
MAX_BODY = 2048    # bytes


class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(405, {"error": "Use POST with {\"domain\": \"example.com\"}."})

    def do_POST(self):
        # Simple guard: only the page's own JavaScript sends this header.
        if self.headers.get("X-Requested-With") != "fetch":
            return self._send(403, {"error": "Missing X-Requested-With header."})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            return self._send(400, {"error": "Send a small JSON body like {\"domain\": \"example.com\"}."})
        try:
            data = json.loads(self.rfile.read(length))
            raw = str(data.get("domain", "")) if isinstance(data, dict) else ""
        except ValueError:
            raw = ""

        domain = scraper.normalize_domain(raw)
        if not domain:
            return self._send(400, {"error": "That is not a domain.", "input": raw[:100]})
        if scraper.is_do_not_contact(domain, scraper.load_do_not_contact()):
            return self._send(200, {"domain": domain, "status": "skipped",
                                    "reason": "on the do-not-contact list (nothing fetched)"})

        lines = []

        def logger(msg):
            lines.append(f"{scraper.now()}  {msg}")

        try:
            result = scraper.DomainScrape(domain, logger=logger,
                                          deadline=time.time() + TIME_BUDGET).run()
        except Exception as e:  # never show a raw traceback to the page
            return self._send(500, {"domain": domain, "error": f"Scrape failed ({type(e).__name__})",
                                    "log": lines})
        result["log"] = lines
        self._send(200, result)

    def log_message(self, *args):
        pass  # keep request lines (with visitor addresses) out of the logs
