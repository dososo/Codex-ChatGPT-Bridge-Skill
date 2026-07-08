#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.cli_encoding import configure_utf8_stdio

configure_utf8_stdio()

PROMPT_ASSET = ROOT / ".agents" / "skills" / "codex-chatgpt-bridge" / "assets" / "right-chatgpt-prompts.md"
VALID_MODES = {
    "task-brief": "18.1A Codex 执行任务单提示词",
    "review": "18.1B Codex 执行结果审查提示词",
}
FIXED_PROMPT = "18.1 首次固定提示词"
RESULT_INTAKE_CONTRACT = {
    "status_source": "build_chatgpt_collaboration_session.py --json result_view / ui_actions.post_chatgpt_result_actions",
    "codex_uses_repo_bound_actions": True,
    "right_side_should_not_tell_user_to_run_local_commands": True,
    "preview_before_import": True,
    "requires_user_confirmation_before_pull_import_or_execute": True,
}


def extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        raise SystemExit(f"missing prompt section: {heading}")
    next_match = re.search(r"^##\s+", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(text)
    section = text[match.end() : end].strip()
    fence = re.search(r"```text\s*([\s\S]+?)\s*```", section)
    return fence.group(1).strip() if fence else section


def load_prompt_sections(mode: str) -> dict[str, str]:
    if mode not in VALID_MODES:
        raise SystemExit(f"unsupported mode: {mode}")
    text = PROMPT_ASSET.read_text(encoding="utf-8")
    mode_heading = VALID_MODES[mode]
    return {
        "fixed": extract_section(text, FIXED_PROMPT),
        "mode_specific": extract_section(text, mode_heading),
        "mode_heading": mode_heading,
    }


def build_message(
    *,
    mode: str,
    title: str,
    request: str,
    context_summary: str,
    task_id: str | None = None,
    execution_summary: str | None = None,
) -> dict[str, Any]:
    sections = load_prompt_sections(mode)
    mode_label = "生成 Codex 执行任务单" if mode == "task-brief" else "审查 Codex 执行结果"
    task_id_status = "provided" if task_id else "missing"
    task_id_text = task_id if task_id else "未提供真实 Bridge task_id；当前消息只能用于草稿协同，不能导入 Codex。"
    execution_text = execution_summary or (
        "如果这是执行前任务单阶段，请只审查需求和上下文；如果是执行后审查阶段，请基于用户提供的 diff、测试输出和审阅材料判断。"
    )
    message_parts = [
        sections["fixed"],
        "",
        sections["mode_specific"],
        "",
        "【本次协同请求】",
        f"- 类型：{mode_label}",
        f"- 标题：{title}",
        f"- task_id：{task_id_text}",
        "- 导入门禁：结构化结果只有在 task_id 是真实 Bridge 任务 ID 时，才能由 Codex 预检并在用户确认后导入。",
        "- 结果回收：不要要求用户手写本地导入或审阅命令；Codex 会读取当前 session 状态卡里的 repo-bound pull / intake / import / review 动作完成接收、预检和审阅。",
        "",
        "【用户原始需求】",
        request.strip(),
        "",
        "【Codex 提供的受控上下文摘要】",
        context_summary.strip(),
        "",
        "【Codex 执行状态 / 审查材料摘要】",
        execution_text.strip(),
        "",
        "【回传要求】",
        "- 如果官方 MCP write 工具可用，优先写回结构化结果。",
        "- 如果写回不可用，且本消息包含真实 task_id，请在最终回答中输出 fenced `codex-bridge-result-json`，并使用该真实 task_id。",
        "- fenced `codex-bridge-result-json` 必须包含顶层 `summary`，用于 Codex intake schema 校验。",
        "- 如果本消息没有真实 task_id，请先提示 Codex 重新生成带 task_id 的消息；不要把 `unknown` 包装成可导入结果。",
        "- suggested_actions 只能是建议，必须等待 Codex 审阅并由用户确认。",
    ]
    if task_id:
        message_parts.extend(
            [
                "",
                "【真实 task_id】",
                f"- fenced `codex-bridge-result-json` 的 task_id 字段必须是：{task_id}",
            ]
        )
    else:
        message_parts.extend(
            [
                "",
                "【缺少真实 task_id】",
                "- 当前消息没有真实 Bridge task_id，只能用于生成任务单草稿或审查思路。",
                "- 如果需要把结果导入 Codex，请先让 Codex 创建 / 发送 Bridge 任务，并重新生成带 `--task-id` 的消息。",
                "- 不要输出把 `task_id` 写成 `unknown` 的可导入 JSON。",
            ]
        )
    if mode == "task-brief":
        message_parts.extend(
            [
                "",
                "【任务单结构化字段】",
                "- summary：一句话结论，必须放在 JSON 顶层。",
                "- result_type 必须是 task_brief。",
                "- task_brief.original_problem：原始问题。",
                "- task_brief.expected_result：预期结果。",
                "- task_brief.unchanged_behaviors：不能改变的行为数组。",
                "- task_brief.possible_files：可能涉及的文件数组，只能来自受控上下文。",
                "- task_brief.minimal_plan：最小修改方案数组。",
                "- task_brief.validation_commands：验证命令建议数组，命令只能作为建议。",
                "- task_brief.stop_conditions：停止并询问用户的情况数组。",
                "- task_brief.codex_execution_prompt：可直接交给 Codex 的执行提示词。",
            ]
        )
    copyable_message = "\n".join(message_parts).strip() + "\n"
    return {
        "ok": True,
        "mode": mode,
        "default_mode": "automated_collaboration",
        "mode_label": mode_label,
        "title": title,
        "prompt_asset": str(PROMPT_ASSET),
        "template_sections": [FIXED_PROMPT, sections["mode_heading"]],
        "task_id_status": task_id_status,
        "requires_real_task_id_for_import": True,
        "structured_import_ready": bool(task_id),
        "codex_result_intake_contract": RESULT_INTAKE_CONTRACT,
        "requires_user_confirmation_before_send": True,
        "auto_execute": False,
        "sends_context": False,
        "copyable_message": copyable_message,
        "will_not_do": [
            "仅生成消息时不会打开 ChatGPT 网页；打开网页需要单独授权。",
            "不会发送上下文。",
            "不会读取 secrets、.env、token、cookie、私钥、完整 Connector URL 或 .git。",
            "不会执行 ChatGPT 建议、运行命令或应用 patch。",
            "不会写入真实外部 evidence。",
        ],
        "external_not_proven": [
            "真实 ChatGPT 已收到该消息",
            "真实 ChatGPT 已按模板输出任务单或审查结果",
            "真实 MCP read/write tool call 已发生",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ChatGPT 协同消息",
        "",
        f"模式：{payload['mode_label']}",
        "",
        "发送前必须由用户确认上下文不含 secrets、`.env`、token、cookie、私钥、完整 Connector URL 或 `.git` 内容。",
        "",
        "## 可直接发送给 ChatGPT 的消息",
        "",
        "```text",
        payload["copyable_message"].rstrip(),
        "```",
        "",
        "## 我不会做",
        "",
    ]
    for item in payload["will_not_do"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成可发送给右侧 ChatGPT 的任务单 / 审查协同消息。")
    parser.add_argument("--mode", choices=sorted(VALID_MODES), required=True)
    parser.add_argument("--title", default="ChatGPT 任务单 / 审查协同")
    parser.add_argument("--request", default="请基于 Codex 已准备并经用户确认的最小上下文协助规划或审查。")
    parser.add_argument("--context-summary", default="上下文将由 Codex 在发送前预览并经用户确认；不要请求 secrets 或未允许文件。")
    parser.add_argument("--task-id")
    parser.add_argument("--execution-summary")
    parser.add_argument("--output", help="写入 Markdown 文件；不传则输出到 stdout。")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_message(
        mode=args.mode,
        title=args.title,
        request=args.request,
        context_summary=args.context_summary,
        task_id=args.task_id,
        execution_summary=args.execution_summary,
    )
    markdown = render_markdown(payload)
    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    payload["output"] = str(output_path) if output_path else None

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif output_path:
        print("已生成 ChatGPT 协同消息。")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
