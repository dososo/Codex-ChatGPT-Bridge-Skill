#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from _bootstrap import ROOT
from bridge.state import BridgeState
from bridge.tools import BridgeTools, CODEX_LOCAL


CHATGPT_MESSAGE_MODES = ("task-brief", "review")


def git_output(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def build_context(args: argparse.Namespace) -> dict[str, object]:
    allowed = list(args.allowed_file)
    if args.changed_files:
        allowed.extend([line.strip() for line in git_output(["diff", "--name-only"]).splitlines() if line.strip()])

    context: dict[str, object] = {
        "git_status_excerpt": git_output(["status", "--short"])[:20000],
        "diff_stat": git_output(["diff", "--stat"])[:20000],
        "diff_excerpt": git_output(["diff"])[:60000],
        "allowed_files": allowed,
    }
    if args.test_log_file:
        context["test_log_excerpt"] = (ROOT / args.test_log_file).read_text(encoding="utf-8", errors="replace")
    return context


def build_preview(args: argparse.Namespace, context: dict[str, object]) -> dict[str, object]:
    allowed_files = context.get("allowed_files", [])
    if not isinstance(allowed_files, list):
        allowed_files = []
    preview: dict[str, object] = {
        "would_send": True,
        "requires_user_confirmation": True,
        "send_requires_yes": True,
        "title": args.title,
        "goal": args.goal,
        "mode": args.mode,
        "allowed_files": allowed_files,
        "allowed_files_count": len(allowed_files),
        "git_status_excerpt_chars": len(str(context.get("git_status_excerpt", ""))),
        "diff_stat_chars": len(str(context.get("diff_stat", ""))),
        "diff_excerpt_chars": len(str(context.get("diff_excerpt", ""))),
        "test_log_excerpt_chars": len(str(context.get("test_log_excerpt", ""))) if "test_log_excerpt" in context else 0,
        "confirmation_text": "确认将这些上下文发送给右侧 ChatGPT 审查；不得包含 secrets、.env、私钥、cookie、.git 内容或完整 Connector URL。",
        "safety": {
            "right_side_chatgpt_can_edit_source": False,
            "right_side_chatgpt_can_execute_shell": False,
            "suggested_actions_require_user_confirmation": True,
        },
    }
    chatgpt_message_mode = getattr(args, "chatgpt_message_mode", None)
    if chatgpt_message_mode:
        preview["post_confirmation_chatgpt_message"] = {
            "available": True,
            "mode": chatgpt_message_mode,
            "output": getattr(args, "chatgpt_message_output", None),
            "requires_real_task_id": True,
            "requires_user_confirmation_before_send": True,
            "auto_send_to_chatgpt": False,
        }
    return preview


def load_chatgpt_message_builder() -> Any:
    path = ROOT / "scripts" / "build_chatgpt_collaboration_message.py"
    spec = importlib.util.spec_from_file_location("build_chatgpt_collaboration_message", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build_chatgpt_collaboration_message.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_output_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    output_path = Path(path_value)
    return output_path if output_path.is_absolute() else ROOT / output_path


def build_chatgpt_context_summary(preview: dict[str, object]) -> str:
    return "\n".join(
        [
            f"- Bridge 已创建真实任务，标题：{preview['title']}",
            f"- 任务模式：{preview['mode']}",
            f"- 允许文件数：{preview['allowed_files_count']}",
            f"- git status 摘要字符数：{preview['git_status_excerpt_chars']}",
            f"- diff stat 字符数：{preview['diff_stat_chars']}",
            f"- diff excerpt 字符数：{preview['diff_excerpt_chars']}",
            f"- test/log 摘要字符数：{preview['test_log_excerpt_chars']}",
            "- 上下文已由 Codex 预览并经用户确认后才创建任务。",
            "- 不要请求 secrets、.env、私钥、cookie、.git、完整 Connector URL 或未允许文件。",
        ]
    )


def build_post_confirmation_chatgpt_message(
    *,
    mode: str,
    output_path: Path | None,
    task_id: str,
    title: str,
    goal: str,
    preview: dict[str, object],
) -> dict[str, object]:
    builder = load_chatgpt_message_builder()
    payload = builder.build_message(
        mode=mode,
        title=title,
        request=goal,
        context_summary=build_chatgpt_context_summary(preview),
        task_id=task_id,
    )
    markdown = builder.render_markdown(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    return {
        "generated": True,
        "mode": payload["mode"],
        "output": str(output_path) if output_path else None,
        "task_id": task_id,
        "task_id_status": payload["task_id_status"],
        "structured_import_ready": payload["structured_import_ready"],
        "requires_real_task_id_for_import": payload["requires_real_task_id_for_import"],
        "requires_user_confirmation_before_send": payload["requires_user_confirmation_before_send"],
        "auto_send_to_chatgpt": False,
        "auto_execute": payload["auto_execute"],
        "copyable_message": payload["copyable_message"] if output_path is None else None,
    }


def print_human_preview(preview: dict[str, object]) -> None:
    print("即将发送右侧 ChatGPT 审查任务：")
    print(f"- 标题：{preview['title']}")
    print(f"- 目标：{preview['goal']}")
    print(f"- 模式：{preview['mode']}")
    print(f"- 允许文件数：{preview['allowed_files_count']}")
    print(f"- git status 摘要字符数：{preview['git_status_excerpt_chars']}")
    print(f"- diff stat 字符数：{preview['diff_stat_chars']}")
    print(f"- diff excerpt 字符数：{preview['diff_excerpt_chars']}")
    print("确认点：")
    print("- 不含 secrets、.env、私钥、cookie、.git 内容或完整 Connector URL。")
    print("- 右侧 ChatGPT 只给建议，不直接改源码，不执行 shell。")
    print("- 回传 suggested_actions 后仍需用户逐条确认。")


def require_confirmation(preview: dict[str, object], *, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        raise SystemExit("user_confirmation_required: re-run with --preview first, then add --yes after manual confirmation")
    print_human_preview(preview)
    answer = input("确认发送请输入 yes：").strip()
    if answer != "yes":
        raise SystemExit("cancelled_by_user")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--mode", default="review")
    parser.add_argument("--allowed-file", action="append", default=[])
    parser.add_argument("--changed-files", action="store_true")
    parser.add_argument("--test-log-file")
    parser.add_argument("--preview", action="store_true", help="Preview task context summary without sending it.")
    parser.add_argument("--yes", action="store_true", help="Send after manual confirmation.")
    parser.add_argument(
        "--chatgpt-message-mode",
        choices=CHATGPT_MESSAGE_MODES,
        help="After confirmed send, generate a ChatGPT collaboration message bound to the real task_id.",
    )
    parser.add_argument(
        "--chatgpt-message-output",
        help="Markdown path for the generated ChatGPT collaboration message. Relative paths are resolved from the repo root.",
    )
    args = parser.parse_args()

    context = build_context(args)
    preview = build_preview(args, context)
    if args.preview:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    require_confirmation(preview, yes=args.yes)

    state = BridgeState(ROOT)
    result = BridgeTools(state).call_tool(
        "bridge_push_task",
        {"title": args.title, "goal": args.goal, "mode": args.mode, "context": context},
        CODEX_LOCAL,
    )
    if args.chatgpt_message_mode:
        task_id = str(result["task_id"])
        result["chatgpt_message"] = build_post_confirmation_chatgpt_message(
            mode=args.chatgpt_message_mode,
            output_path=resolve_output_path(args.chatgpt_message_output),
            task_id=task_id,
            title=args.title,
            goal=args.goal,
            preview=preview,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
