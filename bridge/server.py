from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .audit import append_http_audit
from .errors import BridgeError
from .mcp_protocol import MCP_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS, handle_mcp_message, is_jsonrpc_message
from .state import BridgeState
from .tools import CHATGPT_REMOTE, CODEX_LOCAL, BridgeTools

AUTH_FAILURE_LIMIT = 5
AUTH_FAILURE_WINDOW_SECONDS = 60


class BridgeHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "CodexChatGPTBridge/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health-local" and self.client_address[0] in {"127.0.0.1", "::1"}:
            tools = BridgeTools(self.server.bridge_state)  # type: ignore[attr-defined]
            self._send_json(200, {"ok": True, "result": tools.bridge_health({}, CODEX_LOCAL)})
            return
        if parsed.path == "/mcp" or parsed.path.startswith("/mcp/remote/"):
            self._send_json(405, {"ok": False, "error": {"code": "sse_not_supported", "message": "SSE GET stream is not supported by this Bridge"}})
            return
        self._send_json(404, {"ok": False, "error": {"code": "not_found", "message": "not found"}})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        started = time.monotonic()
        endpoint = _redact_endpoint(parsed.path)
        role: str | None = None
        mcp_method: str | None = None
        status_code = 200
        auth_failure_count: int | None = None
        try:
            self._validate_origin(parsed.path)
            role = self._resolve_role(parsed.path)
            payload = self._read_json()
            mcp_method = payload.get("method") if isinstance(payload.get("method"), str) else payload.get("tool") if isinstance(payload.get("tool"), str) else None
            if is_jsonrpc_message(payload):
                self._validate_mcp_http_headers()
                response = handle_mcp_message(BridgeTools(self.server.bridge_state), payload, role)  # type: ignore[attr-defined]
                status_code = response.status
                if response.body is None:
                    self._send_empty(response.status, response.headers)
                else:
                    self._send_json(response.status, response.body, response.headers)
                append_http_audit(self.server.bridge_state.bridge_dir, endpoint=endpoint, role=role, mcp_method=mcp_method, status="ok", status_code=status_code, duration_ms=_duration_ms(started), auth_failure_count=auth_failure_count)  # type: ignore[attr-defined]
                return
            tool = payload.get("tool") or payload.get("name")
            arguments = payload.get("arguments", {})
            if not isinstance(tool, str):
                raise BridgeError("invalid_request", "tool must be provided")
            if not isinstance(arguments, dict):
                raise BridgeError("invalid_request", "arguments must be an object")
            tools = BridgeTools(self.server.bridge_state)  # type: ignore[attr-defined]
            result = tools.call_tool(tool, arguments, role)
            self._send_json(200, {"ok": True, "result": result})
            append_http_audit(self.server.bridge_state.bridge_dir, endpoint=endpoint, role=role, mcp_method=mcp_method, status="ok", status_code=200, duration_ms=_duration_ms(started), auth_failure_count=auth_failure_count)  # type: ignore[attr-defined]
        except BridgeError as exc:
            status = 404 if exc.code in {"invalid_token", "token_expired", "not_found"} else exc.http_status
            status_code = status
            auth_failure_count = getattr(self, "_auth_failure_count", None)
            append_http_audit(self.server.bridge_state.bridge_dir, endpoint=endpoint, role=role, mcp_method=mcp_method, status="error", status_code=status_code, duration_ms=_duration_ms(started), error_code=exc.code, auth_failure_count=auth_failure_count)  # type: ignore[attr-defined]
            self._send_json(status, {"ok": False, "error": exc.to_dict()})
        except json.JSONDecodeError:
            status_code = 400
            append_http_audit(self.server.bridge_state.bridge_dir, endpoint=endpoint, role=role, mcp_method=mcp_method, status="error", status_code=status_code, duration_ms=_duration_ms(started), error_code="invalid_json", auth_failure_count=auth_failure_count)  # type: ignore[attr-defined]
            self._send_json(status_code, {"ok": False, "error": {"code": "invalid_json", "message": "request body must be JSON"}})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _resolve_role(self, path: str) -> str:
        state: BridgeState = self.server.bridge_state  # type: ignore[attr-defined]
        if path == "/mcp":
            auth = self.headers.get("Authorization", "")
            expected = f"Bearer {state.read_token('local')}"
            if auth != expected:
                self._record_auth_failure("local")
                raise BridgeError("invalid_token", "invalid token", 404)
            return CODEX_LOCAL
        prefix = "/mcp/remote/"
        if path.startswith(prefix):
            supplied = path[len(prefix) :]
            if supplied != state.read_token("remote"):
                self._record_auth_failure("remote")
                raise BridgeError("invalid_token", "invalid token", 404)
            if _remote_token_expired(state):
                self._record_auth_failure("remote")
                raise BridgeError("token_expired", "token expired", 404)
            return CHATGPT_REMOTE
        raise BridgeError("not_found", "not found", 404)

    def _record_auth_failure(self, bucket: str) -> None:
        key = f"{self.client_address[0]}:{bucket}"
        now = time.monotonic()
        failures = self.server.auth_failures.setdefault(key, [])  # type: ignore[attr-defined]
        failures[:] = [item for item in failures if now - item < AUTH_FAILURE_WINDOW_SECONDS]
        failures.append(now)
        self._auth_failure_count = len(failures)
        if len(failures) > AUTH_FAILURE_LIMIT:
            raise BridgeError("auth_rate_limited", "too many failed authentication attempts", 429)

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise BridgeError("invalid_request", "request body must be an object")
        return data

    def _validate_origin(self, path: str) -> None:
        origin = self.headers.get("Origin")
        if not origin:
            return
        config = self.server.bridge_state.load_config(default={})  # type: ignore[attr-defined]
        allowed = set(config.get("allowed_origins", [])) if isinstance(config.get("allowed_origins", []), list) else set()
        allowed.update({"http://127.0.0.1", "http://localhost"})
        normalized = origin.rstrip("/")
        local_origin = normalized.startswith("http://127.0.0.1:") or normalized.startswith("http://localhost:")
        if normalized not in allowed and not local_origin:
            raise BridgeError("origin_denied", "Origin is not allowed", 403)

    def _validate_mcp_http_headers(self) -> None:
        accept = self.headers.get("Accept", "")
        accepted_types = {part.split(";", 1)[0].strip().lower() for part in accept.split(",")}
        if "application/json" not in accepted_types or "text/event-stream" not in accepted_types:
            raise BridgeError("invalid_accept_header", "MCP JSON-RPC requests must accept application/json and text/event-stream", 406)

        version = self.headers.get("MCP-Protocol-Version")
        if version and version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise BridgeError("unsupported_mcp_protocol_version", f"unsupported MCP protocol version: {version}", 400)

    def _send_json(self, status: int, payload: dict[str, object], headers: dict[str, str] | None = None) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        headers = headers or {"Content-Type": "application/json; charset=utf-8"}
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if "MCP-Protocol-Version" not in headers and (self.path == "/mcp" or self.path.startswith("/mcp/remote/")):
            headers["MCP-Protocol-Version"] = MCP_PROTOCOL_VERSION
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_empty(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()


class BridgeHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], state: BridgeState):
        self.bridge_state = state
        self.auth_failures: dict[str, list[float]] = {}
        super().__init__(address, BridgeHTTPRequestHandler)


def serve(repo_root: Path | str, host: str = "127.0.0.1", port: int = 8765) -> None:
    state = BridgeState(repo_root)
    state.init_state(port=port)
    server = BridgeHTTPServer((host, port), state)
    server.serve_forever()


def _remote_token_expired(state: BridgeState) -> bool:
    raw = state.load_config(default={}).get("remote_token_expires_at")
    if not isinstance(raw, str):
        return False
    try:
        expires_at = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _redact_endpoint(path: str) -> str:
    if path.startswith("/mcp/remote/"):
        return "/mcp/remote/<redacted>"
    return path


def _duration_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
