#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CHATGPT_URL = "https://chatgpt.com/"
TASK_BOUND_MESSAGE_OUTPUT = ".ai-bridge-test-runs/first-use/chatgpt-task-brief-message.md"

ASSIST_STEPS = [
    {
        "id": "request_permission",
        "title": "请求用户授权浏览器协助",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "向用户说明会打开 ChatGPT 网页发送任务单 / 审查请求，并把 ChatGPT 回复带回 Codex 审阅；用户未确认前不打开浏览器。",
        "evidence_item": None,
    },
    {
        "id": "check_browser_assist_tools",
        "title": "探测浏览器协助能力",
        "user_confirmation_required": False,
        "auto_execute": False,
        "instruction": "真正打开 ChatGPT 前，先确认当前 Codex 会话具备浏览器协助能力；若不可用，则改用人工网页指南或人工带回兜底。",
        "evidence_item": None,
    },
    {
        "id": "open_official_chatgpt",
        "title": "打开官方 ChatGPT 页面",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "默认只打开官方 ChatGPT 对话页面；只有后续单独确认能力验证时，才进入设置或连接页面。不读取或保存 cookie、密码、账号信息。",
        "evidence_item": None,
    },
    {
        "id": "prepare_collaboration_context",
        "title": "准备任务单 / 审查协同包",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "Codex 先生成最小上下文预览和可发送 ChatGPT 协同消息；用户确认无 secrets 后才允许发送给右侧 ChatGPT。",
        "evidence_item": None,
    },
    {
        "id": "send_task_brief_or_review_request",
        "title": "发送任务单或审查请求",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "在右侧 ChatGPT 中发送任务单或审查请求；ChatGPT 只做规划、审计和建议清单，不写代码、不执行 shell。",
        "evidence_item": None,
    },
    {
        "id": "sync_structured_result",
        "title": "接收 ChatGPT 回复",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "优先自动接收 ChatGPT 回复；自动接收不可用时让 ChatGPT 按固定格式回复，再由 Codex 检查并接收。",
        "evidence_item": None,
    },
    {
        "id": "codex_review_before_execution",
        "title": "Codex 审阅后等待用户确认",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "Codex 生成审阅清单；只有用户逐条确认后，Codex 才能执行最小修改或命令。",
        "evidence_item": None,
    },
    {
        "id": "create_connector",
        "title": "创建或检查 ChatGPT 连接",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "只在官方页面粘贴用户确认过的公开连接地址；不把完整连接地址、token 或账号信息写入聊天、日志或仓库。",
        "evidence_item": "chatgpt_connector_created",
    },
    {
        "id": "refresh_tools",
        "title": "刷新并确认工具列表",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "在 ChatGPT 页面中刷新或重新扫描工具，确认能看到读取任务和回传建议的工具。",
        "evidence_item": "chatgpt_tools_discovered",
    },
    {
        "id": "read_smoke",
        "title": "完成真实读取验证",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "先由 Codex 生成发送前预览，用户确认发送后，让右侧 ChatGPT 读取当前任务；记录脱敏工具调用摘要。",
        "evidence_item": "real_read_smoke",
    },
    {
        "id": "write_smoke",
        "title": "完成真实回传验证",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "让右侧 ChatGPT 回传建议；Codex 接收后必须生成审阅清单，且不自动执行建议。",
        "evidence_item": "real_write_smoke",
    },
    {
        "id": "record_evidence",
        "title": "记录脱敏外部证据",
        "user_confirmation_required": True,
        "auto_execute": False,
        "instruction": "只有用户确认脱敏内容后，才写入外部证据清单。",
        "evidence_item": None,
    },
]

EVIDENCE_ITEMS = [
    "external_https_or_secure_mcp_tunnel",
    "chatgpt_connector_created",
    "chatgpt_tools_discovered",
    "real_read_smoke",
    "real_write_smoke",
]

WILL_NOT_DO = [
    "不会读取或保存 ChatGPT cookie、密码、账号信息。",
    "不会把完整连接地址、token、.env、私钥或 .git 内容写入聊天、日志、证据或仓库。",
    "不会在用户确认前发送源码上下文给 ChatGPT。",
    "不会执行 ChatGPT 回传建议动作，也不会自动应用代码修改。",
    "不会把本地测试或浏览器打开成功冒充成真实外部证据。",
]


def browser_collaboration_actions(consent_prompt: str) -> dict[str, object]:
    return {
        "open_official_chatgpt": {
            "id": "open_official_chatgpt",
            "url": OFFICIAL_CHATGPT_URL,
            "target_surface": "official_chatgpt_conversation",
            "requires_user_permission": True,
            "permission_prompt": consent_prompt,
            "browser_assist_runtime_check_required": True,
            "can_assist_after_permission": True,
            "opens_connector_settings": False,
            "uses_dom_scraping": False,
            "reads_or_saves_cookies": False,
            "sends_context": False,
            "does_not_prove_connector": True,
            "auto_execute_without_user_permission": False,
        },
        "send_task_bound_message": {
            "id": "send_task_bound_message",
            "requires_confirmed_send_action": True,
            "requires_real_task_id": True,
            "message_source": "chatgpt_confirmed_send_action",
            "task_bound_message_output": TASK_BOUND_MESSAGE_OUTPUT,
            "requires_user_confirmation_before_send": True,
            "sends_context_without_user_confirmation": False,
            "right_side_can_edit_source": False,
            "right_side_can_run_shell": False,
            "auto_execute": False,
        },
        "sync_structured_result": {
            "id": "sync_structured_result",
            "prefer_official_mcp": True,
            "read_only_fallback_tool": "bridge_fetch_task_packet",
            "structured_import_fallback": "codex-bridge-result-json",
            "requires_review_result_before_execution": True,
            "suggested_actions_require_user_confirmation": True,
            "auto_execute": False,
        },
    }


def build_packet() -> dict[str, object]:
    consent_prompt = "是否允许我打开 ChatGPT 网页，发送这次任务单 / 审查请求，并把 ChatGPT 回复带回 Codex 审阅？"
    return {
        "ok": True,
        "title": "ChatGPT 网页协助包",
        "audience": "普通用户授权后的浏览器协助",
        "default_mode": "automated_collaboration",
        "requires_user_permission": True,
        "auto_execute": False,
        "can_use_codex_browser_or_computer_use": True,
        "browser_assist_capability_gate": {
            "must_check_runtime_tools_before_opening_chatgpt": True,
            "accepted_capabilities": ["Chrome 控制能力", "computer use"],
            "if_available": "用户授权后可协助官方 ChatGPT 页面操作。",
            "if_unavailable": "改用人工网页指南或人工带回兜底，不要求用户手敲本地命令。",
            "does_not_prove_connector": True,
        },
        "consent_prompt": consent_prompt,
        "browser_collaboration_actions": browser_collaboration_actions(consent_prompt),
        "requires_separate_confirmation_for": [
            "创建或修改 ChatGPT 连接 / App。",
            "刷新工具列表或执行真实外部验证。",
            "写入真实外部证据。",
            "执行 ChatGPT 建议、运行命令或应用代码修改。",
        ],
        "codex_auto_preflight": [
            "自动完成首次本地验证和能力门诊。",
            "自动检查 Bridge 状态和本地工具。",
            "自动生成任务单 / 审查协同包。",
            "自动生成可直接发送给 ChatGPT 的任务单 / 审查消息。",
            "自动生成连接材料和兜底材料。",
        ],
        "collaboration_message_builder": {
            "script": "scripts/build_chatgpt_collaboration_message.py",
            "task_brief_command": "python3 scripts/build_chatgpt_collaboration_message.py --mode task-brief --output .ai-bridge-test-runs/first-use/chatgpt-task-brief-message.md --json",
            "review_command": "python3 scripts/build_chatgpt_collaboration_message.py --mode review --output .ai-bridge-test-runs/first-use/chatgpt-review-message.md --json",
            "requires_user_confirmation_before_send": True,
            "auto_execute": False,
            "draft_only_without_task_id": True,
            "structured_import_ready_without_task_id": False,
        },
        "task_bound_message_builder": {
            "script": ".agents/skills/codex-chatgpt-bridge/scripts/push_task.py",
            "task_brief_preview_command": "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py --title \"ChatGPT 任务单 / 审查协同\" --goal \"请先不要写代码。请把这次需求整理成适合 Codex 执行的任务单。\" --mode plan --chatgpt-message-mode task-brief --chatgpt-message-output .ai-bridge-test-runs/first-use/chatgpt-task-brief-message.md --preview",
            "review_preview_command": "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py --title \"ChatGPT 执行结果审查\" --goal \"审查 Codex 执行结果并输出结构化建议。\" --mode review --chatgpt-message-mode review --chatgpt-message-output .ai-bridge-test-runs/first-use/chatgpt-review-message.md --preview",
            "confirmed_send_replaces_preview_with_yes": True,
            "requires_real_task_id": True,
            "structured_import_ready_after_confirmed_send": True,
            "draft_messages_importable": False,
            "requires_user_confirmation_before_send": True,
            "auto_send_to_chatgpt": False,
            "auto_execute": False,
        },
        "collaboration_flow": [
            "ChatGPT Pro 生成 Codex 执行任务单。",
            "Codex 执行用户确认后的最小修改并跑验证。",
            "ChatGPT Pro 审查 Codex 执行结果。",
            "Codex 接收或检查 ChatGPT 回复，等待用户确认后再执行建议。",
        ],
        "connector_validation_flow": [
            "刷新工具列表只证明工具发现。",
            "真实读取和回传验证必须来自真实工具调用与 Bridge 审计。",
            "没有真实外部证据时，外部连接能力继续保持未验证。",
        ],
        "steps": ASSIST_STEPS,
        "evidence_items": EVIDENCE_ITEMS,
        "maintainer_attest_commands": {
            item: f"python3 scripts/attest_connector_evidence.py --item-id {item} --template --json"
            for item in EVIDENCE_ITEMS
        },
        "will_not_do": WILL_NOT_DO,
        "fallback_if_not_allowed": "Codex 仍可准备脱敏协同包；人工带回只作为最后兜底。",
        "not_proven_by_this_packet": [
            "真实 ChatGPT 已收到并处理任务单 / 审查请求",
            "真实 ChatGPT 连接已创建",
            "真实工具列表已刷新",
            "真实外部读取 / 回传验证已通过",
            "真实外部证据已写入证据清单",
        ],
    }


def render_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# ChatGPT 网页协助包",
        "",
        "用途：当普通用户确认后，Codex 可以协助操作官方 ChatGPT 页面，让 ChatGPT Pro 生成任务单、审查 Codex 执行结果，并把 ChatGPT 回复带回 Codex 审阅链路。",
        "",
        "这不是完成证明。只有真实网页操作完成、证据脱敏并写入外部证据清单后，发布门禁才可能通过。",
        "",
        "打开 ChatGPT 前，Codex 必须先确认当前会话具备浏览器协助能力；如果不可用，就切回人工网页指南或人工带回兜底。",
        "",
        "## 授权提示",
        "",
        str(packet["consent_prompt"]),
        "",
        "以下动作不包含在第一屏默认授权内，必须后续单独确认：",
    ]
    for item in packet["requires_separate_confirmation_for"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(
        [
        "",
        "## 默认协同流程",
        "",
        ]
    )
    builder = packet["collaboration_message_builder"]  # type: ignore[index]
    if isinstance(builder, dict):
        lines.extend(
            [
                "可发送给 ChatGPT 的任务单 / 审查消息由一键首次验证自动准备；普通用户不需要手动拼命令。",
                "真正发送给 ChatGPT 的消息必须来自用户确认后的本次协同任务；草稿消息不能接入 Codex 审阅链路。",
                "",
            ]
        )
    for item in packet["collaboration_flow"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 外部连接能力验证阶段",
            "",
        ]
    )
    for item in packet["connector_validation_flow"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
        "## 浏览器协助步骤",
        "",
        ]
    )
    for index, step in enumerate(packet["steps"], start=1):
        if not isinstance(step, dict):
            continue
        lines.extend(
            [
                f"{index}. {step['title']}",
                f"   - 说明：{step['instruction']}",
                f"   - 需要用户确认：{str(step['user_confirmation_required']).lower()}",
                f"   - 自动执行：{str(step['auto_execute']).lower()}",
            ]
        )
    lines.extend(["", "## 我不会做", ""])
    for item in packet["will_not_do"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 证据记录",
            "",
            "真实网页操作完成后，Codex 会先展示脱敏证据摘要；只有用户确认后，才由 Codex 或维护者写入证据文件。",
        ]
    )
    lines.extend(["", f"未授权时：{packet['fallback_if_not_allowed']}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 ChatGPT 网页协助操作包。")
    parser.add_argument("--output", help="写入 Markdown 文件；不传则输出到 stdout。")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    packet = build_packet()
    markdown = render_markdown(packet)
    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    packet["output"] = str(output_path) if output_path else None

    if args.json:
        print(json.dumps(packet, ensure_ascii=False, indent=2))
    elif output_path:
        print(f"已写入：{output_path}")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
