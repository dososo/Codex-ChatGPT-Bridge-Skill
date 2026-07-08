#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import socket
from typing import Any

from _bootstrap import ROOT
from bridge.capabilities import FULL_CONNECTOR, PACKET_OR_MANUAL, READ_ONLY_CONNECTOR, capability_evidence_status
from bridge.codex_config import inspect_codex_mcp_config
from bridge.ordinary_journey import (
    codex_auto_responsibilities,
    ordinary_user_journey,
    user_required_responsibilities,
)
from bridge.schema_status import connector_schema_status
from bridge.state import BridgeState
from status import remote_token_status


PLAN_CAPABILITY_NOTE = (
    "不要按账号名称承诺能力；个人 Pro 常见只能作为 read/fetch 候选，"
    "Full Connector 必须由真实 ChatGPT full MCP write smoke 证明。"
)
ORDINARY_PLAN_CAPABILITY_NOTE = "不要按账号名称承诺能力；个人 Pro 也需要按当前真实验证结果选择可用协同方式。"
READ_ONLY_PACKET_OR_MANUAL = "read_only_packet_or_manual"
AUTOMATED_COLLABORATION = "automated_collaboration"
AUTOMATED_COLLABORATION_LABEL = "ChatGPT 任务单 / 审查协同"
AUTOMATED_COLLABORATION_TASK_MODE = "plan"
AUTOMATED_COLLABORATION_MESSAGE_MODE = "task-brief"
AUTOMATED_COLLABORATION_MESSAGE_OUTPUT = ".ai-bridge-test-runs/first-use/chatgpt-task-brief-message.md"
TASK_BRIEF_GOAL = (
    "请先不要写代码。请把这次需求整理成适合 Codex 执行的任务单，"
    "包含原始问题、预期结果、不能改变的行为、可能涉及的文件、最小修改方案、"
    "验证命令、需要停止并询问用户的情况；结构化回传时 result_type 必须是 task_brief，"
    "并填写 task_brief 对象。"
)
REPO_ROOT_CLI = shlex.quote(str(ROOT))
PULL_RESULT_COMMAND = (
    "python .agents/skills/codex-chatgpt-bridge/scripts/pull_result.py "
    f"--json --repo-root {REPO_ROOT_CLI}"
)
INTAKE_RESULT_COMMAND = f"python scripts/intake_chatgpt_result.py --stdin --json --repo-root {REPO_ROOT_CLI}"
REVIEW_RESULT_COMMAND = (
    "python .agents/skills/codex-chatgpt-bridge/scripts/review_result.py "
    f"--repo-root {REPO_ROOT_CLI}"
)


def port_running(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def action(
    action_id: str,
    title: str,
    why: str,
    command: str | None = None,
    manual: str | None = None,
    confirmation: str | None = None,
) -> dict[str, object]:
    return {
        "id": action_id,
        "title": title,
        "why": why,
        "command": command,
        "manual": manual,
        "requires_user_confirmation": confirmation is not None,
        "confirmation": confirmation,
        "auto_execute": False,
    }


def automated_collaboration_push_task_argv(*, preview: bool) -> list[str]:
    final_flag = "--preview" if preview else "--yes"
    return [
        "python",
        ".agents/skills/codex-chatgpt-bridge/scripts/push_task.py",
        "--title",
        AUTOMATED_COLLABORATION_LABEL,
        "--goal",
        TASK_BRIEF_GOAL,
        "--mode",
        AUTOMATED_COLLABORATION_TASK_MODE,
        "--chatgpt-message-mode",
        AUTOMATED_COLLABORATION_MESSAGE_MODE,
        "--chatgpt-message-output",
        AUTOMATED_COLLABORATION_MESSAGE_OUTPUT,
        final_flag,
    ]


def automated_collaboration_push_task_command(*, preview: bool) -> str:
    return shlex.join(automated_collaboration_push_task_argv(preview=preview))


def automated_collaboration_confirmed_send_action() -> dict[str, object]:
    return {
        "id": "confirm_send_task_bound_chatgpt_message",
        "title": "确认后创建真实任务并生成 task-bound 消息",
        "command_argv": automated_collaboration_push_task_argv(preview=False),
        "command": automated_collaboration_push_task_command(preview=False),
        "requires_user_confirmation": True,
        "confirmation": "只有用户确认 preview 不含 secrets、.env、私钥、cookie、.git 或完整 Connector URL 后，Codex 才能执行该动作。",
        "creates_real_bridge_task": True,
        "generates_task_bound_chatgpt_message": True,
        "requires_real_task_id": True,
        "structured_import_ready_after_confirmed_send": True,
        "auto_send_to_chatgpt": False,
        "auto_execute": False,
    }


def guide_step(
    step_id: str,
    title: str,
    plain_language_instruction: str,
    completion_check: str,
    command: str | None = None,
    manual: str | None = None,
    user_confirmation: str | None = None,
    fallback: str | None = None,
) -> dict[str, object]:
    return {
        "id": step_id,
        "title": title,
        "plain_language_instruction": plain_language_instruction,
        "command": command,
        "manual": manual,
        "completion_check": completion_check,
        "requires_user_confirmation": user_confirmation is not None,
        "user_confirmation": user_confirmation,
        "fallback": fallback,
        "auto_execute": False,
    }


def quick_start_targets() -> dict[str, object]:
    return {
        "clinic_minutes": 5,
        "install_to_capability_minutes": 15,
        "first_linkage_minutes": 20,
        "requires_real_user_evidence_for_release": True,
    }


def user_paths() -> list[dict[str, object]]:
    return [
        {
            "mode": FULL_CONNECTOR,
            "label": "Full Connector",
            "when_to_use": "真实 read/write smoke 都通过，右侧 ChatGPT 可以读取任务并写回结果；通常需要 Business / Enterprise / Edu 或等价 full MCP 写权限。",
            "first_step": "先 `push_task.py --preview` 预览上下文，确认后再改用 `--yes` 发送。",
            "confirmation": "回传结果只作为建议，执行 patch 或命令前必须由用户再次确认。",
        },
        {
            "mode": READ_ONLY_CONNECTOR,
            "label": "Read-only Connector",
            "when_to_use": "真实 read smoke 通过，但写回不可用或没有证据；个人 Pro 常见只能到 read/fetch，需要手动导入结果。",
            "first_step": "优先让右侧 ChatGPT 调用 `bridge_fetch_task_packet` 只读读取任务；写回不可用时输出 fenced JSON，Codex 从 session 状态卡读取 repo-bound intake 动作预检。",
            "confirmation": "预检通过后由用户确认导入，再从状态卡运行 repo-bound review 动作；不能自动执行建议。",
        },
        {
            "mode": "packet",
            "label": "Packet fallback",
            "when_to_use": "Connector、tunnel 或账号能力不确定，但用户可以上传脱敏 packet。",
            "first_step": "运行 `build_packet.py`，自查 markdown 后再上传给 ChatGPT。",
            "confirmation": "上传前确认 packet 不含 secrets、完整 Connector URL、`.env`、私钥、cookie 或 `.git` 内容。",
        },
        {
            "mode": "manual",
            "label": "Manual fallback",
            "when_to_use": "不能或不想启动 Connector，只能复制粘贴最小上下文。",
            "first_step": "让 ChatGPT 输出 `codex-bridge-result-json` fenced JSON，Codex 从 session 状态卡读取 repo-bound intake 动作预检，确认后再导入。",
            "confirmation": "所有 findings、patch 和 suggested_actions 都是不可信建议，审阅后再决定是否执行。",
        },
    ]


def prd_first_use_flow() -> list[dict[str, object]]:
    flow: list[dict[str, object]] = [
        {
            "id": "install_skill",
            "prd_step": "用户安装 Skill 到 .agents/skills/codex-chatgpt-bridge/",
            "user_action": "确认当前仓库存在 `.agents/skills/codex-chatgpt-bridge/SKILL.md`。",
            "local_evidence": "能力门诊的 summary.skill 显示已发现。",
            "completion_check": "Skill 文件在仓库级路径可读。",
            "requires_user_confirmation": False,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "explicit_skill_invocation",
            "prd_step": "用户在 Codex 左侧显式调用 Skill",
            "user_action": "在 Codex 左侧显式调用 `codex-chatgpt-bridge`，先运行 `first_run.py` 能力门诊。",
            "local_evidence": "本脚本是 Skill 被选中后的首次入口。",
            "completion_check": "用户能看到能力门诊、推荐路径和确认点。",
            "requires_user_confirmation": False,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "run_doctor",
            "prd_step": "Codex 运行 doctor.py --json",
            "user_action": "运行 `python .agents/skills/codex-chatgpt-bridge/scripts/doctor.py --json`。",
            "local_evidence": "onboarding_guide.doctor 和 next_actions.run_doctor 都指向 doctor。",
            "completion_check": "用户看过 required_actions，并知道下一步处理顺序。",
            "requires_user_confirmation": False,
            "external_evidence_required": False,
            "auto_execute": False,
        },
        {
            "id": "run_setup",
            "prd_step": "Codex 运行 setup.py，创建 .ai-bridge/",
            "user_action": "用户确认后运行 `setup.py --json`，只写入当前仓库的 `.ai-bridge/` 和配置片段。",
            "local_evidence": "onboarding_guide.setup 和 next_actions.run_setup 都带用户确认。",
            "completion_check": "当前仓库出现 `.ai-bridge/` 和 `.codex/codex-chatgpt-bridge.config.toml`。",
            "requires_user_confirmation": True,
            "external_evidence_required": False,
            "auto_execute": False,
        },
        {
            "id": "generate_tokens",
            "prd_step": "Bridge 生成两个 token：local_token 与 remote_token",
            "user_action": "让 `setup.py` 生成 local_token 与 remote_token，但不要把 token 复制到聊天、issue 或日志。",
            "local_evidence": "setup 只在本地状态文件和被 gitignore 的环境文件保存 token。",
            "completion_check": "token 已生成；输出、任务包和审计日志不展示原始 token。",
            "requires_user_confirmation": True,
            "external_evidence_required": False,
            "auto_execute": False,
        },
        {
            "id": "codex_mcp_stdio",
            "prd_step": "本地 Codex MCP 配置优先使用 stdio command，由 Codex 启动本地 server",
            "user_action": "让 Skill 自动生成或更新 `.codex/codex-chatgpt-bridge.config.toml`，并安全更新仓库和用户级 Codex active 配置；确认它使用 `command + args` 指向本仓库 `scripts/codex_bridge_stdio_mcp.py`。",
            "local_evidence": "onboarding_guide.review_codex_config 和 confirmation_points 都要求先审查 stdio 配置片段与 `scripts/codex_bridge_stdio_mcp.py`。",
            "completion_check": "活跃 Codex MCP 配置不含 token URL，且能看到或调用 Bridge 工具。",
            "requires_user_confirmation": True,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "remote_connection_path",
            "prd_step": "ChatGPT 远端连接优先使用 Secure MCP Tunnel；不可用时使用 HTTPS tunnel + remote path token",
            "user_action": "优先配置 OAuth 或 Secure MCP Tunnel；不可用时才使用 HTTPS tunnel + remote path token，并只在 Connector UI 粘贴 endpoint。",
            "local_evidence": "create_connector 动作和生产 readiness 文档都把 Secure MCP Tunnel / OAuth 作为优先路径。",
            "completion_check": "远端 `/mcp` endpoint 可达，且没有把完整 Connector URL 或 remote token 写入聊天、issue 或仓库。",
            "requires_user_confirmation": True,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "create_chatgpt_connector",
            "prd_step": "用户在 ChatGPT 开启 Developer Mode 并创建 Connector",
            "user_action": "在 ChatGPT 官方 Connector UI 中创建 Connector，不在本地脚本里伪造 UI 成功。",
            "local_evidence": "next_actions.create_connector 只给手动操作说明。",
            "completion_check": "ChatGPT UI 显示 Connector 创建成功并能看到工具列表。",
            "requires_user_confirmation": True,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "run_read_smoke",
            "prd_step": "运行读 smoke test",
            "user_action": "在真实 ChatGPT tool call 后运行 read smoke，并把证据保存到用户确认过的脱敏 evidence 文件。",
            "local_evidence": "capability_check 和 next_actions.run_read_smoke 都要求真实证据。",
            "completion_check": "用户确认过的脱敏 evidence 文件里有结构化 read_smoke 证据。",
            "requires_user_confirmation": True,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "run_write_smoke",
            "prd_step": "运行写 smoke test",
            "user_action": "在真实 ChatGPT `bridge_send_result` 写回后运行 write smoke，并把证据保存到用户确认过的脱敏 evidence 文件。",
            "local_evidence": "next_actions.run_write_smoke 明确失败时回退 Read-only。",
            "completion_check": "用户确认过的脱敏 evidence 文件里有结构化 write_smoke、pull_result 和 review_result 证据。",
            "requires_user_confirmation": True,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "capability_gate",
            "prd_step": "能力判定：Full / Read-only / Packet",
            "user_action": "根据真实 read/write smoke 结果选择 Full Connector、Read-only Connector 或 Packet / Manual。",
            "local_evidence": "recommended_path、user_paths 和 quick_start_targets 都显示能力判定与 fallback。",
            "completion_check": "没有真实证据时，不把本地预检结果写成 Full 或 Read-only。",
            "requires_user_confirmation": False,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "send_test_task",
            "prd_step": "Codex 发送测试任务",
            "user_action": "先运行 `push_task.py --preview` 或 `build_packet.py` 自查上下文；用户确认后才把 `--preview` 改成 `--yes`，并生成带真实 task_id 的 ChatGPT 消息或手动上传。",
            "local_evidence": "onboarding_guide.preview_context 和 send_or_share 固定先预览再确认发送。",
            "completion_check": "上下文已通过 secret scan；发送动作可追溯到用户确认；结构化导入消息绑定真实 task_id。",
            "requires_user_confirmation": True,
            "external_evidence_required": False,
            "auto_execute": False,
        },
        {
            "id": "right_side_receive_or_return",
            "prd_step": "右侧 ChatGPT 读取任务并写回，或输出可导入结果",
            "user_action": "Full 模式使用 `bridge_pull_task` / `bridge_send_result`；Read-only 优先使用 `bridge_fetch_task_packet` 只读取包，Packet 或 Manual 输出 fenced `codex-bridge-result-json` 后，Codex 从 session 状态卡读取 repo-bound intake 动作预检，用户确认后导入。",
            "local_evidence": "user_paths、onboarding_guide.receive_result 和 session 状态卡区分 pull_result 与 intake/import。",
            "completion_check": "本地已有 result 记录，且危险命令被剔除或标记。",
            "requires_user_confirmation": True,
            "external_evidence_required": True,
            "auto_execute": False,
        },
        {
            "id": "codex_close_loop",
            "prd_step": "Codex 读取结果并完成闭环",
            "user_action": "从 session 状态卡读取 repo-bound pull / intake / review 动作；先拉取或预检并确认导入后，再生成审阅清单。",
            "local_evidence": "onboarding_guide.review_result 和 user_approval_before_execution 明确不自动执行建议。",
            "completion_check": "用户逐条批准后，Codex 才执行被批准的最小动作。",
            "requires_user_confirmation": True,
            "external_evidence_required": False,
            "auto_execute": False,
        },
    ]
    for index, item in enumerate(flow, start=1):
        item["step"] = index
    return flow


def build_onboarding_guide(
    *,
    config: dict[str, Any],
    bridge_running: bool,
    recommended_mode: dict[str, str],
    capability_evidence: dict[str, object],
) -> list[dict[str, object]]:
    mode = recommended_mode["mode"]
    guide: list[dict[str, object]] = [
        guide_step(
            "clinic",
            "先看能力门诊",
            "从这里启动 ChatGPT 任务单 / 审查协同；Connector、Packet 和 Manual 只是后台能力分流。",
            "你能说清楚当前推荐路径、原因和下一步确认点。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/first_run.py",
        ),
        guide_step(
            "doctor",
            "跑机器诊断",
            "确认 Skill、Bridge、Codex MCP 配置、工具 schema 和真实能力证据的状态。",
            "`doctor.py --json` 输出已看过；如果有 required_actions，先按顺序处理。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/doctor.py --json",
        ),
    ]

    if not config:
        guide.extend(
            [
                guide_step(
                    "setup",
                    "初始化本地配置",
                    "只在当前仓库生成 Bridge 状态目录、token 文件和 Codex MCP 配置片段。",
                    "当前仓库出现 `.ai-bridge/`，并生成可审查的 `.codex/codex-chatgpt-bridge.config.toml`。",
                    "python .agents/skills/codex-chatgpt-bridge/scripts/setup.py --json",
                    user_confirmation="确认允许脚本在当前仓库写入本地配置文件；不要把生成的 token 复制到聊天或 issue。",
                ),
                guide_step(
                    "review_codex_config",
                    "审查 Codex 配置片段",
                    "Codex 本地配置使用 stdio，由 Codex 自己启动本地 MCP server，不依赖 GUI 环境变量。",
                    "配置里使用 `command + args` 指向 `scripts/codex_bridge_stdio_mcp.py`，没有把 token 写进 URL。",
                    manual="打开 `.codex/codex-chatgpt-bridge.config.toml` 审查；普通用户入口会在安全情况下自动写入仓库和用户级 active 配置。",
                    user_confirmation="确认配置片段不含完整 Connector URL、remote token 或 `/mcp/remote/<token>`。",
                ),
            ]
        )

    if not bridge_running:
        guide.append(
            guide_step(
                "start_bridge",
                "启动本地 Bridge",
                "让本机 MCP 工具可用；远端 ChatGPT 访问仍需要你另行配置安全 tunnel。",
                "`status.py --json` 或 `doctor.py --json` 显示 Bridge running。",
                "python .agents/skills/codex-chatgpt-bridge/scripts/start_bridge.py",
                user_confirmation="确认只在本机启动 localhost Bridge；不要把 remote token 或完整 endpoint 贴到聊天里。",
            )
        )

    guide.append(
        guide_step(
            "capability_check",
            "判定真实能力",
            "真实能力只决定后台同步方式；不要按 Plus、Pro、Business 等账号名称承诺能力，没有证据时仍保持自动协同入口并走受控导入兜底。",
            "真实证据必须写入用户确认过的脱敏 evidence 文件；没有真实证据时不升级 capability_mode。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/smoke_test.py --read",
            manual="write smoke 必须在真实 ChatGPT UI 完成后再运行；无法验证时不冒充 Full Connector，继续用内置浏览器协同和结构化导入。",
            user_confirmation="确认 smoke 证据来自真实 ChatGPT Connector tool call，而不是本地模拟输出。",
            fallback="Connector、账号或 tunnel 不确定时，优先保持右侧 ChatGPT 协同；Packet / Manual 只作最后兜底。",
        )
    )

    if capability_evidence.get("status") == "verified" and mode == FULL_CONNECTOR:
        preview_command = (
            "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py "
            '--title "右侧 ChatGPT 审查" --goal "审查当前改动并给出建议" --preview'
        )
        receive_command = PULL_RESULT_COMMAND
        receive_manual = None
    elif capability_evidence.get("status") == "verified" and mode == READ_ONLY_CONNECTOR:
        preview_command = (
            "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py "
            '--title "右侧 ChatGPT 只读审查" --goal "审查当前改动并输出 result JSON" --preview'
        )
        receive_command = INTAKE_RESULT_COMMAND
        receive_manual = "把右侧 ChatGPT 输出的 fenced `codex-bridge-result-json` 复制到 stdin；预检通过后再由用户确认导入。"
    elif mode == READ_ONLY_PACKET_OR_MANUAL:
        preview_command = (
            "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py "
            '--title "右侧 ChatGPT 只读审查" --goal "审查当前改动并输出 result JSON" --preview'
        )
        receive_command = INTAKE_RESULT_COMMAND
        receive_manual = "如果右侧能看到只读工具，让它调用 `bridge_fetch_task_packet`；如果没有工具入口，就上传 packet 或复制最小上下文，并把 fenced `codex-bridge-result-json` 复制到 stdin 做预检。"
    elif mode == AUTOMATED_COLLABORATION:
        preview_command = automated_collaboration_push_task_command(preview=True)
        receive_command = INTAKE_RESULT_COMMAND
        receive_manual = "优先通过官方 MCP read/fetch/write 同步；只读可用时调用 `bridge_fetch_task_packet`，写回不可用时让右侧输出 fenced `codex-bridge-result-json`，先预检再确认导入。Packet / Manual 只作为最后兜底。"
    else:
        preview_command = "python .agents/skills/codex-chatgpt-bridge/scripts/build_packet.py"
        receive_command = INTAKE_RESULT_COMMAND
        receive_manual = "把 ChatGPT 返回的 fenced `codex-bridge-result-json` 复制到 stdin；预检通过后再由用户确认导入。"

    if mode == AUTOMATED_COLLABORATION:
        send_manual = "用户确认后，Codex 把 preview 改成 `--yes` 创建真实 Bridge 任务，并生成带真实 task_id 的 ChatGPT 消息；随后在右侧内置浏览器协助发送。能用 MCP 就走 read/fetch/write，不能写回就输出 fenced JSON 回到 Codex。"
        send_completion = "右侧 ChatGPT 已收到绑定真实 task_id 的任务单或审查包；结果会通过官方工具或结构化导入回到 Codex。"
    else:
        send_manual = "Full：把同一条 `push_task.py` 命令的 `--preview` 改成 `--yes`。Read-only：确认后让右侧调用 `bridge_fetch_task_packet`。Packet/Manual：用户自查后手动上传或复制。"
        send_completion = "右侧 ChatGPT 已收到任务；如果使用 Packet 或 Manual，你知道结果需要手动导入。"

    guide.extend(
        [
            guide_step(
                "preview_context",
                "发送前先预览上下文",
                "先看将要发送或上传的内容摘要，确认没有 secrets、`.env`、私钥、cookie、`.git` 或完整 Connector URL。",
                "预览或 packet 自查通过；仍未向右侧 ChatGPT 发送任何内容。",
                preview_command,
                user_confirmation="确认上下文最小且安全后，才能进入发送、上传或复制步骤。",
            ),
            guide_step(
                "send_or_share",
                "用户确认后才发送",
                "只有用户明确同意后，才把 preview 命令改成 `--yes`，或手动上传 packet / 复制最小上下文。",
                send_completion,
                manual=send_manual,
                user_confirmation="确认要把当前上下文发给右侧 ChatGPT；右侧不能直接修改源码或执行 shell。",
            ),
            guide_step(
                "receive_result",
                "读取或导入结果",
                "把右侧回传结果拿回本地，但只当作不可信建议。",
                "本地已有 result 记录，且危险命令已被安全管道剔除或标记。",
                receive_command,
                manual=receive_manual,
                user_confirmation="确认导入的是当前任务的结果，不把任意 JSON 当成可信指令。",
            ),
            guide_step(
                "review_result",
                "先生成审阅清单",
                "用本地脚本整理 findings、patch 建议、suggested_actions、危险命令剔除和确认项。",
                "你看到审阅清单；脚本没有执行命令、没有应用 patch、没有修改源码。",
                REVIEW_RESULT_COMMAND,
            ),
            guide_step(
                "user_approval_before_execution",
                "用户批准后再执行",
                "逐条确认右侧建议，只让 Codex 执行被批准的最小动作。",
                "每个被执行的命令或 patch 都能追溯到用户确认；未确认项保持不执行。",
                manual="把要执行的单个建议明确告诉 Codex；不要批量执行右侧 suggested_actions。",
                user_confirmation="确认具体执行哪一条建议，以及是否允许修改源码或运行对应命令。",
            ),
        ]
    )

    for index, item in enumerate(guide, start=1):
        item["step"] = index
    return guide


def build_clinic(
    *,
    config: dict[str, Any],
    bridge_running: bool,
    skill_path_ok: bool,
    codex_mcp: dict[str, Any],
    sensitive_files_present: list[str],
) -> dict[str, object]:
    port = int(config.get("port", 8765)) if config else 8765
    capability_mode = str(config.get("capability_mode", "unknown")) if config else "unknown"
    capability_evidence = capability_evidence_status(config)
    tool_schema = connector_schema_status(config)
    remote_token = remote_token_status(config) if config else {"status": "unknown", "refresh_required": True}

    issues: list[str] = []
    if not skill_path_ok:
        issues.append("Skill 文件不在当前仓库 `.agents/skills/codex-chatgpt-bridge/SKILL.md`。")
    if not config:
        issues.append("还没有初始化 `.ai-bridge/`。")
    if config and not bridge_running:
        issues.append("本地 Bridge 当前没有运行。")
    if capability_evidence.get("status") == "unverified":
        issues.append("当前能力模式没有真实 ChatGPT Connector smoke 证据支撑。")
    if tool_schema.get("refresh_required"):
        issues.append("ChatGPT Connector 工具快照可能过期，需要 Refresh。")
    if config and remote_token.get("refresh_required"):
        issues.append("remote token 已过期或状态未知；继续外部连接验证前需要重新生成连接材料。")
    if sensitive_files_present:
        issues.append("仓库根目录存在敏感文件名；Bridge 会拒绝读取，但发送任务前仍建议确认上下文。")
    if codex_mcp.get("active_token_in_url_detected"):
        issues.append("活跃 Codex MCP 配置疑似把 token 写在 URL 里，应切换为本地 stdio command 配置。")

    recommended_mode = recommend_mode(config=config, bridge_running=bridge_running, capability_mode=capability_mode, capability_evidence=capability_evidence)
    onboarding_guide = build_onboarding_guide(
        config=config,
        bridge_running=bridge_running,
        recommended_mode=recommended_mode,
        capability_evidence=capability_evidence,
    )
    next_actions = build_next_actions(
        config=config,
        bridge_running=bridge_running,
        recommended_mode=recommended_mode,
        capability_evidence=capability_evidence,
        tool_schema=tool_schema,
        remote_token=remote_token,
    )
    recommended_path = build_recommended_path(recommended_mode, next_actions)
    simple_onboarding = build_simple_onboarding(recommended_path, recommended_mode)

    return {
        "ok": skill_path_ok,
        "title": "Codex ChatGPT Bridge 能力门诊",
        "audience": "普通用户第一次使用",
        "summary": {
            "skill": "已发现" if skill_path_ok else "未发现",
            "setup": "已初始化" if config else "未初始化",
            "bridge": "运行中" if bridge_running else "未运行",
            "port": port,
            "capability_mode": capability_mode,
            "capability_evidence_status": capability_evidence.get("status"),
            "remote_token_status": remote_token.get("status"),
            "remote_token_refresh_required": remote_token.get("refresh_required"),
            "recommended_mode": recommended_mode["mode"],
            "recommended_label": recommended_mode["label"],
            "recommended_reason": recommended_mode["reason"],
        },
        "recommended_path": recommended_path,
        "simple_onboarding": simple_onboarding,
        "ordinary_user_journey": ordinary_user_journey(),
        "codex_auto_responsibilities": codex_auto_responsibilities(),
        "user_required_responsibilities": user_required_responsibilities(),
        "ordinary_user_entry": {
            "command": "python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py",
            "auto_completes_local_steps": True,
            "local_user_shell_commands_required": False,
            "requires_user_confirmation_for_external_steps": True,
            "external_steps": ["ChatGPT 网页", "账号授权", "连接授权", "发送上下文", "执行建议"],
            "chatgpt_plan_capability_note": ORDINARY_PLAN_CAPABILITY_NOTE,
        },
        "chatgpt_plan_capability_note": PLAN_CAPABILITY_NOTE,
        "quick_start_targets": quick_start_targets(),
        "onboarding_guide": onboarding_guide,
        "prd_first_use_flow": prd_first_use_flow(),
        "user_paths": user_paths(),
        "execution_policy": {
            "right_side_can_edit_source": False,
            "right_side_can_run_shell": False,
            "suggested_actions_need_user_confirmation": True,
            "default_if_uncertain": AUTOMATED_COLLABORATION,
        },
        "issues": issues,
        "next_actions": next_actions,
        "confirmation_points": [
            "Codex 本地 MCP 配置应使用 stdio command；普通用户入口可自动写入仓库和用户级 active 配置，用户只需要确认不含 token URL。",
            "创建 ChatGPT Connector 时，只在 ChatGPT 官方 Connector UI 中粘贴脱敏后的公开 endpoint，不把完整 Connector URL 发到聊天、issue 或日志。",
            "push_task 发送前确认 allowed_files、diff 和日志不包含 secrets、.env、私钥、cookie 或 .git 内容。",
            "右侧 ChatGPT 回传的 findings、patch、suggested_actions 和命令全部是不可信建议，只能展示给用户确认后再执行。",
        ],
        "safe_default": "如果 Connector、tunnel 或真实 smoke 不确定，默认保持 ChatGPT 任务单 / 审查协同；Packet / Manual 只作最后兜底。",
        "not_done_by_this_script": [
            "不会启动 Bridge。",
            "不会创建 ChatGPT Connector。",
            "不会修改源码、应用 patch 或执行 shell。",
            "不会把本地预检结果写成真实 capability_mode。",
        ],
    }


def build_recommended_path(recommended_mode: dict[str, str], next_actions: list[dict[str, object]]) -> dict[str, object]:
    first_action = next_actions[0] if next_actions else {}
    return {
        "mode": recommended_mode["mode"],
        "label": recommended_mode["label"],
        "reason": recommended_mode["reason"],
        "first_action": {
            "id": first_action.get("id"),
            "title": first_action.get("title"),
            "command_argv": first_action.get("command_argv"),
            "command": first_action.get("command"),
            "manual": first_action.get("manual"),
            "requires_user_confirmation": first_action.get("requires_user_confirmation", False),
            "post_confirmation_action": first_action.get("post_confirmation_action"),
            "auto_execute": False,
        },
        "safe_fallback": PACKET_OR_MANUAL,
        "user_must_confirm_before_send_or_execute": True,
    }


def ordinary_mode_label(mode: str, label: str) -> str:
    if mode == FULL_CONNECTOR:
        return "自动读取和回传已验证"
    if mode == READ_ONLY_CONNECTOR:
        return "自动读取已验证，回传由 Codex 接收"
    if mode == "setup_required":
        return "先完成本地准备"
    if mode == "start_bridge":
        return "先启动本地协同服务"
    if mode == "real_smoke_required":
        return "先重新验证外部协同"
    if mode in {PACKET_OR_MANUAL, READ_ONLY_PACKET_OR_MANUAL}:
        return "最后使用人工兜底"
    return label


def ordinary_mode_reason(mode: str, reason: str) -> str:
    if mode == FULL_CONNECTOR:
        return "当前账号的自动读取和回传已经通过真实验证；右侧建议仍需 Codex 审阅，并由用户确认后才执行。"
    if mode == READ_ONLY_CONNECTOR:
        return "当前账号可以让 ChatGPT 读取任务；回传仍先由 Codex 检查和审阅。"
    if mode == "setup_required":
        return "当前仓库还没完成本地准备，需要先让 Codex 初始化 Bridge。"
    if mode == "start_bridge":
        return "本地协同服务还没有运行，需要先让 Codex 启动。"
    if mode == "real_smoke_required":
        return "当前外部协同能力需要重新验证，先不要按自动写回使用。"
    if mode in {PACKET_OR_MANUAL, READ_ONLY_PACKET_OR_MANUAL}:
        return "当前自动协同还不可用；仍先让 Codex 协助 ChatGPT 做任务单和审查，最后才使用人工兜底。"
    if mode == AUTOMATED_COLLABORATION:
        return "默认让 Codex 协助右侧 ChatGPT 做任务单或审查；能自动接收就自动接收，不可用时再受控带回回复。"
    return reason


def ordinary_capability_status(status: object) -> str:
    if status == "verified":
        return "已通过当前账号验证"
    if status == "unverified":
        return "需要重新验证"
    return "待验证"


def build_simple_onboarding(recommended_path: dict[str, object], recommended_mode: dict[str, str]) -> list[dict[str, object]]:
    ordinary_label = ordinary_mode_label(recommended_mode["mode"], recommended_mode["label"])
    return [
        {
            "step": 1,
            "id": "do_recommended_next_step",
            "title": "让 Skill 自动完成本地验证",
            "instruction": "本地 setup、启动 Bridge、状态检查、工具检查、安全检查和任务包准备都由 Skill 自动跑。",
            "command": "python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py",
            "manual": f"当前推荐路径是：{ordinary_label}；一键验证会先处理本地可自动步骤，只有自动协同不可用时才使用人工兜底。",
            "confirmation": "ChatGPT 网页、账号授权、发送上下文或执行建议前，仍会单独请求用户确认。",
            "auto_execute": False,
        },
        {
            "step": 2,
            "id": "preview_before_share",
            "title": "先让 ChatGPT 做任务单或审查",
            "instruction": "任何要发给右侧 ChatGPT 的上下文，都先由 Codex 预览；ChatGPT 先做任务单、规划或审查，不写代码。",
            "command": (
                automated_collaboration_push_task_command(preview=True)
            ),
            "manual": "Codex 优先在右侧内置浏览器协助发送；自动接收不可用时，先检查 ChatGPT 回复并带回 Codex 审阅。",
            "confirmation": "确认不含 secrets、.env、私钥、cookie、.git 或完整外部连接地址后再发送。",
            "auto_execute": False,
        },
        {
            "step": 3,
            "id": "review_before_execute",
            "title": "回传后先审阅",
            "instruction": "右侧 ChatGPT 的结果只是不可信建议，先生成审阅清单，再由用户决定是否执行。",
            "command": REVIEW_RESULT_COMMAND,
            "manual": f"当前推荐模式是 {ordinary_label}；没有完成真实外部验证时，只把 ChatGPT 回复作为建议带回 Codex 审阅，不把外部能力标成可用。",
            "confirmation": "只有用户明确批准的单条建议，Codex 才能继续执行。",
            "auto_execute": False,
        },
    ]


def recommend_mode(
    *,
    config: dict[str, Any],
    bridge_running: bool,
    capability_mode: str,
    capability_evidence: dict[str, object],
) -> dict[str, str]:
    if not config:
        return {
            "mode": "setup_required",
            "label": "先初始化本地 Bridge",
            "reason": "当前仓库还没完成本地准备，需要先让 Codex 初始化 Bridge。",
        }
    if not bridge_running:
        return {
            "mode": "start_bridge",
            "label": "先启动本地 Bridge",
            "reason": "本地 Bridge 还没有运行，需要先让 Codex 启动本机协同服务。",
        }
    if capability_evidence.get("status") == "unverified":
        return {
            "mode": "real_smoke_required",
            "label": "重新做真实能力验证",
            "reason": "当前能力模式缺少真实外部验证，不能按自动写回使用。",
        }
    if capability_mode == FULL_CONNECTOR and capability_evidence.get("status") == "verified":
        return {
            "mode": FULL_CONNECTOR,
            "label": "Full Connector",
            "reason": "真实 read/write smoke 已验证，可用右侧 ChatGPT 读取任务并写回结果。",
        }
    if capability_mode == READ_ONLY_CONNECTOR and capability_evidence.get("status") == "verified":
        return {
            "mode": READ_ONLY_CONNECTOR,
            "label": "Read-only Connector",
            "reason": "真实 read smoke 已验证，但写回不可用或未验证，结果需要手动导入。",
        }
    if capability_mode == PACKET_OR_MANUAL:
        return {
            "mode": AUTOMATED_COLLABORATION,
            "label": AUTOMATED_COLLABORATION_LABEL,
            "reason": "当前没有真实外部同步证明；仍先让 Codex 协助右侧 ChatGPT 做任务单和审查，只有自动协同不可用时才使用人工兜底。",
        }
    return {
        "mode": AUTOMATED_COLLABORATION,
        "label": AUTOMATED_COLLABORATION_LABEL,
        "reason": "Bridge 已就绪但没有真实写回证明；默认让 Codex 协助右侧 ChatGPT 做任务单或审查，能自动接收就自动接收，不可用时再受控带回回复。",
    }


def build_next_actions(
    *,
    config: dict[str, Any],
    bridge_running: bool,
    recommended_mode: dict[str, str],
    capability_evidence: dict[str, object],
    tool_schema: dict[str, object],
    remote_token: dict[str, object],
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    if not config:
        actions.append(
            action(
                "run_setup",
                "初始化本地 Bridge 配置",
                "生成 repo-local `.ai-bridge/`、token 和 Codex MCP 配置片段。",
                "python .agents/skills/codex-chatgpt-bridge/scripts/setup.py --json",
                confirmation="确认允许在当前仓库写入 `.ai-bridge/`、`.env.codex-bridge.local` 和 `.codex/codex-chatgpt-bridge.config.toml`。",
            )
        )
        actions.append(
            action(
                "review_codex_config",
                "审查 Codex MCP 配置片段",
                "确认本地 Codex 配置使用 stdio `command + args`，不把 token 写入 URL。",
                manual="打开 `.codex/codex-chatgpt-bridge.config.toml`，确认它指向 `scripts/codex_bridge_stdio_mcp.py`。",
                confirmation="确认配置片段不含 token 或 `/mcp/remote/<token>`。",
            )
        )
        return actions

    if not bridge_running:
        actions.append(
            action(
                "start_bridge",
                "启动本地 Bridge",
                "让 Codex 和 ChatGPT Connector 可以通过 MCP 调用本地工具。",
                "python .agents/skills/codex-chatgpt-bridge/scripts/start_bridge.py",
                confirmation="确认要在本机 localhost 启动 Bridge；它只绑定本地地址，远端访问仍需你单独配置 tunnel。",
            )
        )

    if recommended_mode["mode"] == AUTOMATED_COLLABORATION and bridge_running:
        actions.append(automated_collaboration_preview_action())

    actions.append(
        action(
            "run_doctor",
            "查看机器诊断",
            "确认 Bridge、Codex MCP 配置、工具 schema 和 capability evidence 状态。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/doctor.py --json",
        )
    )

    if tool_schema.get("refresh_required"):
        actions.append(
            action(
                "refresh_connector_tools",
                "刷新 ChatGPT Connector 工具列表",
                "工具 schema 变化后，ChatGPT 可能还在使用旧快照。",
                manual="打开 ChatGPT Connector 设置，点击 Refresh 或重新连接该 Connector。",
                confirmation="确认 ChatGPT UI 里能看到最新工具列表后，再继续 smoke test。",
            )
        )

    if config and remote_token.get("refresh_required"):
        actions.append(
            action(
                "rotate_remote_connection_materials",
                "重新生成外部连接材料",
                "当前外部连接材料已过期或状态未知；继续 ChatGPT 外部连接验证前，需要先轮换本仓库远端连接材料。",
                "python .agents/skills/codex-chatgpt-bridge/scripts/rotate_token.py --remote",
                confirmation="确认允许轮换本仓库的远端连接材料；旧 ChatGPT Connector URL 或 tunnel 配置会失效，后续连接更新仍需单独确认。",
            )
        )

    if recommended_mode["mode"] in {"real_smoke_required", "start_bridge"}:
        actions.extend(
            [
                action(
                    "confirm_chatgpt_plan_capability",
                    "确认 ChatGPT 账号/工作区能力",
                    "个人 Pro 可能只能使用 read/fetch；Full Connector 写回必须由真实 write smoke 证明。",
                    manual="在 ChatGPT 网页确认当前是否处于支持 full MCP 写动作的工作区；如果模型说没有 `bridge_pull_task` / `bridge_send_result`，保持 blocked 并走 fallback。",
                    confirmation="不要因为 Connector 能创建或工具列表能扫描，就把 write smoke 记为 verified。",
                ),
                action(
                    "create_connector",
                    "创建或检查 ChatGPT Connector",
                    "只有 ChatGPT UI 显示真实 tool call，才算 Connector 侧验证成立。",
                    manual="在 ChatGPT 设置里打开 Developer Mode / Connectors，添加公开 HTTPS `/mcp` endpoint；优先 OAuth 或 Secure MCP Tunnel。",
                    confirmation="确认不把完整 Connector URL、remote token、cookie 或账号信息写入仓库、聊天或 issue。",
                ),
                action(
                    "run_read_smoke",
                    "完成真实 read smoke",
                    "确认右侧 ChatGPT 能真实调用读取类工具。",
                    "python .agents/skills/codex-chatgpt-bridge/scripts/smoke_test.py --read",
                    confirmation="先确认有真实 ChatGPT Connector read smoke 证据，再运行此命令。",
                ),
                action(
                    "run_write_smoke",
                    "完成真实 write smoke",
                    "确认右侧 ChatGPT 能通过 `bridge_send_result` 写回结果；失败时自动走 Read-only。",
                    "python .agents/skills/codex-chatgpt-bridge/scripts/smoke_test.py --write",
                    confirmation="只有 ChatGPT UI 显示真实写工具调用并记录证据后，才能把模式升级为 Full Connector。",
                ),
            ]
        )

    if capability_evidence.get("status") == "verified" and recommended_mode["mode"] == FULL_CONNECTOR:
        actions.extend(full_connector_actions())
    elif capability_evidence.get("status") == "verified" and recommended_mode["mode"] == READ_ONLY_CONNECTOR:
        actions.extend(read_only_actions())
    elif recommended_mode["mode"] == AUTOMATED_COLLABORATION:
        actions.extend(automated_collaboration_actions())
    elif recommended_mode["mode"] == READ_ONLY_PACKET_OR_MANUAL:
        actions.extend(read_only_packet_manual_actions())
    else:
        actions.extend(packet_manual_actions())
    return actions


def automated_collaboration_preview_action() -> dict[str, object]:
    preview = action(
        "prepare_chatgpt_task_brief_preview",
        "预览 ChatGPT 任务单 / 审查协同包",
        "先让 Codex 准备最小上下文和任务单要求；确认安全后再交给右侧 ChatGPT。",
        automated_collaboration_push_task_command(preview=True),
        confirmation="确认预览不含 secrets、.env、私钥、cookie、.git 或完整 Connector URL 后，才允许发送给右侧 ChatGPT。",
    )
    preview["command_argv"] = automated_collaboration_push_task_argv(preview=True)
    preview["post_confirmation_action"] = automated_collaboration_confirmed_send_action()
    return preview


def automated_collaboration_actions() -> list[dict[str, object]]:
    return [
        action(
            "prepare_right_browser_assist",
            "准备右侧内置浏览器协同",
            "用户授权后由 Codex 协助打开 ChatGPT、发送任务单，并尽量通过官方 MCP 或受控导入同步结果。",
            "python scripts/build_authorized_browser_session_plan.py --json",
            confirmation="确认允许打开 ChatGPT 网页并发送当前预览过的上下文；登录、账号授权和发送动作仍需用户确认。",
        ),
        action(
            "try_mcp_or_structured_import",
            "优先尝试 MCP 同步，失败再结构化导入",
            "Full 可用时走 `bridge_pull_task` / `bridge_send_result`；只读可用时走 `bridge_fetch_task_packet`；都不可用时要求 fenced JSON。",
            manual="在右侧 ChatGPT 选择 Bridge 后，先尝试官方工具；没有真实 tool call 时不要冒充成功，要求输出 `codex-bridge-result-json`。",
            confirmation="没有真实 `bridge_pull_task` 和 `bridge_send_result` audit 时，Full Connector 继续 blocked。",
        ),
        action(
            "import_structured_result",
            "预检并导入 ChatGPT 结构化结果",
            "先校验右侧返回的 fenced `codex-bridge-result-json`，确认真实 task_id、本地任务和 schema 后再导入审查链路。",
            INTAKE_RESULT_COMMAND,
            confirmation="预检通过不等于批准执行；导入结果仍是不可信建议。",
        ),
        action(
            "review_result_automated_collaboration",
            "生成结果审阅清单",
            "把 ChatGPT 的任务单、审查意见和 suggested_actions 整理成用户确认清单。",
            REVIEW_RESULT_COMMAND,
            confirmation="只在用户逐条确认后，Codex 才能执行对应最小修改或命令。",
        ),
        action(
            "fallback_packet_only_if_needed",
            "最后兜底生成 Packet",
            "只有官方工具和受控浏览器协同都不可用时，才生成脱敏 packet 给用户手动上传。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/build_packet.py",
            confirmation="确认 packet 已脱敏；这只是兜底，不代表自动化协同已验证完成。",
        ),
    ]


def full_connector_actions() -> list[dict[str, object]]:
    return [
        action(
            "push_task",
            "预览并发送一次右侧审查任务",
            "先查看将发送的上下文摘要，确认后再加 `--yes` 发送给右侧 ChatGPT。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py --title \"右侧 ChatGPT 审查\" --goal \"审查当前改动并给出建议\" --preview",
            confirmation="预览确认无 secrets 后，将同一命令的 `--preview` 改为 `--yes` 才会发送；右侧只给建议，不直接改源码。",
        ),
        action(
            "pull_result",
            "读取右侧结果并人工确认",
            "Codex 读取结果后，只展示 findings 和 suggested_actions，执行前必须由用户确认。",
            PULL_RESULT_COMMAND,
            confirmation="逐条确认 suggested_actions；危险命令即使出现也不得自动执行。",
        ),
        action(
            "review_result",
            "生成结果审阅清单",
            "把右侧回传整理成 findings、建议动作、危险命令剔除和确认清单。",
            REVIEW_RESULT_COMMAND,
            confirmation="只在审阅清单通过人工确认后，再决定是否单独执行某个建议。",
        ),
    ]


def read_only_actions() -> list[dict[str, object]]:
    return [
        action(
            "push_task_read_only",
            "预览并发送只读审查任务",
            "先查看将发送的上下文摘要，确认后再加 `--yes`；右侧结果需要复制回 Codex。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py --title \"右侧 ChatGPT 只读审查\" --goal \"审查当前改动并输出 result JSON\" --preview",
            confirmation="预览确认上下文已经过 secret scan 后，将 `--preview` 改为 `--yes`；右侧不会直接写回或执行命令。",
        ),
        action(
            "import_result",
            "预检并导入 ChatGPT 复制回来的结果",
            "先校验 fenced `codex-bridge-result-json` 的真实 task_id、本地任务和 schema，再由用户确认导入。",
            INTAKE_RESULT_COMMAND,
            confirmation="预检和导入后仍需人工确认 findings 和 suggested_actions，不能自动执行。",
        ),
        action(
            "review_result_read_only",
            "生成结果审阅清单",
            "把导入结果整理成 findings、建议动作、危险命令剔除和确认清单。",
            REVIEW_RESULT_COMMAND,
            confirmation="只在审阅清单通过人工确认后，再决定是否单独执行某个建议。",
        ),
    ]


def read_only_packet_manual_actions() -> list[dict[str, object]]:
    return [
        action(
            "push_task_read_only_preview",
            "预览只读任务包",
            "先查看将暴露给右侧 ChatGPT 的最小上下文；确认后才创建可读取任务。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/push_task.py --title \"右侧 ChatGPT 只读审查\" --goal \"审查当前改动并输出 result JSON\" --preview",
            confirmation="预览确认无 secrets 后，才把 `--preview` 改为 `--yes`；右侧只能读取任务包并输出建议。",
        ),
        action(
            "try_read_only_fetch",
            "尝试只读读取任务包",
            "如果右侧 ChatGPT 只暴露 read/fetch 工具，让它调用只读工具读取任务，不要求 claim 或写回。",
            manual="在右侧 ChatGPT 选择 Bridge 后，要求调用 `bridge_fetch_task_packet`。如果没有可调用工具入口，不要重启或重建 Connector，直接使用 Packet / Manual。",
            confirmation="确认这只证明只读取包可用；没有 `bridge_pull_task` 和 `bridge_send_result` 真实 tool call 时，Full Connector 仍保持 blocked。",
        ),
        *packet_manual_actions(),
    ]


def packet_manual_actions() -> list[dict[str, object]]:
    return [
        action(
            "build_packet",
            "生成 Packet fallback",
            "没有 Connector 时，生成可上传给 ChatGPT 的 review packet。",
            "python .agents/skills/codex-chatgpt-bridge/scripts/build_packet.py",
            confirmation="确认 packet 内容不含 secrets；上传前可以先打开 markdown 自查。",
        ),
        action(
            "manual_import",
            "复制结果并预检导入",
            "让 ChatGPT 输出 `codex-bridge-result-json` fenced JSON，先预检再确认导入本地。",
            INTAKE_RESULT_COMMAND,
            confirmation="导入结果后只作为建议处理；任何命令都要再次确认。",
        ),
        action(
            "review_result_manual",
            "生成结果审阅清单",
            "把手动导入结果整理成确认清单，避免把建议误当成已批准执行。",
            REVIEW_RESULT_COMMAND,
            confirmation="只在审阅清单通过人工确认后，再决定是否单独执行某个建议。",
        ),
    ]


def ordinary_issue_text(issue: str) -> str:
    if "Connector 工具快照" in issue:
        return "右侧 ChatGPT 的工具列表可能还没同步；需要继续时，Codex 会在后续单独确认。"
    if "remote token" in issue:
        return "外部连接材料已经过期或状态未知；需要继续外部连接验证时，Codex 会先请你确认重新生成连接材料。"
    if "Connector smoke" in issue:
        return "当前外部协同能力还缺少真实验证；先按默认协同流程继续。"
    if "token 写在 URL" in issue:
        return "检测到外部连接地址可能包含敏感片段；需要先切回本地安全配置。"
    return issue


def render_simple_text(result: dict[str, object]) -> str:
    summary = result["summary"]  # type: ignore[index]
    assert isinstance(summary, dict)
    lines = [
        "# Codex ChatGPT Bridge 能力门诊",
        "",
        f"推荐路径：{ordinary_mode_label(str(summary['recommended_mode']), str(summary['recommended_label']))}",
        f"原因：{ordinary_mode_reason(str(summary['recommended_mode']), str(summary['recommended_reason']))}",
        "",
        "当前状态：",
        f"- Skill：{summary['skill']}",
        f"- 初始化：{summary['setup']}",
        f"- Bridge：{summary['bridge']}",
        f"- 外部协同：{ordinary_capability_status(summary['capability_evidence_status'])}",
    ]
    issues = result.get("issues", [])
    if isinstance(issues, list) and issues:
        lines.extend(["", "需要注意："])
        lines.extend(f"- {ordinary_issue_text(str(issue))}" for issue in issues[:3])
        if len(issues) > 3:
            lines.append("- 还有更多诊断细节，可运行 `first_run.py --developer` 查看。")

    if result.get("chatgpt_plan_capability_note"):
        lines.extend(["", "账号能力提示：", f"- {ORDINARY_PLAN_CAPABILITY_NOTE}"])

    steps = result.get("simple_onboarding", [])
    if isinstance(steps, list):
        lines.extend(["", "三步开始："])
        for item in steps:
            if not isinstance(item, dict):
                continue
            lines.append(f"{item.get('step')}. {item.get('title')}")
            lines.append(f"   {item.get('instruction')}")
            if item.get("manual"):
                lines.append(f"   处理方式：{item['manual']}")
            if item.get("confirmation"):
                lines.append(f"   确认：{item['confirmation']}")

    journey = result.get("ordinary_user_journey", [])
    if isinstance(journey, list):
        lines.extend(["", "完整流程："])
        for item in journey:
            if not isinstance(item, dict):
                continue
            marker = "用户确认" if item.get("requires_user_action") else "Codex 自动"
            lines.append(f"{item.get('step')}. {item.get('title')}（{marker}）")
            lines.append(f"   你会看到：{item.get('what_user_sees')}")
            lines.append(f"   完成标志：{item.get('done_when')}")

    required = result.get("user_required_responsibilities", [])
    if isinstance(required, list):
        lines.extend(["", "你只需要参与这些动作："])
        for item in required:
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "安全边界：",
            "- 右侧 ChatGPT 只给建议，不直接改源码，不执行 shell。",
            "- 发送前先预览；回传后先审阅；执行前再由用户确认。",
            "- 不发送 secrets、.env、私钥、cookie、.git 或完整外部连接地址。",
            "",
            "普通用户不用复制本地命令。需要继续时，让 Codex 按一键验证入口自动处理；开发/发布审计再查看维护者细节。",
            "维护者细节：使用 `--developer` 视图查看命令、完整底层流程和完整确认点。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_developer_text(result: dict[str, object]) -> str:
    summary = result["summary"]  # type: ignore[index]
    assert isinstance(summary, dict)
    lines = [
        "# Codex ChatGPT Bridge 能力门诊",
        "",
        f"推荐路径：{summary['recommended_label']}",
        f"原因：{summary['recommended_reason']}",
        "",
        "当前状态：",
        f"- Skill：{summary['skill']}",
        f"- 初始化：{summary['setup']}",
        f"- Bridge：{summary['bridge']}，端口 {summary['port']}",
        f"- 能力模式：{summary['capability_mode']}，证据状态：{summary['capability_evidence_status']}",
    ]
    issues = result.get("issues", [])
    if isinstance(issues, list) and issues:
        lines.extend(["", "需要注意："])
        lines.extend(f"- {issue}" for issue in issues)

    targets = result.get("quick_start_targets", {})
    if isinstance(targets, dict):
        lines.extend(
            [
                "",
                "上手目标：",
                f"- {targets.get('clinic_minutes')} 分钟内看懂当前推荐路径。",
                f"- {targets.get('install_to_capability_minutes')} 分钟内完成安装到能力判定。",
                f"- {targets.get('first_linkage_minutes')} 分钟内完成第一次 Connector 或 fallback 联动。",
            ]
        )

    guide_items = result.get("onboarding_guide", [])
    if isinstance(guide_items, list):
        lines.extend(["", "首次上手向导："])
        for item in guide_items:
            if not isinstance(item, dict):
                continue
            lines.append(f"{item.get('step')}. {item.get('title')}")
            lines.append(f"   说明：{item.get('plain_language_instruction')}")
            if item.get("command"):
                lines.append(f"   命令：{item['command']}")
            if item.get("manual"):
                lines.append(f"   操作：{item['manual']}")
            lines.append(f"   完成检查：{item.get('completion_check')}")
            if item.get("user_confirmation"):
                lines.append(f"   用户确认：{item['user_confirmation']}")
            if item.get("fallback"):
                lines.append(f"   退路：{item['fallback']}")

    prd_flow_items = result.get("prd_first_use_flow", [])
    if isinstance(prd_flow_items, list):
        lines.extend(["", "首次使用 14 步映射："])
        for item in prd_flow_items:
            if not isinstance(item, dict):
                continue
            lines.append(f"{item.get('step')}. {item.get('prd_step')}")
            lines.append(f"   用户动作：{item.get('user_action')}")
            lines.append(f"   完成检查：{item.get('completion_check')}")
            if item.get("requires_user_confirmation"):
                lines.append("   确认：需要用户确认后继续")
            if item.get("external_evidence_required"):
                lines.append("   证据：真实发布需要外部或人工证据")

    user_path_items = result.get("user_paths", [])
    if isinstance(user_path_items, list):
        lines.extend(["", "可选路径："])
        for item in user_path_items:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('label')}：{item.get('when_to_use')}")
            lines.append(f"  第一步：{item.get('first_step')}")
            lines.append(f"  确认：{item.get('confirmation')}")

    lines.extend(["", "下一步："])
    actions = result.get("next_actions", [])
    if isinstance(actions, list):
        for index, item in enumerate(actions, start=1):
            if not isinstance(item, dict):
                continue
            lines.append(f"{index}. {item.get('title')}")
            lines.append(f"   目的：{item.get('why')}")
            if item.get("command"):
                lines.append(f"   命令：{item['command']}")
            if item.get("manual"):
                lines.append(f"   操作：{item['manual']}")
            if item.get("confirmation"):
                lines.append(f"   确认：{item['confirmation']}")

    lines.extend(["", "执行前确认点："])
    for item in result.get("confirmation_points", []):
        lines.append(f"- {item}")
    lines.extend(["", f"安全默认：{result['safe_default']}"])
    lines.extend(["", "本脚本不会做："])
    for item in result.get("not_done_by_this_script", []):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def render_text(result: dict[str, object], *, developer: bool = False) -> str:
    if developer:
        return render_developer_text(result)
    return render_simple_text(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="普通用户首次使用能力门诊。")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--developer", action="store_true", help="显示开发/发布审计细节，包括首次使用 14 步映射和四条路径。")
    args = parser.parse_args()

    state = BridgeState(ROOT)
    config = state.load_config(default={})
    port = int(config.get("port", 8765)) if config else 8765
    result = build_clinic(
        config=config,
        bridge_running=port_running(port),
        skill_path_ok=(ROOT / ".agents/skills/codex-chatgpt-bridge/SKILL.md").is_file(),
        codex_mcp=inspect_codex_mcp_config(ROOT, port),
        sensitive_files_present=[
            name
            for name in [".env", ".env.local", "id_rsa", "id_ed25519"]
            if (ROOT / name).exists()
        ],
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result, developer=args.developer))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
