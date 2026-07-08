#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _bootstrap import ROOT
from bridge.state import BridgeState
from bridge.tools import BridgeTools


def extract_json(text: str) -> dict[str, object]:
    match = re.search(r"```(?:codex-bridge-result-json|json)?\s*(\{[\s\S]+?\})\s*```", text)
    raw = match.group(1) if match else text
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("result JSON must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--repo-root", default=str(ROOT), help="要导入结果的项目根目录；默认当前 Skill 所在仓库。")
    args = parser.parse_args()
    if not args.stdin:
        parser.error("only --stdin is supported")
    payload = extract_json(sys.stdin.read())
    result = BridgeTools(BridgeState(Path(args.repo_root).resolve())).import_result(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
