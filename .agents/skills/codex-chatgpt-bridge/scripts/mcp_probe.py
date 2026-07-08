#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

from _bootstrap import ROOT
from bridge.mcp_protocol import MCP_PROTOCOL_VERSION
from bridge.state import BridgeState


def post(url: str, payload: dict[str, object], token: str | None) -> dict[str, object] | None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    request.add_header("MCP-Protocol-Version", MCP_PROTOCOL_VERSION)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=5) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true", help="probe the remote token endpoint instead of local bearer endpoint")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    state = BridgeState(ROOT)
    config = state.load_config(default={})
    port = int(config.get("port", 8765))
    if args.remote:
        url = f"http://127.0.0.1:{port}/mcp/remote/{state.read_token('remote')}"
        token = None
    else:
        url = f"http://127.0.0.1:{port}/mcp"
        token = state.read_token("local")

    try:
        init = post(
            url,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "codex-bridge-probe", "version": "0.5.0"},
                },
            },
            token,
        )
        post(url, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, token)
        tools = post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, token)
    except urllib.error.URLError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    result = {
        "ok": True,
        "endpoint": "/mcp/remote/<redacted>" if args.remote else "/mcp",
        "protocol_version": init["result"]["protocolVersion"] if init else None,
        "tools": [tool["name"] for tool in tools["result"]["tools"]] if tools else [],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
