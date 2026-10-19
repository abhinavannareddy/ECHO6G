"""Small, dependency-light web application for the ECHO-6G decision workspace."""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from importlib.resources import files
from typing import Any

from .native import evaluate_native


MAX_REQUEST_BYTES = 8_192
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/network-illustration.svg": ("network-illustration.svg", "image/svg+xml; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml; charset=utf-8"),
}
INPUT_FIELDS = ("traffic_mbps", "channel_quality", "latency_budget_ms", "reliability_target")
def evaluate_scenario(payload: Any) -> dict[str, Any]:
    """Validate buyer inputs and compare policies for one modeled scenario."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    missing = [field for field in INPUT_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}.")

    values: dict[str, float] = {}
    for field in INPUT_FIELDS:
        raw = payload[field]
        if isinstance(raw, bool):
            raise ValueError(f"{field} must be a number.")
        try:
            values[field] = float(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} must be a number.") from exc
        if not math.isfinite(values[field]):
            raise ValueError(f"{field} must be a finite number.")

    if not 0 <= values["traffic_mbps"] <= 10_000:
        raise ValueError("traffic_mbps must be between 0 and 10000 Mbps")
    if not 0.25 <= values["channel_quality"] <= 1.0:
        raise ValueError("channel_quality must be in [0.25, 1.0]")
    if not 0 < values["latency_budget_ms"] <= 10_000:
        raise ValueError("latency_budget_ms must be greater than 0 and no more than 10000 ms")
    if not 0.01 <= values["reliability_target"] <= 1.0:
        raise ValueError("reliability_target must be between 0.01 and 1")
    return evaluate_native(values)


class DecisionHandler(BaseHTTPRequestHandler):
    # Keep Python's version out of the Server header.
    server_version = "ECHO6G"
    sys_version = ""

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, data: dict[str, Any]) -> None:
        body = json.dumps(data, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok", "service": "echo6g"})
            return
        entry = STATIC_FILES.get(self.path)
        if entry is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        filename, content_type = entry
        data = files("echo6g").joinpath("static", filename).read_bytes()
        self._send(HTTPStatus.OK, data, content_type)

    def do_POST(self) -> None:
        if self.path != "/api/evaluate":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Send a JSON request body."})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 1 or length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be between 1 byte and 8 KB."})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            result = evaluate_scenario(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body is not valid JSON."})
            return
        except ValueError as exc:
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
            return
        except RuntimeError:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": "The model service is not ready. Check that the C++ engine is built, then try again."
            })
            return
        self._send_json(HTTPStatus.OK, result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ECHO-6G network decision workspace")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    server = ThreadingHTTPServer((args.host, args.port), DecisionHandler)
    server.daemon_threads = True
    print(f"ECHO-6G decision workspace listening at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
