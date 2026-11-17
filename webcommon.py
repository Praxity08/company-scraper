"""Shared helpers for the Vercel functions in api/ (kept outside api/ so it is not a function itself)."""
import json
from http.server import BaseHTTPRequestHandler

import settings

settings.load_env()   # local .env only; on Vercel the settings are already in the environment

MAX_BODY = 2048


class BaseHandler(BaseHTTPRequestHandler):
    def send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def from_page(self):
        """Only the page's own JavaScript sends this header (needed on every POST)."""
        if self.headers.get("X-Requested-With") != "fetch":
            self.send_json(403, {"error": "Missing X-Requested-With header."})
            return False
        return True

    def read_json(self):
        """The request body as a dict, or None if it is missing, too big or not JSON."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY:
            return None
        try:
            data = json.loads(self.rfile.read(length))
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def log_message(self, *args):
        pass  # keep request lines (with visitor addresses) out of the logs
