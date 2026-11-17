"""POST /api/step  {"scrape_id": "...", "step": "picture" | "check" | "approve" | "state"}

Runs ONE pipeline step for a saved scrape and returns the updated campaign record.
(Pain points, email draft and send are added here once their rules are approved.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import gemini  # noqa: E402
import pipeline  # noqa: E402
import settings  # noqa: E402
import webcommon  # noqa: E402

STEPS = {
    "picture": pipeline.run_picture,
    "check": pipeline.run_check,
    "approve": pipeline.approve_flag,
    "state": lambda conn, sid: (200, pipeline.state(conn, sid)),
}


class handler(webcommon.BaseHandler):
    def do_GET(self):
        self.send_json(405, {"error": "Use POST with {\"scrape_id\": \"...\", \"step\": \"...\"}."})

    def do_POST(self):
        if not self.from_page():
            return
        data = self.read_json()
        if data is None or not db.as_uuid(data.get("scrape_id")) or data.get("step") not in STEPS:
            return self.send_json(400, {"error": "Send {\"scrape_id\": \"...\", \"step\": one of "
                                                 + ", ".join(STEPS) + "}."})
        if not db.configured():
            return self.send_json(503, {"error": "No database set up (DATABASE_URL missing)."})
        try:
            with db.connect() as conn:
                code, payload = STEPS[data["step"]](conn, data["scrape_id"])
        except Exception as e:
            msg = f"Step failed ({type(e).__name__})"
            for key in (settings.gemini_key(), settings.serper_key()):
                msg = gemini.scrub(msg, key)
            return self.send_json(500, {"error": msg})
        self.send_json(code, payload)
