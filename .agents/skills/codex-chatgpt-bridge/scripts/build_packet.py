#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from _bootstrap import ROOT
from bridge.state import BridgeState
from bridge.tools import BridgeTools


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id")
    parser.add_argument("--title", default="右侧 ChatGPT 审查任务")
    parser.add_argument("--goal", default="请审查当前上下文并给出风险、测试缺口和下一步建议")
    parser.add_argument("--allowed-file", action="append", default=[])
    args = parser.parse_args()
    payload: dict[str, object]
    if args.task_id:
        payload = {"task_id": args.task_id}
    else:
        payload = {"title": args.title, "goal": args.goal, "mode": "review", "context": {"allowed_files": args.allowed_file}}
    result = BridgeTools(BridgeState(ROOT)).build_packet(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
