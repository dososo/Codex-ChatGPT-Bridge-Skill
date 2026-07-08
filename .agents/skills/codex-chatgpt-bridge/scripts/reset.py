#!/usr/bin/env python3
from __future__ import annotations

import json

from _bootstrap import ROOT
from bridge.capabilities import UNKNOWN
from bridge.state import BridgeState


def main() -> int:
    state = BridgeState(ROOT)
    config = state.init_state()
    config["capability_mode"] = UNKNOWN
    config.pop("capability_evidence", None)
    config.pop("last_capability_check_at", None)
    state.save_config(config)
    print(json.dumps({"ok": True, "reset": ["capability_mode", "capability_evidence", "last_capability_check_at"], "note": "未删除 .ai-bridge；卸载请按 docs/uninstall.zh-CN.md 手动逐项处理。"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
