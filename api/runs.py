"""GET /api/runs          the newest saved scrapes (no page text, no contact details)
   GET /api/runs?id=...   one saved scrape with its pages and its Hunter contact (if any)
"""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import pipeline  # noqa: E402
import settings  # noqa: E402
import webcommon  # noqa: E402


class handler(webcommon.BaseHandler):
    def do_GET(self):
        if not db.configured():
            return self.send_json(503, {"error": "No database set up (DATABASE_URL missing)."})
        scrape_id = (parse_qs(urlparse(self.path).query).get("id") or [""])[0]
        try:
            with db.connect() as conn:
                db.purge_old_contacts(conn, settings.CONTACT_KEEP_DAYS)
                if not scrape_id:
                    return self.send_json(200, {"runs": db.list_scrapes(conn, settings.RECENT_RUNS)})
                scrape = db.get_scrape(conn, scrape_id)
                if scrape is None:
                    return self.send_json(404, {"error": "That scrape was not found."})
                st = pipeline.state(conn, scrape_id)
                return self.send_json(200, {"scrape": scrape, "contact": st["contact"],
                                            "campaign": st["campaign"], "next": st["next"]})
        except Exception as e:
            return self.send_json(500, {"error": f"Database error ({type(e).__name__})"})
