"""Local test server: serves public/index.html and /api/scrape the way Vercel does.

Run:  .venv/bin/python tools/dev_server.py      then open http://localhost:8780
"""
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from api.scrape import handler  # noqa: E402

PORT = 8780


class DevHandler(handler):
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            body = (ROOT / "public" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/scrape"):
            super().do_GET()
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] == "/api/scrape":
            return super().do_POST()
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    print(f"Serving on http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), DevHandler).serve_forever()
