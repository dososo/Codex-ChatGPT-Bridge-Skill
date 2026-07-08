#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from _bootstrap import ROOT
from bridge.codex_config import (
    ACTIVE_CONFIG_REL,
    SERVER_NAME,
    SNIPPET_REL,
    install_codex_mcp_active_config,
    inspect_codex_mcp_config,
    user_codex_config_path,
    write_codex_mcp_snippet,
)
from bridge.ordinary_journey import (
    codex_auto_responsibilities,
    ordinary_user_journey,
    user_required_responsibilities,
)
from bridge.redaction import redact_text
from bridge.state import BridgeState


SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_TITLE = "首次验证"
DEFAULT_GOAL = "验证 Codex ChatGPT Bridge Skill 能否自动完成本地首次使用检查，并生成安全的下一步。"
TASK_BRIEF_MODE = "plan"
FIRST_USE_OUTPUT_ROOT = ROOT / ".ai-bridge-test-runs" / "first-use"
TASK_BRIEF_MESSAGE_OUTPUT = ".ai-bridge-test-runs/first-use/chatgpt-task-brief-message.md"
OFFICIAL_CHATGPT_URL = "https://chatgpt.com/"
COLLABORATION_MATERIALS = [
    {
        "id": "chatgpt_browser_assist",
        "label": "ChatGPT 网页协助包",
        "script": "build_chatgpt_browser_assist_packet.py",
        "filename": "chatgpt-browser-assist.md",
    },
    {
        "id": "authorized_browser_session_plan",
        "label": "授权后自动化协同会话计划",
        "script": "build_authorized_browser_session_plan.py",
        "filename": "authorized-browser-session-plan.md",
    },
    {
        "id": "chatgpt_task_brief_message",
        "label": "可发送给 ChatGPT 的任务单消息",
        "script": "build_chatgpt_collaboration_message.py",
        "filename": "chatgpt-task-brief-message.md",
        "args": ["--mode", "task-brief"],
    },
    {
        "id": "chatgpt_review_message",
        "label": "可发送给 ChatGPT 的审查消息",
        "script": "build_chatgpt_collaboration_message.py",
        "filename": "chatgpt-review-message.md",
        "args": ["--mode", "review"],
    },
]
LOCAL_STEP_IDS = [
    "clinic",
    "setup",
    "codex_mcp_config",
    "start_bridge",
    "status",
    "mcp_probe",
    "local_read_smoke",
    "local_write_smoke",
    "preview_task",
    "chatgpt_collaboration_materials",
    "packet_fallback",
]


def run_script(script_name: str, args: list[str], *, timeout: int = 30) -> dict[str, Any]:
    command = script_command(script_name, args)
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    stdout = redact_text(proc.stdout.strip(), BridgeState(ROOT).token_values())
    stderr = redact_text(proc.stderr.strip(), BridgeState(ROOT).token_values())
    parsed: Any = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "json": parsed,
    }


def script_command(script_name: str, args: list[str]) -> list[str]:
    return [sys.executable, str(SCRIPTS_DIR / script_name), *args]


def run_root_script(script_name: str, args: list[str], *, timeout: int = 30) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "scripts" / script_name), *args]
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    stdout = redact_text(proc.stdout.strip(), BridgeState(ROOT).token_values())
    stderr = redact_text(proc.stderr.strip(), BridgeState(ROOT).token_values())
    parsed: Any = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "json": parsed,
    }


def step_result(
    *,
    step_id: str,
    title: str,
    status: str,
    auto_completed: bool,
    summary: str,
    command_result: dict[str, Any] | None = None,
    user_action_required: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": step_id,
        "title": title,
        "status": status,
        "auto_completed": auto_completed,
        "user_action_required": user_action_required,
        "summary": summary,
    }
    if command_result is not None:
        result["returncode"] = command_result["returncode"]
        result["developer_command"] = " ".join(str(part) for part in command_result["command"])
        if not command_result["ok"]:
            result["stdout_tail"] = command_result["stdout"][-800:]
            result["stderr_tail"] = command_result["stderr"][-800:]
    if details:
        result["details"] = details
    return result


def dry_run_result(title: str, goal: str) -> dict[str, Any]:
    steps = [
        step_result(
            step_id=step_id,
            title=title_text,
            status="planned",
            auto_completed=False,
            summary="实际运行时由 Skill 自动完成，不需要普通用户手动敲命令。",
        )
        for step_id, title_text in [
            ("clinic", "读取能力门诊"),
            ("setup", "初始化当前仓库"),
            ("codex_mcp_config", "安装本地 Codex 连接配置"),
            ("start_bridge", "启动本地 Bridge"),
            ("status", "检查 Bridge 状态"),
            ("mcp_probe", "发现本地工具"),
            ("local_read_smoke", "本地读取预检"),
            ("local_write_smoke", "本地回传预检"),
            ("preview_task", "生成发送前预览"),
            ("chatgpt_collaboration_materials", "生成 ChatGPT 协同材料"),
            ("packet_fallback", "生成最后兜底材料"),
        ]
    ]
    return build_result(
        ok=True,
        dry_run=True,
        title=title,
        goal=goal,
        steps=steps,
        local_summary="这是 dry-run，只展示一键验证会自动完成哪些本地步骤。",
        collaboration_materials=planned_collaboration_materials(),
    )


def install_codex_config_if_safe(port: int) -> dict[str, Any]:
    write_codex_mcp_snippet(ROOT, port)
    repo_install = install_codex_mcp_active_config(
        ROOT,
        port,
        active_config_path=ROOT / ACTIVE_CONFIG_REL,
        write=True,
    )
    user_install = install_codex_mcp_active_config(
        ROOT,
        port,
        active_config_path=user_codex_config_path(),
        write=True,
    )
    after = inspect_codex_mcp_config(ROOT, port)
    ok = bool(repo_install["ok"] and user_install["ok"] and after["active_uses_stdio_command"])
    blocked = [item for item in (repo_install, user_install) if not item["ok"]]
    if blocked:
        summary = "检测到本地连接配置存在需要用户确认的风险，已停止自动覆盖。"
        status = "needs_user_confirmation"
    elif repo_install["changed"] or user_install["changed"]:
        summary = f"已自动安装 {SERVER_NAME} 的本地连接配置，使用本地启动方式，不依赖 GUI 环境变量。"
        status = "ok"
    else:
        summary = "仓库和用户级 Codex 本地连接配置已可用。"
        status = "skipped"
    return {
        "ok": ok,
        "status": status,
        "summary": summary,
        "codex_mcp": after,
        "repo_active_install": repo_install,
        "user_active_install": user_install,
    }


def wait_for_bridge(timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last = run_script("status.py", ["--json"], timeout=10)
    while time.time() < deadline:
        payload = last.get("json")
        if isinstance(payload, dict) and isinstance(payload.get("bridge"), dict) and payload["bridge"].get("running"):
            return last
        time.sleep(0.5)
        last = run_script("status.py", ["--json"], timeout=10)
    return last


def planned_collaboration_materials() -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    for material in COLLABORATION_MATERIALS:
        path = FIRST_USE_OUTPUT_ROOT / str(material["filename"])
        materials.append(build_material_summary(material, path=path, generated=False, payload={}))
    return materials


def default_material_capability_flags(material_id: str) -> dict[str, Any]:
    if material_id in {"chatgpt_browser_assist", "authorized_browser_session_plan"}:
        return {
            "draft_only_without_task_id": True,
            "structured_import_ready_without_task_id": False,
            "task_bound_message_builder_available": True,
            "task_bound_requires_real_task_id": True,
            "task_bound_structured_import_ready_after_confirmed_send": True,
            "draft_messages_importable": False,
            "auto_send_to_chatgpt": False,
            "auto_execute": False,
        }
    if material_id in {"chatgpt_task_brief_message", "chatgpt_review_message"}:
        return {
            "task_id_status": "missing",
            "requires_real_task_id_for_import": True,
            "structured_import_ready": False,
            "sends_context": False,
            "auto_execute": False,
        }
    return {}


def material_capability_flags(material_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    flags = default_material_capability_flags(material_id)
    for key in (
        "task_id_status",
        "requires_real_task_id_for_import",
        "structured_import_ready",
        "sends_context",
        "auto_execute",
    ):
        if key in payload:
            flags[key] = payload.get(key)

    collaboration_builder = payload.get("collaboration_message_builder")
    if isinstance(collaboration_builder, dict):
        for key in ("draft_only_without_task_id", "structured_import_ready_without_task_id"):
            if key in collaboration_builder:
                flags[key] = collaboration_builder.get(key)

    task_bound_builder = payload.get("task_bound_message_builder")
    if isinstance(task_bound_builder, dict):
        flags["task_bound_message_builder_available"] = True
        flags["task_bound_requires_real_task_id"] = task_bound_builder.get("requires_real_task_id")
        flags["task_bound_structured_import_ready_after_confirmed_send"] = task_bound_builder.get(
            "structured_import_ready_after_confirmed_send"
        )
        flags["draft_messages_importable"] = task_bound_builder.get("draft_messages_importable")
        flags["task_bound_requires_user_confirmation_before_send"] = task_bound_builder.get(
            "requires_user_confirmation_before_send"
        )
        flags["auto_send_to_chatgpt"] = task_bound_builder.get("auto_send_to_chatgpt")
        flags["auto_execute"] = task_bound_builder.get("auto_execute")
    return flags


def build_material_summary(
    material: dict[str, Any],
    *,
    path: Path,
    generated: bool,
    payload: dict[str, Any],
) -> dict[str, Any]:
    material_id = str(material["id"])
    requires_user_permission = payload.get(
        "requires_user_permission",
        payload.get("requires_user_confirmation_before_send"),
    )
    if requires_user_permission is None:
        requires_user_permission = True
    requires_send_confirmation = payload.get("requires_user_confirmation_before_send")
    if requires_send_confirmation is None and material_id in {"chatgpt_task_brief_message", "chatgpt_review_message"}:
        requires_send_confirmation = True
    mode = payload.get("mode")
    if mode is None and material_id == "chatgpt_task_brief_message":
        mode = "task-brief"
    elif mode is None and material_id == "chatgpt_review_message":
        mode = "review"
    summary = {
        "id": material_id,
        "label": material["label"],
        "path": str(path),
        "exists": path.is_file(),
        "generated": generated,
        "default_mode": payload.get("default_mode", "automated_collaboration"),
        "requires_user_permission": requires_user_permission,
        "requires_user_confirmation_before_send": requires_send_confirmation,
        "mode": mode,
    }
    summary.update(material_capability_flags(material_id, payload))
    return summary


def build_task_brief_preview_goal(goal: str) -> str:
    return (
        "请先不要写代码。请把下面这次需求整理成适合 Codex 执行的任务单，"
        "包含原始问题、预期结果、不能改变的行为、可能涉及的文件、最小修改方案、"
        "验证命令、需要停止并询问用户的情况；结构化回传时 result_type 必须是 task_brief，"
        f"并填写 task_brief 对象。需求：{goal}"
    )


def build_preview_args(title: str, goal: str) -> list[str]:
    return [
        "--title",
        title,
        "--goal",
        build_task_brief_preview_goal(goal),
        "--mode",
        TASK_BRIEF_MODE,
        "--chatgpt-message-mode",
        "task-brief",
        "--chatgpt-message-output",
        TASK_BRIEF_MESSAGE_OUTPUT,
        "--preview",
    ]


def build_preview_action(preview_command: list[Any], preview_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    preview_argv = [str(part) for part in preview_command]
    payload = preview_payload or {}
    send_requires_yes = payload.get("send_requires_yes")
    return {
        "id": "prepare_chatgpt_task_brief_preview",
        "available": bool(send_requires_yes) if send_requires_yes is not None else True,
        "command_argv": preview_argv,
        "command": shlex.join(preview_argv),
        "preview_only": True,
        "mode": payload.get("mode", TASK_BRIEF_MODE),
        "send_requires_yes": bool(send_requires_yes) if send_requires_yes is not None else True,
        "creates_real_bridge_task": False,
        "generates_task_bound_chatgpt_message": False,
        "requires_user_confirmation_to_preview": False,
        "requires_user_confirmation_before_send": True,
        "auto_send_to_chatgpt": False,
        "auto_execute": False,
    }


def build_confirmed_send_action(preview_command: list[Any], preview_payload: dict[str, Any]) -> dict[str, Any]:
    confirmed_argv = ["--yes" if str(part) == "--preview" else str(part) for part in preview_command]
    return {
        "id": "confirm_send_task_bound_chatgpt_message",
        "available": bool(preview_payload.get("send_requires_yes")),
        "requires_user_confirmation": True,
        "confirmation_source_step": "preview_task",
        "command_argv": confirmed_argv,
        "command": shlex.join(confirmed_argv),
        "creates_real_bridge_task": True,
        "generates_task_bound_chatgpt_message": bool(
            preview_payload.get("post_confirmation_chatgpt_message", {}).get("available")
            if isinstance(preview_payload.get("post_confirmation_chatgpt_message"), dict)
            else False
        ),
        "requires_real_task_id": True,
        "structured_import_ready_after_confirmed_send": True,
        "auto_send_to_chatgpt": False,
        "auto_execute": False,
    }


def build_collaboration_materials(title: str, goal: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    FIRST_USE_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    materials: list[dict[str, Any]] = []
    command_results: list[dict[str, Any]] = []
    for material in COLLABORATION_MATERIALS:
        path = FIRST_USE_OUTPUT_ROOT / str(material["filename"])
        command_args = [*list(material.get("args", [])), "--output", str(path), "--json"]
        if material["script"] == "build_chatgpt_collaboration_message.py":
            command_args.extend(["--title", title, "--request", goal])
        command_result = run_root_script(
            str(material["script"]),
            command_args,
            timeout=30,
        )
        command_results.append(command_result)
        payload = command_result.get("json") if isinstance(command_result.get("json"), dict) else {}
        materials.append(
            build_material_summary(
                material,
                path=path,
                generated=command_result["ok"] and path.is_file(),
                payload=payload,
            )
        )
    return materials, command_results


def build_browser_assist_action() -> dict[str, Any]:
    prompt = "是否允许我打开 ChatGPT 网页，发送这次任务单 / 审查请求，并把 ChatGPT 回复带回 Codex 审阅？"
    return {
        "id": "chatgpt_collaboration_browser_assist",
        "title": "让 ChatGPT 协助任务单 / 审查",
        "prompt": prompt,
        "primary_user_goal": "让 ChatGPT Pro 生成 Codex 执行任务单或审查 Codex 执行结果。",
        "requires_user_permission": True,
        "requires_user_confirmation": True,
        "can_be_done_by_codex_with_browser_or_computer_use": True,
        "browser_assist_runtime_check_required": True,
        "auto_execute": False,
        "user_prompt": prompt,
        "requires_separate_confirmation_for": [
            "创建或修改 ChatGPT Connector / App。",
            "刷新工具列表或执行真实外部验证。",
            "写入真实外部证据。",
            "执行 ChatGPT 建议、运行命令或应用 patch。",
        ],
        "will_do": [
            "先打开官方 ChatGPT 页面并发送用户确认过的任务单 / 审查请求。",
            "优先让 ChatGPT Pro 生成 Codex 执行任务单或审查 Codex 执行结果。",
            "能自动同步时优先同步；不能同步时让 ChatGPT 按固定格式回复，再由 Codex 接收审阅。",
        ],
        "will_not_do": [
            "不会读取或保存 cookie、密码、账号信息。",
            "不会把完整 Connector URL、token 或 cookie 写进聊天、日志或仓库。",
            "不会在你确认前发送源码上下文给 ChatGPT。",
            "不会在本次授权里做账号/工具配置、写入外部证据或执行能力验证。",
            "不会执行 ChatGPT 回传的命令或自动应用 patch。",
        ],
        "fallback_if_not_allowed": "Codex 仍保留脱敏协同材料；人工带回只作为最后兜底。",
    }


def build_browser_collaboration_actions(browser_prompt: str) -> dict[str, Any]:
    return {
        "open_official_chatgpt": {
            "id": "open_official_chatgpt",
            "url": OFFICIAL_CHATGPT_URL,
            "target_surface": "official_chatgpt_conversation",
            "requires_user_permission": True,
            "permission_prompt": browser_prompt,
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
            "task_bound_message_output": TASK_BRIEF_MESSAGE_OUTPUT,
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


def load_root_script(filename: str) -> Any:
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_next_external_confirmation_action() -> dict[str, Any]:
    fallback = build_browser_assist_action()
    local_evidence_files = [
        ROOT / ".ai-bridge" / "connector-capability.local.json",
        ROOT / ".ai-bridge" / "readiness.local.json",
        ROOT / ".ai-bridge" / "metrics.local.json",
    ]
    if not all(path.exists() for path in local_evidence_files):
        fallback["source"] = "fallback"
        fallback["fallback_reason"] = "local_evidence_files_missing"
        return fallback
    try:
        doctor = load_root_script("release_evidence_doctor.py")
        next_card = load_root_script("build_next_external_step_card.py")
        result = doctor.build_release_evidence_doctor(
            external_evidence_file=ROOT / ".ai-bridge" / "connector-capability.local.json",
            production_readiness_file=ROOT / ".ai-bridge" / "readiness.local.json",
            success_metrics_file=ROOT / ".ai-bridge" / "metrics.local.json",
            action_limit=5,
        )
        actions = result.get("recommended_next_actions", [])
        action = actions[0] if actions else {}
        if not isinstance(action, dict) or not action:
            return fallback
        action_id = str(action.get("id", "unknown"))
        guidance = getattr(next_card, "ACTION_GUIDANCE", {}).get(action_id, {})
        prompt = str(guidance.get("prompt") or "是否允许我继续处理下一条真实外部证据？")
        browser_needed = action_id in {
            "chatgpt_connector_created",
            "chatgpt_tools_discovered",
            "real_read_smoke",
            "real_write_smoke",
        }
        will_do = list(action.get("codex_auto_steps", [])) or [
            "自动生成当前外部证据的脱敏诊断或证据材料。",
        ]
        return {
            "id": action_id,
            "title": action.get("title", "下一条外部证据"),
            "prompt": prompt,
            "user_prompt": prompt,
            "requires_user_permission": True,
            "requires_user_confirmation": True,
            "can_be_done_by_codex_with_browser_or_computer_use": browser_needed,
            "browser_assist_runtime_check_required": browser_needed,
            "auto_execute": False,
            "current_status": action.get("current_status"),
            "why": action.get("why"),
            "will_do": will_do,
            "user_confirmation_steps": list(action.get("user_confirmation_steps", [])),
            "done_when": action.get("done_when"),
            "will_not_do": [
                "不会要求普通用户手动复制本地命令。",
                "不会读取或保存 ChatGPT cookie、密码、账号信息。",
                "不会记录完整 Connector URL、token、.env、私钥或 .git 内容。",
                "不会把本地诊断或 packet 生成冒充成真实外部证据。",
                "不会执行 ChatGPT 回传的命令或自动应用 patch。",
            ],
            "fallback_if_not_allowed": "暂不处理该外部证据，继续使用本地预检和人工带回兜底。",
            "source": "release_evidence_doctor",
        }
    except Exception as exc:  # pragma: no cover - fallback is defensive for packaged installs.
        fallback["source"] = "fallback"
        fallback["fallback_reason"] = str(exc)
        return fallback


def build_result(
    *,
    ok: bool,
    dry_run: bool,
    title: str,
    goal: str,
    steps: list[dict[str, Any]],
    local_summary: str,
    collaboration_materials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    failed_steps = [step for step in steps if step["status"] == "failed"]
    user_action_steps = [step for step in steps if step.get("user_action_required")]
    browser_assist_action = build_browser_assist_action()
    preview_action = build_preview_action(script_command("push_task.py", build_preview_args(title, goal)))
    confirmed_send_action: dict[str, Any] | None = None
    for step in steps:
        if step.get("id") != "preview_task" or not isinstance(step.get("details"), dict):
            continue
        details = step["details"]
        step_preview_action = details.get("preview_action")
        if isinstance(step_preview_action, dict):
            preview_action = step_preview_action
        step_confirmed_send_action = details.get("confirmed_send_action")
        if isinstance(step_confirmed_send_action, dict):
            confirmed_send_action = step_confirmed_send_action
    return {
        "ok": ok,
        "audience": "普通用户第一次使用",
        "dry_run": dry_run,
        "title": title,
        "goal": goal,
        "local_user_shell_commands_required": False,
        "local_automated_step_ids": LOCAL_STEP_IDS,
        "local_summary": local_summary,
        "ordinary_user_journey": ordinary_user_journey(),
        "codex_auto_responsibilities": codex_auto_responsibilities(),
        "user_required_responsibilities": user_required_responsibilities(),
        "steps": steps,
        "failed_steps": failed_steps,
        "user_action_steps": user_action_steps,
        "chatgpt_collaboration_materials": collaboration_materials or planned_collaboration_materials(),
        "chatgpt_preview_action": preview_action,
        "chatgpt_confirmed_send_action": confirmed_send_action,
        "next_user_confirmation": browser_assist_action,
        "next_external_evidence_confirmation": build_next_external_confirmation_action(),
        "chatgpt_browser_assist_action": browser_assist_action,
        "chatgpt_browser_collaboration_actions": build_browser_collaboration_actions(
            str(browser_assist_action["user_prompt"])
        ),
        "safety": {
            "right_side_chatgpt_can_edit_source": False,
            "right_side_chatgpt_can_execute_shell": False,
            "suggested_actions_need_user_confirmation": True,
            "sends_context_without_user_confirmation": False,
            "records_real_connector_evidence_without_user_confirmation": False,
        },
    }


def verify_first_use(*, title: str, goal: str, dry_run: bool = False, timeout_seconds: int = 12) -> dict[str, Any]:
    if dry_run:
        return dry_run_result(title, goal)

    steps: list[dict[str, Any]] = []

    clinic = run_script("first_run.py", ["--json"], timeout=20)
    clinic_summary = "已读取能力门诊。" if clinic["ok"] else "能力门诊读取失败。"
    steps.append(
        step_result(
            step_id="clinic",
            title="读取能力门诊",
            status="ok" if clinic["ok"] else "failed",
            auto_completed=clinic["ok"],
            summary=clinic_summary,
            command_result=clinic,
            details={"recommended_path": (clinic.get("json") or {}).get("recommended_path")} if isinstance(clinic.get("json"), dict) else None,
        )
    )

    setup_needed = not (ROOT / ".ai-bridge" / "config.json").exists()
    if setup_needed:
        setup = run_script("setup.py", ["--json"], timeout=20)
        steps.append(
            step_result(
                step_id="setup",
                title="初始化当前仓库",
                status="ok" if setup["ok"] else "failed",
                auto_completed=setup["ok"],
                summary="已自动初始化当前仓库的 Bridge 状态和本地 token 文件。" if setup["ok"] else "初始化失败。",
                command_result=setup,
            )
        )
    else:
        steps.append(
            step_result(
                step_id="setup",
                title="初始化当前仓库",
                status="skipped",
                auto_completed=True,
                summary="当前仓库已初始化，不需要用户处理。",
            )
        )

    state = BridgeState(ROOT)
    config = state.init_state()
    port = int(config.get("port", 8765))
    codex_config = install_codex_config_if_safe(port)
    steps.append(
            step_result(
                step_id="codex_mcp_config",
                title="安装本地 Codex 连接配置",
                status=str(codex_config["status"]),
                auto_completed=bool(codex_config["ok"]),
                user_action_required=not bool(codex_config["ok"]),
            summary=str(codex_config["summary"]),
            details={"codex_mcp": codex_config["codex_mcp"]},
        )
    )

    status_before = run_script("status.py", ["--json"], timeout=10)
    bridge_running = False
    if isinstance(status_before.get("json"), dict):
        bridge = status_before["json"].get("bridge")
        bridge_running = isinstance(bridge, dict) and bool(bridge.get("running"))

    if bridge_running:
        steps.append(
            step_result(
                step_id="start_bridge",
                title="启动本地 Bridge",
                status="skipped",
                auto_completed=True,
                summary="本地 Bridge 已在运行。",
            )
        )
        status_after = status_before
    else:
        started = run_script("start_bridge.py", [], timeout=20)
        status_after = wait_for_bridge(timeout_seconds)
        running_after = False
        if isinstance(status_after.get("json"), dict):
            bridge = status_after["json"].get("bridge")
            running_after = isinstance(bridge, dict) and bool(bridge.get("running"))
        steps.append(
            step_result(
                step_id="start_bridge",
                title="启动本地 Bridge",
                status="ok" if started["ok"] and running_after else "failed",
                auto_completed=started["ok"] and running_after,
                summary="已自动启动 localhost Bridge。" if started["ok"] and running_after else "Bridge 启动后未确认运行。",
                command_result=started if not (started["ok"] and running_after) else None,
                details={"port": port},
            )
        )

    status_payload = status_after.get("json") if isinstance(status_after.get("json"), dict) else {}
    running = isinstance(status_payload.get("bridge"), dict) and bool(status_payload["bridge"].get("running"))
    steps.append(
        step_result(
            step_id="status",
            title="检查 Bridge 状态",
            status="ok" if running else "failed",
            auto_completed=running,
            summary="Bridge 正在运行。" if running else "Bridge 还没有运行。",
            command_result=status_after,
            details={"bridge": status_payload.get("bridge")} if status_payload else None,
        )
    )

    can_probe = running
    probe = run_script("mcp_probe.py", ["--json"], timeout=20) if can_probe else None
    tools = []
    if probe and isinstance(probe.get("json"), dict) and isinstance(probe["json"].get("tools"), list):
        tools = list(probe["json"]["tools"])
    steps.append(
        step_result(
            step_id="mcp_probe",
            title="发现本地工具",
            status="ok" if probe and probe["ok"] else "skipped" if not can_probe else "failed",
            auto_completed=bool(probe and probe["ok"]),
            summary=f"已发现 {len(tools)} 个本地工具。" if probe and probe["ok"] else "Bridge 未运行，跳过工具发现。" if not can_probe else "本地工具发现失败。",
            command_result=probe,
            details={"tools": tools} if tools else None,
        )
    )

    read_smoke = run_script("smoke_test.py", ["--read"], timeout=20) if can_probe else None
    steps.append(
        step_result(
            step_id="local_read_smoke",
            title="本地读取预检",
            status="ok" if read_smoke and read_smoke["ok"] else "skipped" if not can_probe else "failed",
            auto_completed=bool(read_smoke and read_smoke["ok"]),
            summary="本地读取预检通过；这还不是 ChatGPT 真实 Connector 证据。" if read_smoke and read_smoke["ok"] else "跳过本地读取预检。" if not can_probe else "本地读取预检失败。",
            command_result=read_smoke,
        )
    )

    write_smoke = run_script("smoke_test.py", ["--write"], timeout=20) if can_probe else None
    steps.append(
        step_result(
            step_id="local_write_smoke",
            title="本地回传预检",
            status="ok" if write_smoke and write_smoke["ok"] else "skipped" if not can_probe else "failed",
            auto_completed=bool(write_smoke and write_smoke["ok"]),
            summary="本地回传预检通过；不会把本地结果冒充成真实 ChatGPT 证据。" if write_smoke and write_smoke["ok"] else "跳过本地回传预检。" if not can_probe else "本地回传预检失败。",
            command_result=write_smoke,
        )
    )

    preview = run_script("push_task.py", build_preview_args(title, goal), timeout=20)
    preview_payload = preview.get("json") if isinstance(preview.get("json"), dict) else {}
    steps.append(
        step_result(
            step_id="preview_task",
            title="生成发送前预览",
            status="ok" if preview["ok"] and preview_payload.get("send_requires_yes") else "failed",
            auto_completed=preview["ok"] and bool(preview_payload.get("send_requires_yes")),
            summary="已生成发送前预览；没有发送给 ChatGPT。" if preview["ok"] else "发送前预览失败。",
            command_result=preview,
            details={
                "send_requires_yes": preview_payload.get("send_requires_yes"),
                "mode": preview_payload.get("mode"),
                "allowed_files_count": preview_payload.get("allowed_files_count"),
                "preview_action": build_preview_action(preview["command"], preview_payload),
                "post_confirmation_chatgpt_message": preview_payload.get("post_confirmation_chatgpt_message"),
                "confirmed_send_action": build_confirmed_send_action(preview["command"], preview_payload),
            } if preview_payload else None,
        )
    )

    collaboration_materials, collaboration_results = build_collaboration_materials(title, goal)
    collaboration_ok = all(item["generated"] for item in collaboration_materials)
    steps.append(
        step_result(
            step_id="chatgpt_collaboration_materials",
            title="生成 ChatGPT 协同材料",
            status="ok" if collaboration_ok else "failed",
            auto_completed=collaboration_ok,
            summary=(
                "已生成 ChatGPT 网页协助包、授权后自动化协同会话计划和可发送协同消息；没有打开浏览器或发送上下文。"
                if collaboration_ok
                else "ChatGPT 协同材料生成失败。"
            ),
            command_result=next((item for item in collaboration_results if not item["ok"]), None),
            details={"generated_files": collaboration_materials},
        )
    )

    packet = run_script("build_packet.py", ["--title", title, "--goal", goal], timeout=20)
    packet_payload = packet.get("json") if isinstance(packet.get("json"), dict) else {}
    steps.append(
        step_result(
            step_id="packet_fallback",
            title="生成最后兜底材料",
            status="ok" if packet["ok"] else "failed",
            auto_completed=packet["ok"],
            summary="已生成脱敏兜底材料；没有自动上传给 ChatGPT。" if packet["ok"] else "兜底材料生成失败。",
            command_result=packet,
            details={"packet_markdown": packet_payload.get("packet_markdown"), "packet_zip": packet_payload.get("packet_zip")} if packet_payload else None,
        )
    )

    failed = [step for step in steps if step["status"] == "failed"]
    blocked = [step for step in steps if step["status"] == "needs_user_confirmation"]
    if failed:
        summary = "本地自动验证有失败项，普通用户不需要手动敲命令；请把结果交给 Codex 或维护者处理。"
    elif blocked:
        summary = "本地验证已自动完成到安全边界；剩余本地配置冲突需要用户确认。"
    else:
        summary = "本地首次使用验证已自动完成。下一步是请求用户授权 ChatGPT 任务单 / 审查协同；发布证据下一项保留在机器可读输出中。"
    return build_result(
        ok=not failed and not blocked,
        dry_run=False,
        title=title,
        goal=goal,
        steps=steps,
        local_summary=summary,
        collaboration_materials=collaboration_materials,
    )


def render_text(result: dict[str, Any]) -> str:
    lines = ["# Codex ChatGPT Bridge 首次使用一键验证", ""]
    lines.append(result["local_summary"])
    lines.append("")
    lines.append("本地自动完成情况：")
    for step in result["steps"]:
        status = str(step["status"])
        if status == "ok":
            label = "完成"
        elif status == "skipped":
            label = "已具备"
        elif status == "planned":
            label = "将自动执行"
        elif status == "needs_user_confirmation":
            label = "需要确认"
        else:
            label = "失败"
        lines.append(f"- {label}：{step['title']}。{step['summary']}")
    lines.extend(
        [
            "",
            "你现在不用手动敲本地命令。",
            "",
            "已准备的 ChatGPT 协同材料：",
        ]
    )
    for material in result["chatgpt_collaboration_materials"]:
        generated = "已生成" if material.get("generated") or material.get("exists") else "将生成"
        lines.append(f"- {generated}：{material['label']}，`{material['path']}`")
    lines.extend(["", "完整流程："])
    for item in result.get("ordinary_user_journey", []):
        if not isinstance(item, dict):
            continue
        marker = "用户确认" if item.get("requires_user_action") else "Codex 自动"
        lines.append(f"{item.get('step')}. {item.get('title')}（{marker}）")
        lines.append(f"   你会看到：{item.get('what_user_sees')}")
        lines.append(f"   完成标志：{item.get('done_when')}")
    lines.extend(["", "你只需要参与这些动作："])
    for item in result.get("user_required_responsibilities", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "下一步需要用户确认：",
            f"- {result['next_user_confirmation']['user_prompt']}",
            "",
            "我会做：",
        ]
    )
    for item in result["next_user_confirmation"]["will_do"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("我不会做：")
    for item in result["next_user_confirmation"]["will_not_do"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            f"如果暂不确认：{result['next_user_confirmation']['fallback_if_not_allowed']}",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="普通用户首次使用一键验证。")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="只展示将自动执行的本地步骤，不启动 Bridge 或写入文件。")
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--goal", default=DEFAULT_GOAL)
    parser.add_argument("--timeout-seconds", type=int, default=12)
    args = parser.parse_args()

    result = verify_first_use(
        title=args.title,
        goal=args.goal,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
