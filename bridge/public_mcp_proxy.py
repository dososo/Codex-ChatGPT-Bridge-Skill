from __future__ import annotations

import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .state import BridgeState

MAX_PROXY_BODY_BYTES = 1024 * 1024
STREAMABLE_ACCEPT = "application/json, text/event-stream"


class PublicMCPProxyHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        *,
        repo_root: Path | str,
        upstream_host: str,
        upstream_port: int,
    ) -> None:
        self.bridge_state = BridgeState(repo_root)
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.upstream_path = "/mcp/remote/" + self.bridge_state.read_token("remote")
        super().__init__(address, PublicMCPProxyHTTPRequestHandler)


class PublicMCPProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "CodexBridgePublicMCPProxy/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health-local" and self.client_address[0] in {"127.0.0.1", "::1"}:
            self._send_json(200, {"ok": True, "public_path": "/mcp", "upstream": "/mcp/remote/<redacted>"})
            return
        if parsed.path == "/mcp":
            self._send_json(
                405,
                {
                    "ok": False,
                    "error": {
                        "code": "streamable_http_post_required",
                        "message": "temporary public MCP proxy supports Streamable HTTP POST only",
                    },
                },
            )
            return
        self._send_json(404, {"ok": False, "error": {"code": "not_found", "message": "not found"}})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/mcp":
            self._send_json(404, {"ok": False, "error": {"code": "not_found", "message": "not found"}})
            return

        try:
            body = self._read_body()
        except ValueError as exc:
            self._send_json(413, {"ok": False, "error": {"code": "payload_too_large", "message": str(exc)}})
            return

        headers = self._forward_headers()
        try:
            conn = http.client.HTTPConnection(self.server.upstream_host, self.server.upstream_port, timeout=10)  # type: ignore[attr-defined]
            conn.request("POST", self.server.upstream_path, body=body, headers=headers)  # type: ignore[attr-defined]
            response = conn.getresponse()
            response_body = response.read()
        except OSError as exc:
            self._send_json(502, {"ok": False, "error": {"code": "upstream_unavailable", "message": str(exc)}})
            return
        finally:
            try:
                conn.close()  # type: ignore[possibly-undefined]
            except Exception:
                pass

        self.send_response(response.status)
        for name, value in response.getheaders():
            lower_name = name.lower()
            if lower_name in {"connection", "content-length", "date", "server", "transfer-encoding"}:
                continue
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_PROXY_BODY_BYTES:
            raise ValueError("request body exceeds temporary proxy limit")
        return self.rfile.read(length)

    def _forward_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": self.headers.get("Content-Type") or "application/json",
            "Accept": _normalize_accept_header(self.headers.get("Accept", "")),
        }
        protocol_version = self.headers.get("MCP-Protocol-Version")
        if protocol_version:
            headers["MCP-Protocol-Version"] = protocol_version
        return headers

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _normalize_accept_header(raw: str) -> str:
    accepted = {part.split(";", 1)[0].strip().lower() for part in raw.split(",") if part.strip()}
    if "application/json" in accepted and "text/event-stream" in accepted:
        return raw
    return STREAMABLE_ACCEPT


def serve_public_mcp_proxy(
    repo_root: Path | str,
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    upstream_host: str = "127.0.0.1",
    upstream_port: int = 8765,
) -> None:
    server = PublicMCPProxyHTTPServer(
        (host, port),
        repo_root=repo_root,
        upstream_host=upstream_host,
        upstream_port=upstream_port,
    )
    server.serve_forever()
