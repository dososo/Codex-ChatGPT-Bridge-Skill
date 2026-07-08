#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import sys

from _bootstrap import ROOT
from bridge.capabilities import capability_evidence_status
from bridge.codex_config import inspect_codex_mcp_config
from bridge.schema_status import connector_schema_status
from bridge.state import BridgeState


def port_running(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    state = BridgeState(ROOT)
    config = state.load_config(default={})
    port = int(config.get("port", 8765))
    required_actions: list[str] = []
    if not config:
        required_actions.append("run_setup")
    if not port_running(port):
        required_actions.append("start_bridge")
    if config.get("capability_mode", "unknown") == "unknown":
        required_actions.extend(["create_connector", "run_read_smoke"])
    capability_evidence = capability_evidence_status(config)
    if capability_evidence.get("status") == "unverified":
        required_actions.append("record_real_connector_smoke_evidence")
    tool_schema = connector_schema_status(config)
    if config and tool_schema.get("refresh_required"):
        required_actions.append("refresh_connector_tools")
    codex_mcp = inspect_codex_mcp_config(ROOT, port)
    if config:
        required_actions.extend(str(action) for action in codex_mcp.get("required_actions", []))

    result = {
        "ok": not required_actions,
        "os": platform.system(),
        "python": sys.version.split()[0],
        "repo_root": str(ROOT),
        "is_git_repo": (ROOT / ".git").is_dir(),
        "skill_path_ok": (ROOT / ".agents/skills/codex-chatgpt-bridge/SKILL.md").exists(),
        "codex_config_exists": (ROOT / ".codex/config.toml").exists(),
        "codex_mcp": codex_mcp,
        "bridge": {"running": port_running(port), "port": port},
        "tunnel": {
            "provider": None,
            "available": [name for name in ["secure-mcp-tunnel"] if shutil.which(name)],
        },
        "sensitive_files_present": [
            name
            for name in [".env", ".env.local", "id_rsa", "id_ed25519"]
            if (ROOT / name).exists()
        ],
        "capability_mode": config.get("capability_mode", "unknown"),
        "capability_evidence": capability_evidence,
        "tool_schema": tool_schema,
        "required_actions": required_actions,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
