#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime, timedelta, timezone

from _bootstrap import ROOT
from bridge.redaction import mask_secret
from bridge.state import BridgeState


def rotate_tokens(state: BridgeState, *, rotate_local: bool, rotate_remote: bool) -> dict[str, object]:
    config = state.init_state()
    changed: list[str] = []
    if rotate_local:
        state.write_token("local", secrets.token_urlsafe(32))
        changed.append("local")
    if rotate_remote:
        state.write_token("remote", secrets.token_urlsafe(32))
        config["remote_token_expires_at"] = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        changed.append("remote")
    state.save_config(config)
    return {
        "ok": True,
        "rotated": changed,
        "local_token_tail": mask_secret(state.read_token("local")),
        "remote_token_tail": mask_secret(state.read_token("remote")),
        "next_actions": ["更新 CODEX_BRIDGE_LOCAL_TOKEN", "如远端 token 轮换，请更新 ChatGPT Connector URL 或 Secure Tunnel 配置"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", action="store_true")
    group.add_argument("--remote", action="store_true")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()

    state = BridgeState(ROOT)
    result = rotate_tokens(state, rotate_local=args.local or args.all, rotate_remote=args.remote or args.all)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
