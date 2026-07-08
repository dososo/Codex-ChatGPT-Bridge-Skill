#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket

from _bootstrap import ROOT
from bridge.codex_config import inspect_codex_mcp_config, write_codex_mcp_snippet
from bridge.registry import default_registry_path, registered_ports
from bridge.redaction import mask_secret
from bridge.state import BridgeState


def find_port(start: int = 8765, reserved_ports: set[int] | None = None) -> int:
    reserved_ports = reserved_ports or set()
    for port in range(start, start + 100):
        if port in reserved_ports:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("no available local port in range 8765-8864")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    state = BridgeState(ROOT)
    reserved = registered_ports(default_registry_path(ROOT), exclude_repo_root=ROOT)
    config = state.init_state(port=find_port(reserved_ports=reserved))
    env_path = ROOT / ".env.codex-bridge.local"
    env_path.write_text(f'export CODEX_BRIDGE_LOCAL_TOKEN="{state.read_token("local")}"\n', encoding="utf-8")
    snippet_path = write_codex_mcp_snippet(ROOT, int(config["port"]))
    codex_mcp = inspect_codex_mcp_config(ROOT, int(config["port"]))

    result = {
        "ok": True,
        "config_path": ".ai-bridge/config.json",
        "env_file": ".env.codex-bridge.local",
        "codex_mcp_config_snippet": str(snippet_path.relative_to(ROOT)),
        "codex_mcp": codex_mcp,
        "local_endpoint": f"http://127.0.0.1:{config['port']}/mcp",
        "remote_endpoint_template": f"https://<tunnel-domain>/mcp/remote/{mask_secret(state.read_token('remote'))}",
        "next_actions": ["review_codex_mcp_config_snippet", "start_bridge", "create_connector", "run_read_smoke", "run_write_smoke"],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Codex ChatGPT Bridge setup complete.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
