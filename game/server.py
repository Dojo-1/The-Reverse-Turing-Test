"""Local-only HTTP relay for a playable Reverse Turing Game.

Usage: python -m game.server [--port 8765]
The printed URLs are participant credentials. Treat them as secrets.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from .engine import Game, RuleError


STATIC = Path(__file__).resolve().parent / "web"
ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
MAX_BODY = 10000


def handler_factory(game: Game):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ReverseTuringRelay/0.1"

        def _headers(self, status, content_type, size):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; img-src 'self'; script-src 'self'; "
                "style-src 'self'; connect-src 'self'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'",
            )
            self.end_headers()

        def _send(self, status, payload):
            blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(blob))
            self.wfile.write(blob)

        def _auth(self):
            header = self.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                raise RuleError("Missing participant credential")
            return game.identify(header.removeprefix("Bearer ").strip())

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ROUTES:
                file_name, content_type = ROUTES[path]
                blob = (STATIC / file_name).read_bytes()
                self._headers(200, content_type, len(blob))
                self.wfile.write(blob)
                return
            if path == "/api/health":
                self._send(200, {"status": "ok", "service": "reverse-turing-relay"})
                return
            if path not in ("/api/view", "/api/export"):
                self._send(404, {"error": "Unknown route"})
                return
            try:
                role = self._auth()
                if path == "/api/export":
                    if role != "controller":
                        raise RuleError("Only the controller can export a trial")
                    self._send(200, game.export())
                else:
                    self._send(200, game.view(role))
            except RuleError as error:
                self._send(403, {"error": str(error)})

        def do_POST(self):
            path = urlsplit(self.path).path
            if path != "/api/act":
                self._send(404, {"error": "Unknown route"})
                return
            try:
                role = self._auth()
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError as error:
                    raise RuleError("Invalid body length") from error
                if length < 1 or length > MAX_BODY:
                    raise RuleError("Request body exceeds limit")
                try:
                    data = json.loads(self.rfile.read(length))
                except (UnicodeError, json.JSONDecodeError) as error:
                    raise RuleError("Request must be valid JSON") from error
                if not isinstance(data, dict):
                    raise RuleError("Expected a JSON object")
                game.act(role, data.get("action"), data)
                self._send(200, {"ok": True})
            except RuleError as error:
                self._send(400, {"error": str(error)})

        def log_message(self, format, *args):
            # Never log bearer tokens: credentials travel in the header,
            # not in the request URL. Standard logging emits only method/path.
            super().log_message(format, *args)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reverse Turing local game relay")
    parser.add_argument("--port", type=int, default=8765, help="local listening port")
    args = parser.parse_args(argv)
    game = Game()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_factory(game))
    host, port = server.server_address
    print("\nREVERSE TURING GAME — LOCAL RELAY", flush=True)
    print("The controller owns these links. SHARE ONLY the intended link with each player.\n", flush=True)
    for role, token in game.tokens.items():
        print(f"{role:>14}: http://{host}:{port}/#token={token}", flush=True)
    print("\nTokens are credentials. Do not publish the terminal output.", flush=True)
    print("Ctrl+C stops the session. Export the controller record before stopping.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
