from __future__ import annotations

from . import SCHEMA_VERSION
from .errors import BridgeError


VALID_MODES = {"review", "plan", "assist", "smoke"}
VALID_PRIORITIES = {"low", "normal", "high"}
VALID_CONFIDENCE = {"low", "medium", "high"}


def ensure_schema_version(value: str | None) -> None:
    if value and value != SCHEMA_VERSION:
        raise BridgeError("unsupported_schema_version", f"expected schema_version {SCHEMA_VERSION}")


def require_string(payload: dict[str, object], key: str, *, max_len: int = 4000) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BridgeError("invalid_schema", f"{key} must be a non-empty string")
    if len(value) > max_len:
        raise BridgeError("invalid_schema", f"{key} is too long")
    return value.strip()


def normalize_task_input(payload: dict[str, object]) -> dict[str, object]:
    ensure_schema_version(payload.get("schema_version") if isinstance(payload.get("schema_version"), str) else None)
    title = require_string(payload, "title", max_len=200)
    goal = require_string(payload, "goal", max_len=4000)
    mode = payload.get("mode", "review")
    priority = payload.get("priority", "normal")
    context_policy = payload.get("context_policy", "focused")
    context = payload.get("context", {})
    expected_output = payload.get("expected_output", ["结论", "高风险问题", "测试缺口", "建议修改", "建议 Codex 下一步执行的命令"])

    if mode not in VALID_MODES:
        raise BridgeError("invalid_schema", "mode must be review, plan, assist, or smoke")
    if priority not in VALID_PRIORITIES:
        raise BridgeError("invalid_schema", "priority must be low, normal, or high")
    if not isinstance(context, dict):
        raise BridgeError("invalid_schema", "context must be an object")
    if not isinstance(expected_output, list) or not all(isinstance(item, str) for item in expected_output):
        raise BridgeError("invalid_schema", "expected_output must be a string list")

    return {
        "title": title,
        "goal": goal,
        "mode": mode,
        "priority": priority,
        "context_policy": context_policy if isinstance(context_policy, str) else "focused",
        "context": dict(context),
        "expected_output": expected_output,
    }


def normalize_result_input(payload: dict[str, object], *, require_claim: bool = True) -> dict[str, object]:
    ensure_schema_version(payload.get("schema_version") if isinstance(payload.get("schema_version"), str) else None)
    task_id = require_string(payload, "task_id", max_len=80)
    claim_id = payload.get("claim_id")
    if require_claim and (not isinstance(claim_id, str) or not claim_id.strip()):
        raise BridgeError("invalid_schema", "claim_id must be provided")

    summary = require_string(payload, "summary", max_len=12000)
    result_type = payload.get("result_type", "review")
    confidence = payload.get("confidence", "medium")
    findings = payload.get("findings", [])
    actions = payload.get("suggested_actions", [])
    suggested_patch = payload.get("suggested_patch")
    task_brief = payload.get("task_brief")

    if confidence not in VALID_CONFIDENCE:
        confidence = "medium"
    if not isinstance(findings, list):
        raise BridgeError("invalid_schema", "findings must be a list")
    if not isinstance(actions, list):
        raise BridgeError("invalid_schema", "suggested_actions must be a list")
    if task_brief is not None and not isinstance(task_brief, dict):
        raise BridgeError("invalid_schema", "task_brief must be an object when provided")

    return {
        "task_id": task_id,
        "claim_id": claim_id.strip() if isinstance(claim_id, str) else None,
        "result_type": result_type if isinstance(result_type, str) else "review",
        "summary": summary,
        "findings": findings,
        "suggested_actions": actions,
        "suggested_patch": suggested_patch,
        "task_brief": dict(task_brief) if isinstance(task_brief, dict) else None,
        "confidence": confidence,
    }
