#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import ROOT
from bridge.registry import default_registry_path, load_registry
from bridge.capabilities import capability_evidence_status
from bridge.schema_status import connector_schema_status
from bridge.state import BridgeState
from bridge.tools import BridgeTools, CODEX_LOCAL


def port_running(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def remote_token_status(config: dict[str, Any], *, now: datetime | None = None) -> dict[str, object]:
    raw_value = config.get("remote_token_expires_at")
    if not isinstance(raw_value, str) or not raw_value:
        return {
            "status": "unknown",
            "expires_at": None,
            "refresh_required": True,
            "message": "未找到 remote token 过期时间；外部连接前请重新生成或轮换连接材料。",
        }
    try:
        expires_at = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return {
            "status": "invalid",
            "expires_at": raw_value,
            "refresh_required": True,
            "message": "remote token 过期时间格式无效；外部连接前请重新生成或轮换连接材料。",
        }
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if expires_at <= reference:
        return {
            "status": "expired",
            "expires_at": raw_value,
            "refresh_required": True,
            "message": "remote token 已过期；外部 ChatGPT 连接材料需要先轮换，不能用旧连接继续验证。",
        }
    return {
        "status": "valid",
        "expires_at": raw_value,
        "refresh_required": False,
        "message": "remote token 仍在有效期内；这只说明连接材料未过期，不证明真实 ChatGPT Connector 可用。",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--all", action="store_true", help="List all repos recorded in the local registry")
    args = parser.parse_args()
    if args.all:
        result = status_all(default_registry_path(ROOT))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    state = BridgeState(ROOT)
    config = state.load_config(default={})
    port = int(config.get("port", 8765))
    running = port_running(port)
    pid = state.read_pid() if running else None
    health = BridgeTools(state).bridge_health({}, CODEX_LOCAL) if config else {"ok": False}
    if config:
        config = state.load_config(default={})
    result = {
        "ok": bool(config),
        "bridge": {"running": running, "port": port, "pid": pid},
        "config": config,
        "tool_schema": connector_schema_status(config),
        "remote_token": remote_token_status(config),
        "capability_evidence": capability_evidence_status(config),
        "health": health,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if config else 1


def status_all(registry_path: Path) -> dict[str, object]:
    registry = load_registry(registry_path)
    repos = registry.get("repos", [])
    if isinstance(repos, list):
        current_config_path = registry_path.parent / "config.json"
        if current_config_path.exists():
            current_config = json.loads(current_config_path.read_text(encoding="utf-8"))
            current_root = current_config.get("repo_root")
            known_roots = {
                entry.get("repo_root")
                for entry in repos
                if isinstance(entry, dict) and isinstance(entry.get("repo_root"), str)
            }
            if isinstance(current_root, str) and current_root not in known_roots:
                repos.append(
                    {
                        "repo_root": current_root,
                        "repo_display_name": current_config.get("repo_display_name", Path(current_root).name),
                        "root_alias": current_config.get("root_alias", "current_repo"),
                        "host": current_config.get("host", "127.0.0.1"),
                        "port": current_config.get("port", 8765),
                        "config_path": str(current_config_path),
                        "updated_at": current_config.get("updated_at"),
                    }
                )
    results: list[dict[str, object]] = []
    if isinstance(repos, list):
        for entry in repos:
            if not isinstance(entry, dict):
                continue
            repo_root = entry.get("repo_root")
            if not isinstance(repo_root, str):
                continue
            state = BridgeState(repo_root)
            config = state.load_config(default={})
            port = int(config.get("port", entry.get("port", 8765)))
            running = port_running(port)
            results.append(
                {
                    "repo_root": repo_root,
                    "repo_display_name": config.get("repo_display_name", entry.get("repo_display_name", Path(repo_root).name)),
                    "root_alias": config.get("root_alias", entry.get("root_alias", "current_repo")),
                    "bridge": {"running": running, "port": port, "pid": state.read_pid() if running else None},
                    "config_path": str(state.config_path),
                    "capability_mode": config.get("capability_mode", "unknown"),
                    "capability_evidence": capability_evidence_status(config),
                    "tool_schema": connector_schema_status(config),
                    "remote_token": remote_token_status(config),
                }
            )
    return {"ok": True, "registry_path": str(registry_path), "repos": results}


if __name__ == "__main__":
    raise SystemExit(main())
