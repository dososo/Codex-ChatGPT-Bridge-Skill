#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ROOT
from bridge.state import BridgeState
from bridge.tools import BridgeTools, CODEX_LOCAL


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id")
    parser.add_argument("--repo-root", default=str(ROOT), help="要读取结果的项目根目录；默认当前 Skill 所在仓库。")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    arguments = {"task_id": args.task_id} if args.task_id else {}
    result = BridgeTools(BridgeState(Path(args.repo_root).resolve())).call_tool("bridge_pull_result", arguments, CODEX_LOCAL)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["result_markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
