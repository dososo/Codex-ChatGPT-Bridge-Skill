#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from _bootstrap import ROOT
from pathlib import Path

from bridge.codex_config import (
    ACTIVE_CONFIG_REL,
    install_codex_mcp_active_config,
    inspect_codex_mcp_config,
    render_codex_mcp_snippet,
    user_codex_config_path,
    write_codex_mcp_snippet,
)
from bridge.state import BridgeState


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Codex MCP config snippet for this Bridge.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--print", action="store_true", dest="print_snippet")
    parser.add_argument("--write-snippet", action="store_true", help="Write .codex/codex-chatgpt-bridge.config.toml")
    parser.add_argument("--write-active", action="store_true", help="Safely install/update the active Codex MCP config.")
    parser.add_argument("--user-active-config", action="store_true", help="Use ~/.codex/config.toml as the active config target.")
    parser.add_argument("--active-config-path", help="Override the active Codex config path; mainly for tests.")
    args = parser.parse_args()

    state = BridgeState(ROOT)
    config = state.init_state()
    port = int(config.get("port", 8765))
    snippet = render_codex_mcp_snippet(port)
    snippet_path = None
    if args.write_snippet:
        snippet_path = write_codex_mcp_snippet(ROOT, port)
    active_target = Path(args.active_config_path).expanduser() if args.active_config_path else (
        user_codex_config_path() if args.user_active_config else ROOT / ACTIVE_CONFIG_REL
    )
    active_install = install_codex_mcp_active_config(
        ROOT,
        port,
        active_config_path=active_target,
        write=args.write_active,
    )
    status = inspect_codex_mcp_config(ROOT, port)

    result = {
        "ok": bool(active_install.get("ok")),
        "snippet": snippet,
        "snippet_path": str(snippet_path.relative_to(ROOT)) if snippet_path else status["snippet_path"],
        "active_config_path": str(active_target),
        "writes_active_config": bool(args.write_active),
        "manual_confirmation_required": bool(active_install.get("required_user_confirmation")),
        "active_install": active_install,
        "status": status,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.print_snippet:
        print(snippet)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
