#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.ordinary_journey import compact_journey_for_status  # noqa: E402

VERIFY_FIRST_USE = ROOT / ".agents" / "skills" / "codex-chatgpt-bridge" / "scripts" / "verify_first_use.py"
SESSION_OUTPUT = ".ai-bridge-test-runs/first-use/chatgpt-collaboration-session.md"
OFFICIAL_CHATGPT_URL = "https://chatgpt.com/"
IMPORT_RESULT_SCRIPT = ".agents/skills/codex-chatgpt-bridge/scripts/import_result.py"
PULL_RESULT_SCRIPT = ".agents/skills/codex-chatgpt-bridge/scripts/pull_result.py"
REVIEW_RESULT_SCRIPT = ".agents/skills/codex-chatgpt-bridge/scripts/review_result.py"
INTAKE_RESULT_SCRIPT = "scripts/intake_chatgpt_result.py"


def script_argv(*args: str) -> list[str]:
    return [sys.executable, "scripts/build_chatgpt_collaboration_session.py", *args]


def skill_script_argv(script: str, *args: str) -> list[str]:
    return [sys.executable, script, *args]


def result_script_argv(script: str, task_id: object | None, *args: str) -> list[str]:
    command = skill_script_argv(script, *args)
    command.extend(["--repo-root", str(ROOT)])
    if isinstance(task_id, str) and task_id:
        command.extend(["--task-id", task_id])
    return command


def run_json_command(command: list[str], *, timeout: int = 120) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    parsed: Any = None
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "command_argv": command,
        "command": shlex.join(command),
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
        "json": parsed,
    }


def run_first_use(*, dry_run: bool) -> dict[str, Any]:
    command = [sys.executable, str(VERIFY_FIRST_USE), "--json"]
    if dry_run:
        command.insert(-1, "--dry-run")
    return run_json_command(command)


def validate_confirmed_send_action(action: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if not isinstance(action, dict):
        return ["missing_confirmed_send_action"]
    command_argv = action.get("command_argv")
    if not isinstance(command_argv, list) or not command_argv:
        errors.append("confirmed_send_action_missing_command_argv")
    else:
        parts = [str(part) for part in command_argv]
        joined = " ".join(parts)
        if "--yes" not in parts:
            errors.append("confirmed_send_action_must_use_yes")
        if "--preview" in parts:
            errors.append("confirmed_send_action_must_not_use_preview")
        if "push_task.py" not in joined:
            errors.append("confirmed_send_action_must_call_push_task")
    if action.get("requires_user_confirmation") is not True:
        errors.append("confirmed_send_action_must_require_user_confirmation")
    if action.get("creates_real_bridge_task") is not True:
        errors.append("confirmed_send_action_must_create_real_task")
    if action.get("auto_send_to_chatgpt") is not False:
        errors.append("confirmed_send_action_must_not_auto_send")
    if action.get("auto_execute") is not False:
        errors.append("confirmed_send_action_must_not_auto_execute")
    return errors


def execute_confirmed_send(first_use: dict[str, Any]) -> dict[str, Any]:
    action = first_use.get("chatgpt_confirmed_send_action")
    errors = validate_confirmed_send_action(action if isinstance(action, dict) else None)
    if errors:
        return {
            "ok": False,
            "returncode": 2,
            "errors": errors,
            "json": None,
        }
    command_argv = [str(part) for part in action["command_argv"]]
    return run_json_command(command_argv, timeout=60)


def confirmed_task_details(confirmed_send_result: dict[str, Any] | None) -> dict[str, Any]:
    payload = confirmed_send_result.get("json") if isinstance(confirmed_send_result, dict) else None
    if not isinstance(payload, dict):
        return {
            "created": False,
            "task_id": None,
            "message_path": None,
            "message_ready_to_send": False,
            "structured_import_ready": False,
        }
    message = payload.get("chatgpt_message")
    message_path = None
    structured_import_ready = False
    if isinstance(message, dict):
        message_path = message.get("output")
        structured_import_ready = bool(message.get("structured_import_ready"))
    return {
        "created": bool(payload.get("task_id")),
        "task_id": payload.get("task_id"),
        "message_path": message_path,
        "message_ready_to_send": bool(message_path and structured_import_ready),
        "structured_import_ready": structured_import_ready,
    }


def post_chatgpt_result_actions(confirmed_details: dict[str, Any]) -> dict[str, Any]:
    task_id = confirmed_details.get("task_id")
    has_task = bool(confirmed_details.get("created"))
    response_blockers = [] if has_task else ["confirmed_task_created"]
    response_blockers.extend(["task_bound_message_sent", "chatgpt_response_available"])
    pull_command = result_script_argv(PULL_RESULT_SCRIPT, task_id, "--json")
    intake_preview_command = skill_script_argv(INTAKE_RESULT_SCRIPT, "--stdin", "--json", "--repo-root", str(ROOT))
    intake_confirm_command = skill_script_argv(INTAKE_RESULT_SCRIPT, "--stdin", "--yes", "--json", "--repo-root", str(ROOT))
    import_command = skill_script_argv(IMPORT_RESULT_SCRIPT, "--stdin", "--repo-root", str(ROOT))
    review_command = result_script_argv(REVIEW_RESULT_SCRIPT, task_id, "--json")
    return {
        "pull_full_connector_result": {
            "id": "pull_full_connector_result",
            "purpose": "Full Connector 已真实写回时，从本地 Bridge 拉取结果。",
            "command_argv": pull_command,
            "command": shlex.join(pull_command),
            "requires_real_task_id": True,
            "task_id": task_id,
            "enabled": False,
            "enabled_after_chatgpt_response": has_task,
            "blocked_until": response_blockers,
            "requires_user_confirmation_before_pull": True,
            "does_not_prove_full_connector": True,
            "writes_external_evidence": False,
            "auto_execute": False,
        },
        "import_fenced_result_json": {
            "id": "import_fenced_result_json",
            "purpose": "写回工具不可用时，先预检 ChatGPT 输出的 fenced codex-bridge-result-json；用户确认后才导入。",
            "command_argv": intake_preview_command,
            "command": shlex.join(intake_preview_command),
            "confirmed_import_command_argv": intake_confirm_command,
            "confirmed_import_command": shlex.join(intake_confirm_command),
            "low_level_import_command_argv": import_command,
            "stdin_format": "fenced codex-bridge-result-json",
            "requires_real_task_id_in_payload": True,
            "requires_user_confirmation_before_import": True,
            "preview_before_import": True,
            "enabled": False,
            "enabled_after_chatgpt_response": has_task,
            "blocked_until": response_blockers,
            "writes_external_evidence": False,
            "writes_local_result_on_preview": False,
            "writes_local_result_after_confirmation": True,
            "auto_execute": False,
        },
        "review_imported_or_pulled_result": {
            "id": "review_imported_or_pulled_result",
            "purpose": "把拉取或导入的右侧结果转换为 Codex 审阅清单。",
            "command_argv": review_command,
            "command": shlex.join(review_command),
            "requires_result_import_or_pull": True,
            "requires_review_before_execution": True,
            "enabled": False,
            "blocked_until": ["result_imported_or_pulled"],
            "execution_allowed_by_this_action": False,
            "suggested_actions_require_user_confirmation": True,
            "auto_execute": False,
        },
        "user_approval_before_execution": {
            "id": "user_approval_before_execution",
            "purpose": "用户逐条确认审阅清单后，Codex 才能另行执行最小修改或命令。",
            "command_argv": None,
            "requires_review_result_output": True,
            "requires_user_confirmation": True,
            "enabled": False,
            "blocked_until": ["review_result_output", "user_confirmation"],
            "right_side_can_edit_source": False,
            "right_side_can_run_shell": False,
            "auto_execute": False,
        },
    }


def browser_handoff(
    *,
    open_action: dict[str, Any],
    send_action: dict[str, Any],
    sync_action: dict[str, Any],
    result_actions: dict[str, Any],
    confirmed_details: dict[str, Any],
) -> dict[str, Any]:
    has_task = bool(confirmed_details.get("created"))
    message_ready = bool(confirmed_details.get("message_ready_to_send"))
    blocked_until: list[str] = []
    if not has_task:
        blocked_until.append("confirmed_task_created")
    if not message_ready:
        blocked_until.append("task_bound_message_ready")
    return {
        "id": "browser_handoff",
        "purpose": "用户授权后，打开官方 ChatGPT 并发送当前 session 的 task-bound 消息。",
        "enabled": message_ready,
        "blocked_until": blocked_until,
        "requires_user_permission": True,
        "permission_prompt": open_action.get(
            "permission_prompt",
            "是否允许我打开 ChatGPT 网页，发送这次任务单 / 审查请求，并把 ChatGPT 回复带回 Codex 审阅？",
        ),
        "browser_assist_runtime_check_required": True,
        "open_url": open_action.get("url"),
        "target_surface": open_action.get("target_surface", "official_chatgpt_conversation"),
        "opens_connector_settings": False,
        "uses_dom_scraping": False,
        "reads_or_saves_cookies": False,
        "task_id": confirmed_details.get("task_id"),
        "message_path": confirmed_details.get("message_path"),
        "message_ready_to_send": message_ready,
        "requires_task_bound_message": True,
        "requires_user_confirmation_before_send": True,
        "sends_context_without_user_confirmation": False,
        "auto_open_chatgpt": False,
        "auto_send_to_chatgpt": False,
        "auto_execute": False,
        "writes_external_evidence": False,
        "does_not_prove_connector": True,
        "actions_in_order": [
            "open_chatgpt_after_task_created",
            "send_task_bound_message",
            "sync_structured_result",
            "review_imported_or_pulled_result",
            "user_approval_before_execution",
        ],
        "open_action": {
            "id": open_action.get("id", "open_official_chatgpt"),
            "enabled": bool(open_action.get("enabled")),
            "blocked_until": open_action.get("blocked_until", []),
            "url": open_action.get("url"),
        },
        "send_action": {
            "id": send_action.get("id", "send_task_bound_message"),
            "enabled": bool(send_action.get("enabled")),
            "blocked_until": send_action.get("blocked_until", []),
            "task_id": send_action.get("task_id"),
            "message_path": send_action.get("message_path"),
        },
        "sync_action": {
            "id": sync_action.get("id", "sync_structured_result"),
            "enabled": bool(sync_action.get("enabled")),
            "enabled_after_chatgpt_response": bool(sync_action.get("enabled_after_chatgpt_response")),
            "blocked_until": sync_action.get("blocked_until", []),
            "intake_result_command_argv": sync_action.get("intake_result_command_argv"),
            "confirm_import_result_command_argv": sync_action.get("confirm_import_result_command_argv"),
            "review_result_command_argv": sync_action.get("review_result_command_argv"),
        },
        "post_chatgpt_result_actions": {
            "pull_full_connector_result": result_actions["pull_full_connector_result"],
            "import_fenced_result_json": result_actions["import_fenced_result_json"],
            "review_imported_or_pulled_result": result_actions["review_imported_or_pulled_result"],
            "user_approval_before_execution": result_actions["user_approval_before_execution"],
        },
        "not_proven_by_this_handoff": [
            "真实 ChatGPT 已打开",
            "真实 ChatGPT 已收到 task-bound 消息",
            "真实 ChatGPT Connector 工具可用",
            "真实 read/write smoke 已通过",
            "真实外部 evidence verified",
        ],
    }


def progress_step(step_id: str, label: str, status: str) -> dict[str, str]:
    return {"id": step_id, "label": label, "status": status}


def user_guidance_for_phase(phase: str) -> dict[str, Any]:
    if phase == "local_preflight_failed":
        return {
            "current_prompt": "现在先不要打开 ChatGPT；请让 Codex 处理本地检查失败项。",
            "why_now": "本地检查没有通过时，发送给 ChatGPT 只会让协同变得不可追踪。",
            "what_user_should_do": ["等待 Codex 展示失败项。", "只确认和本地修复直接相关的动作。"],
            "what_codex_will_do": ["整理失败原因。", "只修阻断协同启动的问题。"],
            "if_stuck": ["如果看不到失败详情，先查看本地检查结果。", "不要复制源码或账号信息到 ChatGPT。"],
            "success_state": "本地检查通过后，再进入发送内容确认。",
        }
    if phase == "dry_run_preview_only":
        return {
            "current_prompt": "现在只是查看流程；下一步让 Codex 准备发送内容确认。",
            "why_now": "先看清会发送什么，避免把无关上下文或敏感信息带给 ChatGPT。",
            "what_user_should_do": ["确认你要让 ChatGPT 协助规划或审查。", "等 Codex 展示发送内容后再决定是否继续。"],
            "what_codex_will_do": ["准备最小任务内容。", "发送前再次提示你确认。"],
            "if_stuck": ["如果你不确定要不要继续，就先停在这里。", "不要自己去拼本地命令或复制隐藏文件。"],
            "success_state": "你看到发送内容确认后，再决定是否生成 ChatGPT 消息。",
        }
    if phase == "needs_user_confirmation_to_create_task":
        return {
            "current_prompt": "现在只需要确认：是否允许 Codex 生成要发给 ChatGPT 的任务单。",
            "why_now": "这样 ChatGPT 只处理这次任务，并且回复能回到 Codex 审阅链路。",
            "what_user_should_do": ["确认发送内容不含敏感信息。", "确认后等待 Codex 生成 ChatGPT 消息。"],
            "what_codex_will_do": ["创建本次协同任务。", "生成可发送给 ChatGPT 的任务单。", "不会打开网页或发送内容。"],
            "if_stuck": ["如果不确定内容是否安全，先让 Codex 重新展示发送内容。", "如果你没有确认，Codex 不会继续发送。"],
            "success_state": "状态变为可以打开 ChatGPT 协同。",
        }
    if phase == "ready_to_open_chatgpt":
        return {
            "current_prompt": "现在只需要确认：是否允许打开 ChatGPT 并发送这次任务单。",
            "why_now": "任务单已准备好；发送后 ChatGPT 可以先做规划或审查，Codex 再负责接收和审阅。",
            "what_user_should_do": ["确认允许打开官方 ChatGPT 页面。", "发送后等待 ChatGPT 回复。"],
            "what_codex_will_do": ["只打开官方 ChatGPT。", "只发送这次任务单。", "不会读取账号信息或保存 cookie。"],
            "if_stuck": ["如果 ChatGPT 没回复，停在当前对话等待。", "如果 ChatGPT 说工具不可用，就让它按固定格式回复，再交给 Codex 检查。"],
            "success_state": "ChatGPT 回复后，回到 Codex 接收并生成审阅清单。",
        }
    if phase == "confirmed_send_failed":
        return {
            "current_prompt": "生成 ChatGPT 消息失败；现在不要打开 ChatGPT 或发送内容。",
            "why_now": "失败状态下发送内容会让结果无法安全回收。",
            "what_user_should_do": ["查看失败详情。", "等待 Codex 修复生成消息的问题。"],
            "what_codex_will_do": ["定位失败原因。", "只修复生成协同消息所需的问题。"],
            "if_stuck": ["如果失败详情为空，先重新运行本地检查。", "不要手动把未确认内容发给 ChatGPT。"],
            "success_state": "重新生成消息成功后，再请求你确认打开 ChatGPT。",
        }
    return {
        "current_prompt": "当前协同状态未知；请先查看状态详情。",
        "why_now": "状态不明确时不应继续发送上下文。",
        "what_user_should_do": ["先停下，不要发送内容。"],
        "what_codex_will_do": ["重新检查协同状态。"],
        "if_stuck": ["让 Codex 重新生成协同状态卡。"],
        "success_state": "状态卡给出明确下一步。",
    }


def result_guidance_for_state(task_ready: bool) -> dict[str, Any]:
    if task_ready:
        return {
            "current_prompt": "ChatGPT 回复后，让 Codex 先接收并检查回复，再生成审阅清单。",
            "why_now": "ChatGPT 的内容只是建议，必须先经过 Codex 审阅，不能直接执行。",
            "what_user_should_do": ["等待 ChatGPT 完成回复。", "让 Codex 接收回复。", "只确认你真正要执行的单条建议。"],
            "what_codex_will_do": ["优先自动接收回复。", "自动接收不可用时检查你带回的回复。", "生成审阅清单。"],
            "if_stuck": ["如果自动接收不可用，把 ChatGPT 的完整回复带回 Codex 检查。", "如果回复不完整，让 ChatGPT 重新按固定格式输出。"],
            "success_state": "你看到审阅清单，并逐条决定是否执行建议。",
        }
    return {
        "current_prompt": "还没有可接收的 ChatGPT 回复；先完成前面的发送步骤。",
        "why_now": "只有本次任务对应的回复，才能进入 Codex 审阅链路。",
        "what_user_should_do": ["先生成 ChatGPT 消息。", "确认后再打开 ChatGPT 并发送。"],
        "what_codex_will_do": ["等待可发送的任务单。", "不会接收无关对话内容。"],
        "if_stuck": ["如果已经有 ChatGPT 回复，但不是这次任务生成的，先不要带回 Codex。", "重新从当前状态卡开始。"],
        "success_state": "发送完成并看到 ChatGPT 回复后，进入接收和审阅。",
    }


def build_user_view(
    *,
    phase: str,
    next_step: str,
    state: dict[str, Any],
    confirm_action: dict[str, Any],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    local_ok = bool(state.get("local_preflight_ok"))
    preview_ready = bool(state.get("preview_ready"))
    task_ready = bool(state.get("task_bound_message_ready_to_send"))

    if phase == "local_preflight_failed":
        headline = "本地检查未通过"
        summary = "Codex 需要先修复本地检查失败项，再生成 ChatGPT 协同消息。"
        primary_action = {
            "id": "review_local_preflight",
            "label": "查看本地检查结果",
            "enabled": False,
            "action_ref": "first_use_summary.failed_steps",
            "blocked_until": ["local_preflight_ok"],
            "requires_user_confirmation": False,
        }
    elif phase == "dry_run_preview_only":
        headline = "准备 ChatGPT 协同预览"
        summary = "当前只是在查看将要发生什么；下一步由 Codex 准备发送前确认。"
        primary_action = {
            "id": "prepare_collaboration_preview",
            "label": "生成协同预览",
            "enabled": True,
            "action_ref": "session_command_argv",
            "command_argv": script_argv("--json"),
            "blocked_until": [],
            "requires_user_confirmation": False,
        }
    elif phase == "needs_user_confirmation_to_create_task":
        headline = "确认后生成 ChatGPT 协同消息"
        summary = "请先确认发送前预览；确认后 Codex 只创建 Bridge 任务和绑定任务的 ChatGPT 消息。"
        primary_action = {
            "id": "confirm_create_task_and_message",
            "label": "确认预览并生成 ChatGPT 消息",
            "enabled": bool(confirm_action.get("available")),
            "action_ref": "ui_actions.confirm_create_task_and_message",
            "command_argv": confirm_action.get("command_argv"),
            "blocked_until": [] if confirm_action.get("available") else ["preview_ready"],
            "requires_user_confirmation": True,
        }
    elif phase == "ready_to_open_chatgpt":
        headline = "可以打开 ChatGPT 协同"
        summary = "已生成绑定真实任务的 ChatGPT 消息；用户授权后 Codex 可协助打开官方 ChatGPT 并发送。"
        primary_action = {
            "id": "authorize_browser_handoff",
            "label": "打开 ChatGPT 并发送任务单",
            "enabled": bool(handoff.get("enabled")),
            "action_ref": "browser_handoff",
            "open_url": handoff.get("open_url"),
            "message_path": handoff.get("message_path"),
            "blocked_until": handoff.get("blocked_until", []),
            "requires_user_confirmation": True,
        }
    elif phase == "confirmed_send_failed":
        headline = "生成协同消息失败"
        summary = "确认创建任务或生成 ChatGPT 消息失败；不要打开 ChatGPT 或发送上下文。"
        primary_action = {
            "id": "review_confirmed_send_failure",
            "label": "查看失败详情",
            "enabled": False,
            "action_ref": "confirmed_send_result",
            "blocked_until": ["confirmed_send_ok"],
            "requires_user_confirmation": False,
        }
    else:
        headline = "ChatGPT 协同状态"
        summary = next_step
        primary_action = {
            "id": "inspect_session_state",
            "label": "查看当前状态",
            "enabled": False,
            "action_ref": "ui_actions",
            "blocked_until": ["known_phase"],
            "requires_user_confirmation": False,
        }

    create_status = "done" if task_ready else "current" if phase == "needs_user_confirmation_to_create_task" else "waiting"
    open_status = "current" if phase == "ready_to_open_chatgpt" else "waiting"
    receive_status = "waiting" if task_ready else "blocked"
    review_status = "waiting" if task_ready else "blocked"
    guidance = user_guidance_for_phase(phase)

    return {
        "id": "ordinary_user_collaboration_card",
        "audience": "ordinary_user",
        "title": "让 ChatGPT 协助规划 / 审查",
        "headline": headline,
        "summary": summary,
        "next_step": next_step,
        "current_prompt": guidance["current_prompt"],
        "why_now": guidance["why_now"],
        "what_user_should_do": guidance["what_user_should_do"],
        "what_codex_will_do": guidance["what_codex_will_do"],
        "if_stuck": guidance["if_stuck"],
        "success_state": guidance["success_state"],
        "primary_action": primary_action,
        "progress_steps": [
            progress_step("local_preflight", "本地检查", "done" if local_ok else "blocked"),
            progress_step("preview_context", "准备发送内容", "done" if preview_ready else "blocked"),
            progress_step("create_task_message", "确认并生成协同消息", create_status),
            progress_step("open_and_send_chatgpt", "打开 ChatGPT 并发送", open_status),
            progress_step("receive_structured_result", "接收 ChatGPT 回复", receive_status),
            progress_step("review_before_execution", "Codex 审阅后再确认执行", review_status),
        ],
        "internal_modes_hidden": True,
        "internal_terms_hidden": True,
        "local_user_shell_commands_required": False,
        "fallback_summary": "自动接收不可用时，Codex 会先检查 ChatGPT 回复；只有自动协同不可用时才使用人工兜底。",
        "reminders": [
            "你只需要确认当前这一步，不需要理解底层模式。",
            "看不懂下一步时，停在状态卡，不要自己复制隐藏文件。",
            "任何发送、保存结果或执行建议都会再次请求你确认。",
        ],
        "guardrails": [
            "不会读取或保存 cookie、密码、token 或私钥。",
            "不会在用户确认前发送上下文。",
            "ChatGPT 不能直接改源码或执行 shell。",
            "ChatGPT 建议必须经 Codex 审阅并由用户确认后才执行。",
            "不会把未验证的外部能力标成可用。",
        ],
        "external_capability_verified_by_this_view": False,
        "developer_details_ref": "ui_actions",
    }


def build_result_view(*, state: dict[str, Any], result_actions: dict[str, Any]) -> dict[str, Any]:
    task_ready = bool(state.get("task_bound_message_ready_to_send"))
    task_id = state.get("task_id")
    if task_ready:
        headline = "等待 ChatGPT 回复"
        summary = "ChatGPT 回复后，Codex 先自动接收；不可用时先检查复制回来的回复，再生成审阅清单。"
        primary_action = {
            "id": "receive_chatgpt_result_after_response",
            "label": "接收 ChatGPT 回复",
            "enabled": False,
            "enabled_after_chatgpt_response": True,
            "action_ref": "ui_actions.post_chatgpt_result_actions",
            "blocked_until": ["task_bound_message_sent", "chatgpt_response_available"],
            "requires_user_confirmation": True,
        }
    else:
        headline = "等待可回收的协同消息"
        summary = "先生成绑定当前任务的协同消息；没有绑定当前任务的 ChatGPT 回复不能进入 Codex 审阅链路。"
        primary_action = {
            "id": "wait_for_task_bound_message",
            "label": "先生成 ChatGPT 协同消息",
            "enabled": False,
            "enabled_after_chatgpt_response": False,
            "action_ref": "user_view.primary_action",
            "blocked_until": ["confirmed_task_created", "task_bound_message_ready"],
            "requires_user_confirmation": False,
        }

    pull_action = result_actions["pull_full_connector_result"]
    import_action = result_actions["import_fenced_result_json"]
    review_action = result_actions["review_imported_or_pulled_result"]
    approval_action = result_actions["user_approval_before_execution"]
    guidance = result_guidance_for_state(task_ready)
    return {
        "id": "ordinary_user_result_sync_card",
        "audience": "ordinary_user",
        "title": "接收 ChatGPT 结果",
        "headline": headline,
        "summary": summary,
        "current_prompt": guidance["current_prompt"],
        "why_now": guidance["why_now"],
        "what_user_should_do": guidance["what_user_should_do"],
        "what_codex_will_do": guidance["what_codex_will_do"],
        "if_stuck": guidance["if_stuck"],
        "success_state": guidance["success_state"],
        "task_id": task_id,
        "requires_real_task_id": True,
        "response_required": True,
        "primary_action": primary_action,
        "visible_steps": [
            progress_step("receive_chatgpt_response", "接收 ChatGPT 回复", "waiting" if task_ready else "blocked"),
            progress_step("check_result", "检查回复内容", "waiting" if task_ready else "blocked"),
            progress_step("review_result", "生成审阅清单", "waiting" if task_ready else "blocked"),
            progress_step("approve_execution", "用户确认后再执行", "blocked"),
        ],
        "result_actions_in_order": [
            "pull_full_connector_result",
            "import_fenced_result_json",
            "review_imported_or_pulled_result",
            "user_approval_before_execution",
        ],
        "collection_options": {
            "official_mcp_result_pull": {
                "label": "自动接收 ChatGPT 回复",
                "action_ref": "ui_actions.post_chatgpt_result_actions.pull_full_connector_result",
                "command_argv": pull_action.get("command_argv"),
                "enabled": bool(pull_action.get("enabled")),
                "enabled_after_chatgpt_response": bool(pull_action.get("enabled_after_chatgpt_response")),
                "blocked_until": pull_action.get("blocked_until", []),
                "requires_user_confirmation": bool(pull_action.get("requires_user_confirmation_before_pull")),
                "does_not_prove_full_connector": bool(pull_action.get("does_not_prove_full_connector")),
            },
            "fenced_json_intake": {
                "label": "检查 ChatGPT 复制回来的回复",
                "action_ref": "ui_actions.post_chatgpt_result_actions.import_fenced_result_json",
                "preview_command_argv": import_action.get("command_argv"),
                "confirmed_import_command_argv": import_action.get("confirmed_import_command_argv"),
                "enabled": bool(import_action.get("enabled")),
                "enabled_after_chatgpt_response": bool(import_action.get("enabled_after_chatgpt_response")),
                "blocked_until": import_action.get("blocked_until", []),
                "requires_user_confirmation": bool(import_action.get("requires_user_confirmation_before_import")),
                "preview_before_import": bool(import_action.get("preview_before_import")),
                "writes_local_result_on_preview": bool(import_action.get("writes_local_result_on_preview")),
            },
        },
        "review_action": {
            "label": "生成 Codex 审阅清单",
            "action_ref": "ui_actions.post_chatgpt_result_actions.review_imported_or_pulled_result",
            "command_argv": review_action.get("command_argv"),
            "enabled": bool(review_action.get("enabled")),
            "blocked_until": review_action.get("blocked_until", []),
            "execution_allowed_by_this_action": bool(review_action.get("execution_allowed_by_this_action")),
            "requires_review_before_execution": bool(review_action.get("requires_review_before_execution")),
        },
        "execution_gate": {
            "label": "用户确认后才执行建议",
            "action_ref": "ui_actions.post_chatgpt_result_actions.user_approval_before_execution",
            "enabled": bool(approval_action.get("enabled")),
            "blocked_until": approval_action.get("blocked_until", []),
            "requires_user_confirmation": bool(approval_action.get("requires_user_confirmation")),
            "auto_execute": bool(approval_action.get("auto_execute")),
            "right_side_can_edit_source": bool(approval_action.get("right_side_can_edit_source")),
            "right_side_can_run_shell": bool(approval_action.get("right_side_can_run_shell")),
        },
        "guardrails": [
            "ChatGPT 回复是不可信建议。",
            "检查回复不会把内容保存为本地结果。",
            "接收回复、保存结果和执行建议都需要用户确认。",
            "审阅清单只整理建议，不修改代码或执行命令。",
            "不会把网页回复当成已验证外部能力。",
        ],
        "reminders": [
            "没有审阅清单，就不要执行 ChatGPT 建议。",
            "保存结果不是批准执行。",
            "如果回复不完整，先让 ChatGPT 重新回答。",
        ],
        "internal_terms_hidden": True,
        "writes_external_evidence": False,
        "external_capability_verified_by_this_view": False,
        "auto_execute": False,
        "developer_details_ref": "ui_actions.post_chatgpt_result_actions",
    }


def build_session(
    first_use: dict[str, Any],
    *,
    dry_run: bool,
    confirmed_send_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    first_use_ok = bool(first_use.get("ok"))
    confirmed_details = confirmed_task_details(confirmed_send_result)
    confirmed_executed = confirmed_send_result is not None
    confirmed_ok = bool(confirmed_send_result.get("ok")) if isinstance(confirmed_send_result, dict) else None
    confirmed_errors = confirmed_send_result.get("errors", []) if isinstance(confirmed_send_result, dict) else []
    browser_actions = first_use.get("chatgpt_browser_collaboration_actions")
    if not isinstance(browser_actions, dict):
        browser_actions = {}

    if not first_use_ok:
        phase = "local_preflight_failed"
        next_step = "先查看本地检查失败项，由 Codex 修复后再继续。"
    elif dry_run:
        phase = "dry_run_preview_only"
        next_step = "下一步由 Codex 准备真实发送预览和确认按钮。"
    elif confirmed_details["created"]:
        phase = "ready_to_open_chatgpt"
        next_step = "请确认是否打开官方 ChatGPT 页面，并发送这次任务单或审查请求。"
    elif confirmed_executed and not confirmed_ok:
        phase = "confirmed_send_failed"
        next_step = "先修复生成协同消息失败项；不要打开 ChatGPT 或发送上下文。"
    else:
        phase = "needs_user_confirmation_to_create_task"
        next_step = "请确认发送前预览；确认后 Codex 生成可发送给 ChatGPT 的消息。"

    preview_action = first_use.get("chatgpt_preview_action")
    confirmed_action = first_use.get("chatgpt_confirmed_send_action")
    confirm_session_action = {
        "id": "confirm_create_task_and_message",
        "command_argv": script_argv("--yes", "--json"),
        "command": shlex.join(script_argv("--yes", "--json")),
        "requires_user_confirmation": True,
        "confirmation_source": "chatgpt_preview_action",
        "creates_real_bridge_task": True,
        "generates_task_bound_chatgpt_message": True,
        "auto_open_chatgpt": False,
        "auto_send_to_chatgpt": False,
        "auto_execute": False,
        "available": bool(isinstance(confirmed_action, dict) and confirmed_action.get("available")),
        "delegates_to": "chatgpt_confirmed_send_action.command_argv",
    }

    open_action = dict(browser_actions.get("open_official_chatgpt", {}))
    open_action.update(
        {
            "enabled": bool(confirmed_details["created"]),
            "blocked_until": [] if confirmed_details["created"] else ["confirmed_task_created"],
            "recommended_after": "confirm_create_task_and_message",
        }
    )
    send_action = dict(browser_actions.get("send_task_bound_message", {}))
    send_action.update(
        {
            "enabled": bool(confirmed_details["message_ready_to_send"]),
            "blocked_until": [] if confirmed_details["message_ready_to_send"] else ["task_bound_message_ready"],
            "task_id": confirmed_details["task_id"],
            "message_path": confirmed_details["message_path"],
            "requires_user_confirmation_before_send": True,
        }
    )
    sync_action = dict(browser_actions.get("sync_structured_result", {}))
    result_actions = post_chatgpt_result_actions(confirmed_details)
    sync_blockers = [] if confirmed_details["created"] else ["confirmed_task_created"]
    sync_blockers.extend(["task_bound_message_sent", "chatgpt_response_available"])
    sync_action.update(
        {
            "enabled": False,
            "enabled_after_chatgpt_response": bool(confirmed_details["created"]),
            "blocked_until": sync_blockers,
            "post_chatgpt_result_actions": list(result_actions),
            "requires_review_result_before_execution": True,
            "suggested_actions_require_user_confirmation": True,
            "pull_result_command_argv": result_actions["pull_full_connector_result"]["command_argv"],
            "intake_result_command_argv": result_actions["import_fenced_result_json"]["command_argv"],
            "confirm_import_result_command_argv": result_actions["import_fenced_result_json"]["confirmed_import_command_argv"],
            "low_level_import_result_command_argv": result_actions["import_fenced_result_json"]["low_level_import_command_argv"],
            "review_result_command_argv": result_actions["review_imported_or_pulled_result"]["command_argv"],
            "auto_execute": False,
        }
    )
    handoff = browser_handoff(
        open_action=open_action,
        send_action=send_action,
        sync_action=sync_action,
        result_actions=result_actions,
        confirmed_details=confirmed_details,
    )
    state = {
        "local_preflight_ok": first_use_ok,
        "preview_ready": isinstance(preview_action, dict) and bool(preview_action.get("available")),
        "confirmed_send_executed": confirmed_executed,
        "confirmed_send_ok": confirmed_ok,
        "confirmed_task_created": confirmed_details["created"],
        "task_id": confirmed_details["task_id"],
        "task_bound_message_path": confirmed_details["message_path"],
        "task_bound_message_ready_to_send": confirmed_details["message_ready_to_send"],
        "full_connector_verified_by_this_session": False,
        "external_evidence_written_by_this_session": False,
    }

    return {
        "ok": first_use_ok and (confirmed_ok is not False),
        "title": "ChatGPT 自动化协同会话状态",
        "audience": "普通用户 UI / Codex",
        "default_mode": "automated_collaboration",
        "dry_run": dry_run,
        "phase": phase,
        "ordinary_user_next_step": next_step,
        "ordinary_user_journey": compact_journey_for_status(),
        "local_user_shell_commands_required": False,
        "session_command_argv": script_argv("--json"),
        "confirm_session_command_argv": script_argv("--yes", "--json"),
        "state": state,
        "user_view": build_user_view(
            phase=phase,
            next_step=next_step,
            state=state,
            confirm_action=confirm_session_action,
            handoff=handoff,
        ),
        "result_view": build_result_view(state=state, result_actions=result_actions),
        "ui_actions": {
            "preview": preview_action,
            "confirm_create_task_and_message": confirm_session_action,
            "open_chatgpt_after_task_created": open_action,
            "send_task_bound_message": send_action,
            "sync_structured_result": sync_action,
            "browser_handoff": handoff,
            "post_chatgpt_result_actions": result_actions,
        },
        "browser_handoff": handoff,
        "first_use_summary": {
            "ok": first_use_ok,
            "failed_steps": first_use.get("failed_steps", []),
            "next_user_confirmation": first_use.get("next_user_confirmation"),
            "next_external_evidence_confirmation": first_use.get("next_external_evidence_confirmation"),
        },
        "confirmed_send_result": {
            "ok": confirmed_ok,
            "errors": confirmed_errors,
            "task": confirmed_details,
        }
        if confirmed_executed
        else None,
        "right_side_contract": {
            "chatgpt_role": "不可信规划 / 审计协作者",
            "codex_role": "主执行器，负责改代码、运行命令和验证",
            "right_side_can_edit_source": False,
            "right_side_can_run_shell": False,
            "suggested_actions_require_user_confirmation": True,
        },
        "safety": {
            "opens_only_official_chatgpt": open_action.get("url") == OFFICIAL_CHATGPT_URL,
            "opens_connector_settings": False,
            "uses_dom_scraping": False,
            "reads_or_saves_cookies": False,
            "sends_context_without_user_confirmation": False,
            "auto_executes_chatgpt_suggestions": False,
            "pulls_result_without_user_confirmation": False,
            "imports_result_without_user_confirmation": False,
            "reviews_result_before_execution": True,
            "records_real_connector_evidence_without_user_confirmation": False,
        },
        "not_proven_by_this_session": [
            "真实 ChatGPT 已收到并处理任务单 / 审查请求",
            "真实 ChatGPT Connector 工具列表已刷新",
            "真实 tools/call bridge_pull_task",
            "真实 tools/call bridge_fetch_task_packet",
            "真实 tools/call bridge_send_result",
            "真实外部 evidence verified",
        ],
    }


def visible_status_label(status: object) -> str:
    labels = {
        "done": "已完成",
        "current": "当前步骤",
        "waiting": "等待",
        "blocked": "暂不可用",
    }
    return labels.get(str(status), "等待")


def render_markdown(session: dict[str, Any]) -> str:
    user_view = session["user_view"]
    result_view = session["result_view"]
    lines = [
        "# ChatGPT 自动化协同会话状态",
        "",
        "## 当前协同",
        "",
        f"- 目标：{user_view['title']}",
        f"- 状态：{user_view['headline']}",
        f"- 下一步：{user_view['summary']}",
        f"- 主按钮：{user_view['primary_action']['label']}（{'可用' if user_view['primary_action']['enabled'] else '不可用'}）",
        "",
        "## 你现在只需要",
        "",
        f"- {user_view['current_prompt']}",
    ]
    for item in user_view.get("what_user_should_do", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 为什么这一步",
            "",
            f"- {user_view['why_now']}",
        ]
    )
    for item in user_view.get("what_codex_will_do", []):
        lines.append(f"- Codex 会：{item}")
    lines.extend(
        [
            "",
            "## 完整流程",
            "",
        ]
    )
    for item in session.get("ordinary_user_journey", []):
        if isinstance(item, dict):
            marker = "用户确认" if item.get("requires_user_action") else "Codex 自动"
            lines.append(f"- {item.get('step')}. {item.get('title')}：{marker}；{item.get('done_when')}")
    lines.extend(
        [
            "",
            "## 进度",
            "",
        ]
    )
    for step in user_view.get("progress_steps", []):
        if isinstance(step, dict):
            lines.append(f"- {step.get('label')}：{visible_status_label(step.get('status'))}")

    lines.extend(
        [
            "",
            "## ChatGPT 回复",
            "",
            f"- 状态：{result_view['headline']}",
            f"- 下一步：{result_view['summary']}",
            f"- 主按钮：{result_view['primary_action']['label']}（{'可用' if result_view['primary_action']['enabled'] else '等待 ChatGPT 回复或当前任务'}）",
            f"- 提醒：{result_view['current_prompt']}",
            "",
            "## 回复处理",
            "",
        ]
    )
    for step in result_view.get("visible_steps", []):
        if isinstance(step, dict):
            lines.append(f"- {step.get('label')}：{visible_status_label(step.get('status'))}")

    lines.extend(
        [
            "",
            "## 如果卡住",
            "",
        ]
    )
    for item in user_view.get("if_stuck", []):
        lines.append(f"- {item}")
    for item in result_view.get("if_stuck", []):
        if item not in user_view.get("if_stuck", []):
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 成功标志",
            "",
            f"- {user_view['success_state']}",
            f"- {result_view['success_state']}",
            "",
            "## 提醒",
            "",
        ]
    )
    for item in user_view.get("reminders", []):
        lines.append(f"- {item}")
    for item in result_view.get("reminders", []):
        if item not in user_view.get("reminders", []):
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 安全边界",
            "",
        ]
    )
    for guardrail in user_view.get("guardrails", []):
        lines.append(f"- {guardrail}")
    for guardrail in result_view.get("guardrails", []):
        if guardrail not in user_view.get("guardrails", []):
            lines.append(f"- {guardrail}")

    lines.extend(
        [
            "- ChatGPT 网页协同和外部能力验证仍需要单独确认。",
            "- 这个状态页不会把未验证的外部能力标成可用。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a UI-ready ChatGPT collaboration session state.")
    parser.add_argument("--dry-run", action="store_true", help="Only show the no-side-effect first-use plan.")
    parser.add_argument("--yes", action="store_true", help="After user confirmation, create the real Bridge task and task-bound message.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=SESSION_OUTPUT)
    args = parser.parse_args()

    first_use_command = run_first_use(dry_run=args.dry_run)
    first_use = first_use_command.get("json") if isinstance(first_use_command.get("json"), dict) else {}
    if first_use_command["ok"] and not first_use:
        first_use = {"ok": False, "failed_steps": [{"id": "verify_first_use_json", "summary": "无法解析 JSON 输出。"}]}
    elif not first_use_command["ok"]:
        first_use = {
            "ok": False,
            "failed_steps": [
                {
                    "id": "verify_first_use",
                    "summary": "一键首次验证失败。",
                    "returncode": first_use_command["returncode"],
                    "stderr_tail": first_use_command["stderr_tail"],
                }
            ],
        }

    confirmed_send_result = execute_confirmed_send(first_use) if args.yes and not args.dry_run else None
    session = build_session(first_use, dry_run=args.dry_run, confirmed_send_result=confirmed_send_result)

    output_path = Path(args.output)
    output_path = output_path if output_path.is_absolute() else ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(session), encoding="utf-8")
    session["output"] = str(output_path)

    if args.json:
        print(json.dumps(session, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(session))
        print("已生成协同状态页。")
    return 0 if session["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
