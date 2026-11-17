"""GET /api/usage   today's counts only (India time): Hunter lookups used and the daily cap."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import contactflow  # noqa: E402
import db  # noqa: E402
import settings  # noqa: E402
import webcommon  # noqa: E402


class handler(webcommon.BaseHandler):
    def do_GET(self):
        if not db.configured():
            return self.send_json(200, {"database": False, "hunter_used": None,
                                        "hunter_cap": settings.HUNTER_DAILY_CAP,
                                        "hunter_ready": bool(settings.hunter_key())})
        try:
            with db.connect() as conn:
                u = contactflow.usage(conn)
        except Exception as e:
            return self.send_json(500, {"error": f"Database error ({type(e).__name__})"})
        self.send_json(200, dict(u, database=True, hunter_ready=bool(settings.hunter_key())))
