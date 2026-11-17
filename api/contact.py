"""POST /api/contact  {"scrape_id": "..."}

Runs ONE Hunter lookup for a saved scrape (at most one per scrape, at most
settings.HUNTER_DAILY_CAP per day for everyone). Nobody is ever emailed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import contactflow  # noqa: E402
import db  # noqa: E402
import hunter  # noqa: E402
import settings  # noqa: E402
import webcommon  # noqa: E402


class handler(webcommon.BaseHandler):
    def do_GET(self):
        self.send_json(405, {"error": "Use POST with {\"scrape_id\": \"...\"}."})

    def do_POST(self):
        if not self.from_page():
            return
        data = self.read_json()
        if data is None or not db.as_uuid(data.get("scrape_id")):
            return self.send_json(400, {"error": "Send {\"scrape_id\": \"...\"} for a saved scrape."})
        if not db.configured():
            return self.send_json(503, {"error": "No database set up (DATABASE_URL missing)."})
        key = settings.hunter_key()
        try:
            with db.connect() as conn:
                code, payload = contactflow.lookup(conn, data["scrape_id"], key)
        except Exception as e:
            return self.send_json(500, {"error": hunter.scrub(f"Lookup failed ({type(e).__name__})", key)})
        self.send_json(code, payload)
