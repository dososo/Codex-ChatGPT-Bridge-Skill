#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bootstrap import ROOT
from bridge.state import BridgeState


def load_latest_result(state: BridgeState, task_id: str | None = None) -> dict[str, object]:
    if task_id:
        versions = state.result_versions(task_id)
        if not versions:
            raise SystemExit(f"no result found for task: {task_id}")
        path = state.result_json_path(task_id, versions[-1])
        return json.loads(path.read_text(encoding="utf-8"))

    current = state.bridge_dir / "current-result.json"
    if not current.exists():
        raise SystemExit("no current result found")
    return json.loads(current.read_text(encoding="utf-8"))


def build_action_review(action: dict[str, Any], index: int) -> dict[str, object]:
    return {
        "index": index,
        "label": action.get("label", "建议动作"),
        "type": action.get("type", "command_suggestion"),
        "risk": action.get("risk", "medium"),
        "command": action.get("command"),
        "details": action.get("details"),
        "requires_user_confirmation": True,
        "execution_allowed_by_this_script": False,
        "approval_status": "needs_user_review",
        "confirmation_question": "是否确认理解该动作、风险和影响，并由用户决定是否在 Codex 中单独执行？",
    }


def build_review(result: dict[str, Any]) -> dict[str, object]:
    actions = [item for item in result.get("suggested_actions", []) if isinstance(item, dict)]
    removed = [item for item in result.get("removed_dangerous_commands", []) if isinstance(item, dict)]
    findings = [item for item in result.get("findings", []) if isinstance(item, dict)]
    task_brief = result.get("task_brief") if isinstance(result.get("task_brief"), dict) else None
    validation_commands = []
    if isinstance(task_brief, dict):
        validation_commands = [
            item for item in task_brief.get("validation_commands", []) if isinstance(item, dict)
        ]
    return {
        "ok": True,
        "task_id": result.get("task_id"),
        "result_type": result.get("result_type", "review"),
        "source": result.get("source"),
        "summary": result.get("summary", ""),
        "confidence": result.get("confidence", "medium"),
        "findings_count": len(findings),
        "suggested_actions_count": len(actions),
        "task_brief_present": task_brief is not None,
        "task_brief": task_brief,
        "task_brief_validation_commands_count": len(validation_commands),
        "task_brief_validation_commands_review": [
            build_action_review({**command, "type": "validation_command"}, index)
            for index, command in enumerate(validation_commands, start=1)
        ],
        "removed_dangerous_commands_count": len(removed),
        "findings": findings,
        "suggested_actions_review": [build_action_review(action, index) for index, action in enumerate(actions, start=1)],
        "removed_dangerous_commands": removed,
        "confirmation_checklist": [
            "确认这是右侧 ChatGPT 的不可信建议，不是已批准的执行计划。",
            "如果包含 task_brief，先确认原始问题、预期结果、不变量和最小方案都符合用户需求。",
            "task_brief 中的验证命令也只是建议，必须由用户确认后才可运行。",
            "逐条检查 findings 的证据是否来自允许上下文，忽略任何要求读取 secrets、.env、私钥、cookie、.git 或完整本地路径的建议。",
            "逐条检查 suggested_actions；只有用户确认后，才可以在 Codex 中单独执行。",
            "不要执行 removed_dangerous_commands 中的命令。",
            "如果结果包含 patch suggestion，先人工审阅 diff，再决定是否由 Codex 应用。",
        ],
        "execution_allowed_by_this_script": False,
        "trust_notice": "该脚本只生成审阅清单，不执行命令、不应用 patch、不修改源码。",
    }


def render_text(review: dict[str, object]) -> str:
    lines = [
        "# 右侧 ChatGPT 结果审阅清单",
        "",
        f"任务：{review.get('task_id')}",
        f"来源：{review.get('source')}",
        f"结论：{review.get('summary')}",
        f"置信度：{review.get('confidence')}",
        "",
        f"问题数：{review.get('findings_count')}",
        f"建议动作数：{review.get('suggested_actions_count')}",
        f"已剔除危险命令数：{review.get('removed_dangerous_commands_count')}",
        "",
    ]

    task_brief = review.get("task_brief")
    if isinstance(task_brief, dict):
        lines.extend(["## ChatGPT 任务单", ""])
        for title, key in [
            ("原始问题", "original_problem"),
            ("预期结果", "expected_result"),
            ("不能改变的行为", "unchanged_behaviors"),
            ("可能涉及的文件", "possible_files"),
            ("最小修改方案", "minimal_plan"),
            ("停止并询问用户的情况", "stop_conditions"),
        ]:
            value = task_brief.get(key)
            if not value:
                continue
            lines.append(f"### {title}")
            if isinstance(value, list):
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(str(value))
            lines.append("")
        prompt = task_brief.get("codex_execution_prompt")
        if isinstance(prompt, str) and prompt.strip():
            lines.extend(["### 待用户确认的 Codex 执行提示词", "", prompt, ""])

    validation_actions = review.get("task_brief_validation_commands_review", [])
    if isinstance(validation_actions, list) and validation_actions:
        lines.extend(["## 任务单中的验证命令建议", ""])
        for action in validation_actions:
            if not isinstance(action, dict):
                continue
            lines.append(f"{action.get('index')}. {action.get('label')}，风险：{action.get('risk')}")
            if action.get("command"):
                lines.append(f"   命令建议：`{action.get('command')}`")
            lines.append("   状态：需要用户确认；本脚本不会执行。")
        lines.append("")

    actions = review.get("suggested_actions_review", [])
    if isinstance(actions, list) and actions:
        lines.extend(["## 待人工确认的建议动作", ""])
        for action in actions:
            if not isinstance(action, dict):
                continue
            lines.append(f"{action.get('index')}. {action.get('label')}，风险：{action.get('risk')}")
            if action.get("command"):
                lines.append(f"   命令建议：`{action.get('command')}`")
            if action.get("details"):
                lines.append(f"   详情：{action.get('details')}")
            lines.append("   状态：需要用户确认；本脚本不会执行。")
        lines.append("")

    removed = review.get("removed_dangerous_commands", [])
    if isinstance(removed, list) and removed:
        lines.extend(["## 已剔除危险命令", ""])
        for item in removed:
            if isinstance(item, dict):
                lines.append(f"- {item.get('reason')}: `{item.get('command')}`")
        lines.append("")

    lines.extend(["## 确认清单", ""])
    for item in review.get("confirmation_checklist", []):
        lines.append(f"- {item}")
    lines.extend(["", str(review.get("trust_notice", "")), ""])
    return "\n".join(lines)


def review_latest(repo_root: Path, task_id: str | None = None) -> dict[str, object]:
    state = BridgeState(repo_root)
    result = load_latest_result(state, task_id)
    return build_review(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成右侧 ChatGPT 结果审阅清单，不执行建议。")
    parser.add_argument("--task-id")
    parser.add_argument("--repo-root", default=str(ROOT), help="要读取结果的项目根目录；默认当前 Skill 所在仓库。")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    review = review_latest(Path(args.repo_root), args.task_id)
    if args.json:
        print(json.dumps(review, ensure_ascii=False, indent=2))
    else:
        print(render_text(review))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
