"""Hosted explorer adapter; the original loopback CLI remains unchanged."""

import os
from importlib.resources import files
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, request

from proofscope.lexer import MAX_SOURCE_CHARS
from proofscope.parser import parse_proof
from proofscope.semantics import analyze
from proofscope.verifier import verify

origin = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=300_000, TRUSTED_HOSTS=[urlsplit(origin).hostname])


@app.before_request
def same_origin():
    if request.headers.get("Origin") not in (None, origin):
        abort(403)


@app.after_request
def headers(response):
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'self'; style-src 'self'; script-src 'self'; "
                "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
            ),
        }
    )
    return response


@app.get("/")
@app.get("/<asset>")
def assets(asset="index.html"):
    types = {"index.html": "text/html", "app.js": "text/javascript", "style.css": "text/css"}
    if asset not in types:
        abort(404)
    content = files("proofscope").joinpath("web", asset).read_bytes()
    if asset == "index.html":
        content = content.replace(b"Local Python engine", b"Hosted Python engine")
        content = content.replace(
            b"Runs on your machine.<br />No accounts. No external services.",
            b"Proofs are checked on this server.<br />No account required.",
        )
    return app.response_class(content, mimetype=types[asset])


@app.get("/api/examples")
def examples():
    return jsonify(
        [
            {"name": path.name.removesuffix(".proof"), "source": path.read_text("utf-8")}
            for path in sorted(
                files("proofscope").joinpath("examples").iterdir(), key=lambda p: p.name
            )
            if path.name.endswith(".proof")
        ]
    )


@app.post("/api/verify")
def check():
    if request.mimetype != "application/json":
        return jsonify(error="Use application/json."), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("source"), str):
        return jsonify(error="Expected a JSON object with a string 'source'."), 400
    source = payload["source"]
    if len(source) > MAX_SOURCE_CHARS:
        return jsonify(error="Source exceeds 65,536 characters."), 413
    result = verify(source)
    response = result.to_dict()
    if result.syntax_valid:
        proof = parse_proof(source)
        response["semantics"] = analyze(proof.premises, proof.goal)
    return jsonify(response)
