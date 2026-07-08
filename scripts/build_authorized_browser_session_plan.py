#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CHATGPT_URL = "https://chatgpt.com/"
TASK_BOUND_MESSAGE_OUTPUT = ".ai-bridge-test-runs/first-use/chatgpt-task-brief-message.md"
PERMISSION_PHRASE = "允许打开 ChatGPT 网页协同"
COLLABORATION_SESSION_SCRIPT = "scripts/build_chatgpt_collaboration_session.py"
ACTOR_LABELS = {
    "codex": "Codex",
    "user": "用户",
    "codex_with_user_permission": "Codex（用户授权后）",
    "codex_and_user": "Codex 和用户",
    "codex_after_user_review": "Codex（用户确认后）",
}

SESSION_STEPS = [
    {
        "id": "local_preflight",
        "title": "自动完成本地预检",
        "actor": "codex",
        "requires_user_confirmation": False,
        "auto_execute_after_permission": True,
        "instruction": "由 Skill 自动完成本地首次验证、证据包和下一步卡片生成，不需要用户手动敲本地命令。",
    },
    {
        "id": "request_browser_permission",
        "title": "请求打开 ChatGPT 网页授权",
        "actor": "user",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "用户明确回复“允许打开 ChatGPT 网页协同”后，Codex 才能使用 Chrome / computer use 协助发送任务单 / 审查请求。",
    },
    {
        "id": "check_browser_assist_tools",
        "title": "探测浏览器协助能力",
        "actor": "codex",
        "requires_user_confirmation": False,
        "auto_execute_after_permission": True,
        "instruction": "打开 ChatGPT 前先探测当前 Codex 会话是否有浏览器协助能力；没有就切到人工网页指南或人工带回兜底。",
    },
    {
        "id": "prepare_collaboration_context",
        "title": "准备 ChatGPT 任务单 / 审查协同包",
        "actor": "codex",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "Codex 先读取当前协同状态卡；用户确认预览后，才创建本次协同任务并生成可发送 ChatGPT 的消息。",
    },
    {
        "id": "open_official_chatgpt",
        "title": "打开官方 ChatGPT 页面",
        "actor": "codex_with_user_permission",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": True,
        "instruction": "只有当前协同状态卡显示消息已准备好后，才打开官方 ChatGPT 对话页面；不读取 cookie、密码、账号资料或网页结构数据。",
    },
    {
        "id": "user_login_or_admin",
        "title": "用户处理登录、2FA 或管理员权限",
        "actor": "user",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "登录、2FA、工作区选择、Developer Mode 管理员开关只能由用户自己确认。",
    },
    {
        "id": "send_task_brief_to_chatgpt",
        "title": "发送任务单请求给 ChatGPT",
        "actor": "codex_with_user_permission",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": True,
        "instruction": "只发送当前协同状态卡指定的本次任务消息；ChatGPT 只做规划、审计和建议清单，不写代码、不执行 shell。",
    },
    {
        "id": "sync_chatgpt_result",
        "title": "接收 ChatGPT 回复",
        "actor": "codex_and_user",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "优先自动接收 ChatGPT 回复；自动接收不可用时让 ChatGPT 按固定格式回复，再由 Codex 检查并接收。",
    },
    {
        "id": "codex_review_and_user_approval",
        "title": "Codex 审阅并等待用户确认",
        "actor": "codex_after_user_review",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "Codex 生成审阅清单；只有用户逐条确认后，Codex 才能执行最小修改或命令。",
    },
    {
        "id": "create_connector",
        "title": "协助创建 ChatGPT 连接",
        "actor": "codex_with_user_permission",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": True,
        "instruction": "在用户确认后粘贴已检查的公开连接地址；不记录完整连接地址或 token。",
        "evidence_item": "chatgpt_connector_created",
    },
    {
        "id": "refresh_tools",
        "title": "协助刷新工具列表",
        "actor": "codex_with_user_permission",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": True,
        "instruction": "在官方页面中刷新或扫描工具，确认是否出现读取任务和回传建议的工具。",
        "evidence_item": "chatgpt_tools_discovered",
    },
    {
        "id": "read_smoke",
        "title": "真实读取验证",
        "actor": "codex_and_user",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "Codex 生成发送前预览；用户确认后才发送最小上下文，让右侧 ChatGPT 读取当前任务。",
        "evidence_item": "real_read_smoke",
    },
    {
        "id": "write_smoke",
        "title": "真实回传验证",
        "actor": "codex_and_user",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "右侧 ChatGPT 回传建议；Codex 只接收并生成审阅清单，不执行建议。",
        "evidence_item": "real_write_smoke",
    },
    {
        "id": "record_redacted_evidence",
        "title": "记录脱敏证据",
        "actor": "codex_after_user_review",
        "requires_user_confirmation": True,
        "auto_execute_after_permission": False,
        "instruction": "用户确认脱敏摘要后，才写入外部证据清单。",
    },
]

HUMAN_ONLY_STEPS = [
    "ChatGPT 登录、2FA、验证码或账号切换。",
    "工作区、Developer Mode、ChatGPT 连接权限或管理员开关确认。",
    "确认是否发送任务上下文给 ChatGPT。",
    "确认脱敏证据是否可以写入外部证据清单。",
    "确认是否执行右侧 ChatGPT 回传建议。",
]

WILL_NOT_DO = [
    "不会读取或保存 cookie、密码、账号资料、token、.env、私钥或 .git 内容。",
    "不会抓取 ChatGPT 网页结构，不依赖网页结构解析作为产品能力。",
    "不会把完整连接地址或 token 写入聊天、日志、证据或仓库。",
    "不会在用户确认前发送源码上下文给 ChatGPT。",
    "不会执行 ChatGPT 回传建议动作，也不会自动应用代码修改。",
    "不会把网页打开成功、本地测试或兜底材料生成冒充成真实外部证据。",
]


def browser_collaboration_actions() -> dict[str, object]:
    return {
        "open_official_chatgpt": {
            "id": "open_official_chatgpt",
            "url": OFFICIAL_CHATGPT_URL,
            "target_surface": "official_chatgpt_conversation",
            "requires_user_permission": True,
            "permission_phrase": PERMISSION_PHRASE,
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


def session_bound_handoff() -> dict[str, object]:
    return {
        "script": COLLABORATION_SESSION_SCRIPT,
        "state_command": "python3 scripts/build_chatgpt_collaboration_session.py --json",
        "confirm_task_message_command": "python3 scripts/build_chatgpt_collaboration_session.py --yes --json",
        "ordinary_user_field": "user_view",
        "browser_handoff_field": "browser_handoff",
        "execution_actions_field": "ui_actions",
        "required_phase_before_open": "ready_to_open_chatgpt",
        "requires_user_view_primary_action": True,
        "requires_browser_handoff_enabled": True,
        "requires_real_task_id": True,
        "requires_task_bound_message_ready_to_send": True,
        "requires_message_path": True,
        "requires_user_confirmation_before_confirm": True,
        "requires_user_confirmation_before_open": True,
        "requires_user_confirmation_before_send": True,
        "does_not_open_chatgpt_when_creating_task": True,
        "does_not_send_chatgpt_when_creating_task": True,
        "does_not_write_external_evidence": True,
        "does_not_prove_connector": True,
        "blocked_until": [
            "confirmed_task_created",
            "task_bound_message_ready",
        ],
        "state_fields": [
            "state.confirmed_task_created",
            "state.task_id",
            "state.task_bound_message_path",
            "state.task_bound_message_ready_to_send",
            "browser_handoff.enabled",
            "browser_handoff.message_path",
        ],
    }


def build_plan() -> dict[str, object]:
    return {
        "ok": True,
        "title": "授权后 ChatGPT 自动化协同会话计划",
        "audience": "普通用户和协助执行的 Codex",
        "purpose": "用户明确授权后，由 Codex 协助操作官方 ChatGPT 页面，让 ChatGPT Pro 生成任务单、做审查，并把 ChatGPT 回复带回 Codex 审阅链路。",
        "default_mode": "automated_collaboration",
        "product_runtime_dependency": False,
        "uses_dom_scraping": False,
        "requires_user_permission": True,
        "permission_phrase": PERMISSION_PHRASE,
        "local_user_shell_commands_required": False,
        "requires_separate_confirmation_for": [
            "创建或修改 ChatGPT 连接 / App。",
            "刷新工具列表或执行真实外部验证。",
            "写入真实外部证据。",
            "执行 ChatGPT 建议、运行命令或应用代码修改。",
        ],
        "codex_auto_preparation": [
            "自动完成本地首次验证。",
            "自动生成本次协同状态卡。",
            "自动生成 ChatGPT 任务单 / 审查协同包。",
            "自动生成可直接发送给 ChatGPT 的任务单 / 审查消息。",
            "自动准备连接材料、兜底材料和外部证据确认材料。",
            "自动生成下一步用户确认卡。",
        ],
        "session_state_source": {
            "script": COLLABORATION_SESSION_SCRIPT,
            "command": "python3 scripts/build_chatgpt_collaboration_session.py --json",
            "ordinary_user_card": "user_view",
            "browser_execution_handoff": "browser_handoff",
            "developer_actions": "ui_actions",
            "single_source_of_truth": True,
        },
        "session_bound_handoff": session_bound_handoff(),
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
            {
                "id": "task_brief",
                "title": "生成 Codex 执行任务单",
                "chatgpt_role": "读受控上下文、拆需求、列不变量、给最小方案和验证命令。",
                "codex_role": "准备最小上下文、执行用户确认后的任务单、跑验证。",
                "result_return": "优先自动接收；不可用时按固定格式回复。",
            },
            {
                "id": "execution_review",
                "title": "审查 Codex 执行结果",
                "chatgpt_role": "审查 diff 风险、行为回归、测试遗漏和安全边界。",
                "codex_role": "接收审查结果，生成审阅清单，等待用户确认。",
                "result_return": "建议动作只是不可信建议，必须由用户确认。",
            },
        ],
        "connector_validation_flow": [
            "刷新 ChatGPT 连接工具列表。",
            "真实读取验证：只在确认右侧工具真正读取任务后记录。",
            "真实回传验证：只在回传、接收和审阅链路都通过后记录。",
        ],
        "can_use_codex_chrome_or_computer_use_after_permission": True,
        "browser_collaboration_actions": browser_collaboration_actions(),
        "browser_assist_capability_gate": {
            "must_check_runtime_tools_before_opening_chatgpt": True,
            "accepted_capabilities": ["Chrome 控制能力", "computer use"],
            "if_available": "用户授权后可由 Codex 协助打开官方 ChatGPT、发送任务单 / 审查请求并接收 ChatGPT 回复；连接配置、工具刷新和真实验证需要后续单独确认。",
            "if_unavailable": "不让用户拼本地命令，改用人工网页指南或人工带回兜底。",
            "does_not_prove_connector": True,
        },
        "steps": SESSION_STEPS,
        "human_only_steps": HUMAN_ONLY_STEPS,
        "will_not_do": WILL_NOT_DO,
        "fallback_if_not_allowed": "不授权浏览器协助时，Codex 仍可准备脱敏协同包；人工带回只作为最后兜底。",
        "recording_policy": {
            "auto_record_external_evidence": False,
            "requires_user_review_before_record": True,
            "redacted_evidence_only": True,
        },
        "next_user_message": "如果你要我继续网页侧协同，请直接回复：允许打开 ChatGPT 网页协同",
        "not_proven_by_this_plan": [
            "真实 ChatGPT 已收到并处理任务单 / 审查请求",
            "真实 ChatGPT 连接已创建",
            "真实 ChatGPT 工具列表已刷新",
            "真实外部读取 / 回传验证已通过",
            "真实外部证据已写入证据清单",
        ],
    }


def render_markdown(plan: dict[str, object]) -> str:
    lines = [
        "# 授权后 ChatGPT 自动化协同会话计划",
        "",
        "用途：用户明确授权后，让 Codex 协助操作官方 ChatGPT 页面，请 ChatGPT Pro 生成任务单、审查 Codex 执行结果，并把 ChatGPT 回复带回 Codex 审阅链路。",
        "",
        "这不是产品运行时依赖，也不是网页结构抓取方案。没有授权前，Codex 不打开网页；登录、2FA、发送上下文和记录证据都必须由用户确认。",
        "",
        "打开 ChatGPT 前，Codex 还必须先探测当前会话是否有浏览器协助能力；如果没有，就切回人工网页指南或人工带回兜底。",
        "",
        "## 用户只需要回复",
        "",
        f"`{plan['permission_phrase']}`",
        "",
        "以下动作不包含在第一屏默认授权内，必须后续单独确认：",
    ]
    for item in plan["requires_separate_confirmation_for"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(
        [
        "",
        "## 默认协同阶段",
        "",
        ]
    )
    builder = plan["collaboration_message_builder"]  # type: ignore[index]
    if isinstance(builder, dict):
        lines.extend(
            [
                "可发送给 ChatGPT 的任务单 / 审查消息由一键首次验证自动准备；普通用户不需要手动拼命令。",
                "授权后的按钮、打开网页和发送动作都以当前协同状态卡为准。",
                "真正发送给 ChatGPT 的消息必须来自用户确认后的本次协同任务；草稿消息不能接入 Codex 审阅链路。",
                "",
            ]
        )
    for index, item in enumerate(plan["collaboration_flow"], start=1):  # type: ignore[index]
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"{index}. {item['title']}",
                f"   - ChatGPT：{item['chatgpt_role']}",
                f"   - Codex：{item['codex_role']}",
                f"   - 回传：{item['result_return']}",
            ]
        )
    lines.extend(
        [
            "",
            "## 外部连接能力验证阶段",
            "",
        ]
    )
    for item in plan["connector_validation_flow"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
        "## 会话步骤",
        "",
        ]
    )
    for index, step in enumerate(plan["steps"], start=1):  # type: ignore[index]
        if not isinstance(step, dict):
            continue
        actor = str(step["actor"])
        lines.extend(
            [
                f"{index}. {step['title']}",
                f"   - 执行方：{ACTOR_LABELS.get(actor, actor)}",
                f"   - 需要用户确认：{str(step['requires_user_confirmation']).lower()}",
                f"   - 授权后可自动协助：{str(step['auto_execute_after_permission']).lower()}",
                f"   - 说明：{step['instruction']}",
            ]
        )
    lines.extend(["", "## 必须用户自己确认", ""])
    for item in plan["human_only_steps"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(["", "## 我不会做", ""])
    for item in plan["will_not_do"]:  # type: ignore[index]
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 不授权浏览器协助时",
            "",
            str(plan["fallback_if_not_allowed"]),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成用户授权后的 ChatGPT 自动化协同会话计划。")
    parser.add_argument("--output", help="写入 Markdown 文件；不传则输出到 stdout。")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan = build_plan()
    markdown = render_markdown(plan)
    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    plan["output"] = str(output_path) if output_path else None

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    elif output_path:
        print(f"已写入：{output_path}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
