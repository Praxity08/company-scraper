"""Local test server: serves public/index.html and the api/ functions the way Vercel does.

Reads keys from .env. Run:  .venv/bin/python tools/dev_server.py   then open http://localhost:8780
"""
import importlib
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import webcommon  # noqa: E402  (also loads .env)

PORT = 8780
ROUTES = {f"/api/{name}": importlib.import_module(f"api.{name}").handler
          for name in ("scrape", "contact", "runs", "usage")}


class DevHandler(webcommon.BaseHandler):
    def _route(self, method):
        path = urlparse(self.path).path
        cls = ROUTES.get(path)
        if cls and hasattr(cls, method):
            return getattr(cls, method)(self)
        if method == "do_GET" and path in ("/", "/index.html"):
            body = (ROOT / "public" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        self.send_json(405 if cls else 404, {"error": "not found" if not cls else "method not allowed"})

    def do_GET(self):
        self._route("do_GET")

    def do_POST(self):
        self._route("do_POST")


if __name__ == "__main__":
    print(f"Serving on http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), DevHandler).serve_forever()
