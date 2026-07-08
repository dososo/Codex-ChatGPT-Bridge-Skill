from __future__ import annotations

import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
import urllib.error
import urllib.request

from bridge.server import BridgeHTTPServer
from bridge.state import BridgeState

from tests.helpers import make_repo


class HttpAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        repo = make_repo("http-auth")
        self.state = BridgeState(repo)
        self.state.init_state()
        self.server = BridgeHTTPServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def request(self, path: str, payload: dict[str, object], *, token: str | None = None, origin: str | None = None) -> urllib.request.Request:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json, text/event-stream")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        if origin:
            request.add_header("Origin", origin)
        return request

    def test_local_bearer_token_required(self) -> None:
        body = json.dumps({"tool": "bridge_health", "arguments": {}}).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/mcp", data=body, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(ctx.exception.code, 404)

        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/mcp", data=body, method="POST")
        request.add_header("Authorization", f"Bearer {self.state.read_token('local')}")
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])

    def test_invalid_auth_is_rate_limited(self) -> None:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        for _ in range(5):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(self.request("/mcp", payload, token="wrong"), timeout=2)
            self.assertEqual(ctx.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.request("/mcp", payload, token="wrong"), timeout=2)
        self.assertEqual(ctx.exception.code, 429)

    def test_remote_token_expiry_returns_404_and_audit_redacts_endpoint(self) -> None:
        config = self.state.load_config()
        config["remote_token_expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.state.save_config(config)
        token = self.state.read_token("remote")
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.request(f"/mcp/remote/{token}", payload), timeout=2)
        self.assertEqual(ctx.exception.code, 404)
        body = ctx.exception.read().decode("utf-8")
        self.assertIn("token_expired", body)

        audit = (self.state.bridge_dir / "logs" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertIn("/mcp/remote/<redacted>", audit)
        self.assertNotIn(token, audit)

    def test_origin_protection_blocks_untrusted_origin(self) -> None:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.request("/mcp", payload, token=self.state.read_token("local"), origin="https://evil.example"), timeout=2)
        self.assertEqual(ctx.exception.code, 403)

        with urllib.request.urlopen(self.request("/mcp", payload, token=self.state.read_token("local"), origin=f"http://127.0.0.1:{self.port}"), timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertIn("result", data)


if __name__ == "__main__":
    unittest.main()
