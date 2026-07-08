#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / ".agents" / "skills" / "codex-chatgpt-bridge" / "scripts"
IMPORT_RESULT_SCRIPT = ".agents/skills/codex-chatgpt-bridge/scripts/import_result.py"
REVIEW_RESULT_SCRIPT = ".agents/skills/codex-chatgpt-bridge/scripts/review_result.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.cli_encoding import configure_utf8_stdio
from bridge.errors import BridgeError
from bridge.schemas import normalize_result_input
from bridge.state import BridgeState
from bridge.tools import BridgeTools, sanitize_result_payload

configure_utf8_stdio()


def load_import_result_module() -> Any:
    path = SKILL_SCRIPTS / "import_result.py"
    if str(SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location("import_result", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load import_result.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def script_argv(*args: str) -> list[str]:
    return [sys.executable, "scripts/intake_chatgpt_result.py", *args]


def intake_argv(repo_root: Path, *args: str) -> list[str]:
    command = script_argv(*args)
    command.extend(["--repo-root", str(repo_root)])
    return command


def review_argv(task_id: object | None, repo_root: Path) -> list[str]:
    command = [sys.executable, REVIEW_RESULT_SCRIPT, "--json"]
    command.extend(["--repo-root", str(repo_root)])
    if isinstance(task_id, str) and task_id:
        command.extend(["--task-id", task_id])
    return command


def import_result_argv() -> list[str]:
    return [sys.executable, IMPORT_RESULT_SCRIPT, "--stdin"]


def validate_payload(payload: dict[str, object], repo_root: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, object] | None = None
    sanitized: dict[str, object] | None = None

    try:
        normalized = normalize_result_input(payload, require_claim=False)
    except BridgeError as exc:
        errors.append(f"{exc.code}: {exc.message}")

    task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id or task_id == "unknown":
        errors.append("task_id_missing_or_unknown")
    task_id_str = task_id if isinstance(task_id, str) and task_id and task_id != "unknown" else None

    state = BridgeState(repo_root)
    task_exists = bool(task_id_str and state.task_path(task_id_str).is_file())
    if task_id_str and not task_exists:
        errors.append("task_not_found")

    if normalized is not None and task_exists:
        try:
            sanitized = sanitize_result_payload(normalized, state.token_values())
        except (BridgeError, OSError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"sanitize_failed: {exc}")

    if sanitized and sanitized.get("removed_dangerous_commands"):
        warnings.append("dangerous_commands_will_be_removed")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "task_id": task_id_str,
        "task_exists": task_exists,
        "normalized": normalized,
        "sanitized_preview": {
            "summary": sanitized.get("summary") if isinstance(sanitized, dict) else None,
            "result_type": sanitized.get("result_type") if isinstance(sanitized, dict) else payload.get("result_type", "review"),
            "findings_count": len(sanitized.get("findings", [])) if isinstance(sanitized, dict) and isinstance(sanitized.get("findings"), list) else 0,
            "suggested_actions_count": len(sanitized.get("suggested_actions", [])) if isinstance(sanitized, dict) and isinstance(sanitized.get("suggested_actions"), list) else 0,
            "removed_dangerous_commands_count": len(sanitized.get("removed_dangerous_commands", [])) if isinstance(sanitized, dict) and isinstance(sanitized.get("removed_dangerous_commands"), list) else 0,
            "task_brief_present": bool(isinstance(sanitized, dict) and sanitized.get("task_brief")),
            "redactions_count": len(sanitized.get("redactions", [])) if isinstance(sanitized, dict) and isinstance(sanitized.get("redactions"), list) else 0,
        },
    }


def build_result(
    payload: dict[str, object],
    validation: dict[str, object],
    *,
    repo_root: Path,
    yes: bool,
    imported: dict[str, object] | None = None,
) -> dict[str, object]:
    task_id = validation.get("task_id")
    import_ready = bool(validation.get("ok"))
    imported_ok = bool(imported and imported.get("status") == "result_saved")
    preview_command = intake_argv(repo_root, "--stdin", "--json")
    confirm_command = intake_argv(repo_root, "--stdin", "--yes", "--json")
    review_command = review_argv(task_id, repo_root)
    return {
        "ok": import_ready and (not yes or imported_ok),
        "title": "ChatGPT 结构化结果导入预检",
        "repo_root": str(repo_root),
        "preview_only": not yes,
        "imported": imported_ok,
        "task_id": task_id,
        "task_exists": validation.get("task_exists"),
        "import_ready": import_ready,
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "sanitized_preview": validation.get("sanitized_preview", {}),
        "ui_actions": {
            "preview_intake_result": {
                "id": "preview_intake_result",
                "command_argv": preview_command,
                "command": shlex.join(preview_command),
                "stdin_format": "fenced codex-bridge-result-json",
                "writes_result": False,
                "auto_execute": False,
            },
            "confirm_import_result": {
                "id": "confirm_import_result",
                "command_argv": confirm_command,
                "command": shlex.join(confirm_command),
                "stdin_format": "fenced codex-bridge-result-json",
                "enabled": import_ready and not imported_ok,
                "blocked_until": [] if import_ready else list(validation.get("errors", [])),
                "requires_user_confirmation_before_import": True,
                "writes_local_result": True,
                "writes_external_evidence": False,
                "auto_execute": False,
            },
            "review_imported_result": {
                "id": "review_imported_result",
                "command_argv": review_command,
                "command": shlex.join(review_command),
                "enabled": imported_ok,
                "blocked_until": [] if imported_ok else ["result_import_confirmed"],
                "requires_review_before_execution": True,
                "execution_allowed_by_this_action": False,
                "auto_execute": False,
            },
        },
        "import_result": imported,
        "safety": {
            "right_side_result_is_untrusted": True,
            "requires_real_task_id": True,
            "requires_user_confirmation_before_import": True,
            "executes_suggested_actions": False,
            "applies_patch": False,
            "writes_external_evidence": False,
        },
        "not_proven_by_this_intake": [
            "真实 ChatGPT Connector write-back",
            "真实 tools/call bridge_send_result",
            "用户已批准 suggested_actions",
            "外部 evidence verified",
        ],
    }


def render_text(result: dict[str, object]) -> str:
    lines = [
        "# ChatGPT 结构化结果导入预检",
        "",
        f"- 可导入：{'是' if result.get('import_ready') else '否'}",
        f"- 已导入：{'是' if result.get('imported') else '否'}",
        f"- 任务 ID：{result.get('task_id') or '缺失'}",
    ]
    preview = result.get("sanitized_preview", {})
    if isinstance(preview, dict):
        lines.extend(
            [
                f"- 建议动作数：{preview.get('suggested_actions_count', 0)}",
                f"- 将剔除危险命令数：{preview.get('removed_dangerous_commands_count', 0)}",
            ]
        )
    errors = result.get("errors", [])
    if isinstance(errors, list) and errors:
        lines.append("")
        lines.append("## 阻塞项")
        for error in errors:
            lines.append(f"- {error}")
    lines.extend(
        [
            "",
            "导入前必须由用户确认；导入后仍需运行 review_result.py，且不会自动执行建议。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or import a fenced ChatGPT codex-bridge-result-json payload.")
    parser.add_argument("--stdin", action="store_true", help="Read ChatGPT output from stdin.")
    parser.add_argument("--yes", action="store_true", help="After user confirmation, import the result into local Bridge state.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.stdin:
        parser.error("only --stdin is supported")

    repo_root = Path(args.repo_root).resolve()
    text = sys.stdin.read()
    errors: list[str] = []
    payload: dict[str, object] = {}
    try:
        payload = load_import_result_module().extract_json(text)
    except Exception as exc:  # noqa: BLE001 - convert parser failures into UI-readable diagnostics.
        errors.append(f"parse_failed: {exc}")

    validation = validate_payload(payload, repo_root) if payload else {
        "ok": False,
        "errors": errors,
        "warnings": [],
        "task_id": None,
        "task_exists": False,
        "sanitized_preview": {},
    }
    imported: dict[str, object] | None = None
    if args.yes and validation.get("ok"):
        imported = BridgeTools(BridgeState(repo_root)).import_result(payload)
    result = build_result(payload, validation, repo_root=repo_root, yes=args.yes, imported=imported)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
