#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ROOT
from bridge.capabilities import capability_evidence_status, classify, real_smoke_status_from_evidence
from bridge.errors import BridgeError
from bridge.state import BridgeState
from bridge.tools import BridgeTools, CHATGPT_REMOTE, CODEX_LOCAL


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--evidence-file",
        help="真实 ChatGPT Connector smoke 证据 JSON；只有其中 real_read_smoke / real_write_smoke 为 verified 时才更新 capability_mode。",
    )
    args = parser.parse_args()
    if not args.read and not args.write:
        parser.error("choose --read or --write")

    state = BridgeState(ROOT)
    tools = BridgeTools(state)
    state.init_state()
    read_ok = False
    write_ok = False
    error = None
    try:
        if args.read:
            tools.call_tool("bridge_list_allowed_roots_redacted", {}, CHATGPT_REMOTE)
            read_ok = True
        if args.write:
            created = tools.call_tool(
                "bridge_push_task",
                {"title": "写回能力测试", "goal": "验证 bridge_send_result 能写回", "mode": "smoke", "context": {"allowed_files": []}},
                CODEX_LOCAL,
            )
            pulled = tools.call_tool("bridge_pull_task", {}, CHATGPT_REMOTE)
            tools.call_tool(
                "bridge_send_result",
                {
                    "task_id": pulled["task_id"],
                    "claim_id": pulled["claim_id"],
                    "summary": "write smoke ok",
                    "result_type": "review",
                    "findings": [],
                    "suggested_actions": [],
                    "confidence": "high",
                },
                CHATGPT_REMOTE,
            )
            read_ok = True
            write_ok = True
    except BridgeError as exc:
        error = exc.to_dict()

    config = state.load_config(default={})
    current_mode = config.get("capability_mode", "unknown")
    proposed_mode = classify(read_ok, write_ok)
    capability_updated = False
    mode = current_mode
    evidence_result: dict[str, object] | None = None
    evidence_error: str | None = None

    if args.evidence_file and error is None:
        try:
            evidence_path = Path(args.evidence_file)
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("evidence root must be an object")
            evidence_result = real_smoke_status_from_evidence(payload)
            evidence_errors = list(evidence_result.get("errors", [])) if isinstance(evidence_result.get("errors", []), list) else []
            if args.read and not evidence_result.get("read_verified"):
                evidence_errors.append("real_read_smoke is not verified")
            if args.write and not evidence_result.get("write_verified"):
                evidence_errors.append("real_write_smoke is not verified")
            if evidence_errors:
                evidence_error = "; ".join(str(item) for item in evidence_errors)
            else:
                mode = tools.update_capability_mode(
                    read_ok=bool(evidence_result.get("read_verified")),
                    write_ok=bool(evidence_result.get("write_verified")),
                    evidence_source=str(evidence_path),
                    evidence_level="real_connector",
                    real_connector_verified=True,
                )
                capability_updated = True
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            evidence_error = str(exc)

    ok = error is None and evidence_error is None
    result = {
        "ok": ok,
        "read_ok": read_ok,
        "write_ok": write_ok,
        "check_scope": "local_bridge_preflight",
        "capability_mode": mode,
        "capability_evidence": capability_evidence_status(state.load_config(default={})),
        "capability_mode_updated": capability_updated,
        "proposed_capability_mode_if_real_connector": proposed_mode,
        "required_external_evidence": ["real_read_smoke", "real_write_smoke"] if args.write else ["real_read_smoke"],
        "evidence_result": evidence_result,
        "error": error or ({"code": "missing_real_connector_evidence", "message": evidence_error} if evidence_error else None),
        "notice": "未提供真实 Connector 证据文件时，本脚本只做本地预检，不更新 capability_mode。",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
