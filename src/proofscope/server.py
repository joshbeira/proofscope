"""Loopback-only, dependency-free HTTP adapter for the same verification API."""

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit

from .lexer import MAX_SOURCE_CHARS
from .parser import parse_proof
from .semantics import analyze
from .verifier import verify

MAX_REQUEST_BYTES = 300_000


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def allowed(self) -> bool:
        expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in expected and (
            origin is None or origin in {f"http://{host}" for host in expected}
        )

    def send(self, status: int, content: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status: int, value: dict | list) -> None:
        self.send(status, json.dumps(value).encode())

    def do_GET(self) -> None:
        if not self.allowed():
            self.send_json(403, {"error": "Only same-origin loopback requests are allowed."})
            return
        path = urlsplit(self.path).path
        assets = {
            "/": ("index.html", "text/html"),
            "/app.js": ("app.js", "text/javascript"),
            "/style.css": ("style.css", "text/css"),
        }
        if path in assets:
            name, mime = assets[path]
            self.send(200, files("proofscope").joinpath("web", name).read_bytes(), mime)
        elif path == "/api/examples":
            examples = files("proofscope").joinpath("examples")
            self.send_json(
                200,
                [
                    {"name": p.name.removesuffix(".proof"), "source": p.read_text("utf-8")}
                    for p in sorted(examples.iterdir(), key=lambda p: p.name)
                    if p.name.endswith(".proof")
                ],
            )
        else:
            self.send_json(404, {"error": "Not found."})

    def do_POST(self) -> None:
        if not self.allowed():
            self.send_json(403, {"error": "Only same-origin loopback requests are allowed."})
            return
        if self.path != "/api/verify":
            self.send_json(404, {"error": "Not found."})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "Use application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                self.send_json(413, {"error": "Request is empty or too large."})
                return
            self.connection.settimeout(5)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get("source"), str):
                raise ValueError("Expected a JSON object with a string 'source'.")
            source = payload["source"]
            if len(source) > MAX_SOURCE_CHARS:
                self.send_json(413, {"error": "Source exceeds 65,536 characters."})
                return
        except (ValueError, UnicodeError, OSError) as error:
            self.send_json(400, {"error": str(error)})
            return
        result = verify(source)
        response = result.to_dict()
        if result.syntax_valid:
            proof = parse_proof(source)
            response["semantics"] = analyze(proof.premises, proof.goal)
        self.send_json(200, response)


def create_server(port: int = 8765) -> ThreadingHTTPServer:
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port: int = 8765, *, open_browser: bool = False) -> None:
    with create_server(port) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"ProofScope explorer: {url}\nPress Ctrl+C to stop.", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
