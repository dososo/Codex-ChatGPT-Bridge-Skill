from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from bridge.mcp_protocol import MCP_PROTOCOL_VERSION
from bridge.server import BridgeHTTPServer
from bridge.state import BridgeState

from tests.helpers import make_repo


class McpProtocolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo("mcp-protocol")
        self.state = BridgeState(self.repo)
        self.state.init_state()
        self.server = BridgeHTTPServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def post(self, payload: dict[str, object], *, path: str = "/mcp", token_kind: str = "local") -> tuple[int, dict[str, object] | None]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, method="POST")
        request.add_header("Accept", "application/json, text/event-stream")
        request.add_header("Content-Type", "application/json")
        request.add_header("Authorization", f"Bearer {self.state.read_token(token_kind)}")
        with urllib.request.urlopen(request, timeout=3) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else None

    def test_initialize_and_local_tools_list(self) -> None:
        _, init = self.post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
            }
        )
        assert init is not None
        self.assertEqual(init["result"]["capabilities"], {"tools": {"listChanged": False}})
        self.assertIn("instructions", init["result"])

        _, listed = self.post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert listed is not None
        tool_names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertIn("bridge_push_task", tool_names)
        self.assertNotIn("bridge_send_result", tool_names)

    def test_remote_tools_call_flow(self) -> None:
        _, pushed = self.post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "bridge_push_task",
                    "arguments": {"title": "mcp task", "goal": "verify MCP call", "context": {"allowed_files": ["src/app.py"]}},
                },
            }
        )
        assert pushed is not None
        task_id = pushed["result"]["structuredContent"]["task_id"]

        remote_path = f"/mcp/remote/{self.state.read_token('remote')}"
        _, listed = self.post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, path=remote_path, token_kind="remote")
        assert listed is not None
        remote_tool_names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertIn("bridge_fetch_task_packet", remote_tool_names)
        self.assertIn("bridge_send_result", remote_tool_names)
        self.assertNotIn("bridge_push_task", remote_tool_names)

        _, fetched = self.post({"jsonrpc": "2.0", "id": 30, "method": "tools/call", "params": {"name": "bridge_fetch_task_packet", "arguments": {}}}, path=remote_path, token_kind="remote")
        assert fetched is not None
        fetched_content = fetched["result"]["structuredContent"]
        self.assertEqual(fetched_content["task_id"], task_id)
        self.assertIsNone(fetched_content["claim_id"])
        self.assertEqual(self.state.load_task(task_id)["status"], "queued")

        _, pulled = self.post({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "bridge_pull_task", "arguments": {}}}, path=remote_path, token_kind="remote")
        assert pulled is not None
        claim_id = pulled["result"]["structuredContent"]["claim_id"]
        self.assertEqual(pulled["result"]["structuredContent"]["task_id"], task_id)

        _, sent = self.post(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "bridge_send_result", "arguments": {"task_id": task_id, "claim_id": claim_id, "summary": "mcp result ok"}},
            },
            path=remote_path,
            token_kind="remote",
        )
        assert sent is not None
        self.assertEqual(sent["result"]["structuredContent"]["status"], "result_saved")

    def test_initialized_notification_returns_accepted(self) -> None:
        status, payload = self.post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        self.assertEqual(status, 202)
        self.assertIsNone(payload)

    def test_unknown_method_returns_jsonrpc_error(self) -> None:
        _, payload = self.post({"jsonrpc": "2.0", "id": 99, "method": "unknown/method", "params": {}})
        assert payload is not None
        self.assertEqual(payload["error"]["code"], -32601)

    def test_get_mcp_returns_405_when_sse_not_supported(self) -> None:
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/mcp", method="GET")
        request.add_header("Accept", "text/event-stream")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(ctx.exception.code, 405)

    def test_mcp_jsonrpc_requires_streamable_http_accept_header(self) -> None:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/mcp", data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        request.add_header("Authorization", f"Bearer {self.state.read_token('local')}")

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(ctx.exception.code, 406)
        error = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(error["error"]["code"], "invalid_accept_header")

    def test_invalid_mcp_protocol_version_header_returns_400(self) -> None:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/mcp", data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json, text/event-stream")
        request.add_header("MCP-Protocol-Version", "2099-01-01")
        request.add_header("Authorization", f"Bearer {self.state.read_token('local')}")

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(ctx.exception.code, 400)
        error = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(error["error"]["code"], "unsupported_mcp_protocol_version")

    def test_initialize_falls_back_from_unsupported_requested_version(self) -> None:
        _, init = self.post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2099-01-01", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
            }
        )
        assert init is not None
        self.assertEqual(init["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)


if __name__ == "__main__":
    unittest.main()
