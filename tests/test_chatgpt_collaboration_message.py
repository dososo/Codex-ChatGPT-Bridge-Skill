from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_chatgpt_collaboration_message.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_chatgpt_collaboration_message", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build_chatgpt_collaboration_message.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChatGptCollaborationMessageTest(unittest.TestCase):
    def test_task_brief_message_uses_safe_task_template(self) -> None:
        builder = load_builder()
        result = builder.build_message(
            mode="task-brief",
            title="小计算器修复",
            request="修复 divide 行为。",
            context_summary="只允许查看 mini-calculator 相关文件。",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "task-brief")
        self.assertEqual(result["default_mode"], "automated_collaboration")
        self.assertTrue(result["requires_user_confirmation_before_send"])
        self.assertFalse(result["auto_execute"])
        self.assertFalse(result["sends_context"])
        self.assertEqual(result["task_id_status"], "missing")
        self.assertTrue(result["requires_real_task_id_for_import"])
        self.assertFalse(result["structured_import_ready"])
        contract = result["codex_result_intake_contract"]
        self.assertTrue(contract["codex_uses_repo_bound_actions"])
        self.assertTrue(contract["right_side_should_not_tell_user_to_run_local_commands"])
        self.assertTrue(contract["preview_before_import"])
        message = result["copyable_message"]
        self.assertIn("当前 ChatGPT Pro", message)
        self.assertIn("没有真实工具入口", message)
        self.assertIn("本消息中的受控上下文", message)
        self.assertIn("请先不要写代码", message)
        self.assertIn("原始问题", message)
        self.assertIn("可直接粘贴给 Codex 的执行提示词", message)
        self.assertIn("result_type 必须是 task_brief", message)
        self.assertIn("task_brief.validation_commands", message)
        self.assertIn("task_brief.codex_execution_prompt", message)
        self.assertIn("不执行 shell", message)
        self.assertIn("不直接修改源码", message)
        self.assertIn("suggested_actions", message)
        self.assertIn("用户确认", message)
        self.assertIn("不要要求用户手写本地导入或审阅命令", message)
        self.assertIn("session 状态卡", message)
        self.assertIn("repo-bound pull / intake / import / review", message)
        self.assertIn("summary", message)
        self.assertIn("必须放在 JSON 顶层", message)
        self.assertIn("当前消息没有真实 Bridge task_id", message)
        self.assertIn("不能导入 Codex", message)
        self.assertIn("不要输出把 `task_id` 写成 `unknown`", message)
        self.assertNotIn("创建 Connector", message)
        self.assertIn("仅生成消息时不会打开 ChatGPT 网页", result["will_not_do"][0])
        self.assertIn("真实 ChatGPT 已收到该消息", result["external_not_proven"])

    def test_review_message_uses_structured_result_template(self) -> None:
        builder = load_builder()
        result = builder.build_message(
            mode="review",
            title="执行结果审查",
            request="审查 Codex 已完成的修复。",
            context_summary="只允许使用用户确认后的 diff 和测试输出。",
            task_id="task_123",
            execution_summary="测试已通过。",
        )

        message = result["copyable_message"]
        self.assertEqual(result["mode"], "review")
        self.assertEqual(result["task_id_status"], "provided")
        self.assertTrue(result["structured_import_ready"])
        self.assertIn("审查 Codex 已完成的执行结果", message)
        self.assertIn("diff 风险", message)
        self.assertIn("测试遗漏", message)
        self.assertIn("codex-bridge-result-json", message)
        self.assertIn("task_123", message)
        self.assertIn("task_id 字段必须是：task_123", message)
        self.assertIn("Codex 会读取当前 session 状态卡", message)
        self.assertIn("测试已通过。", message)

    def test_cli_writes_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "message.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--mode",
                    "task-brief",
                    "--title",
                    "任务单",
                    "--request",
                    "整理需求。",
                    "--output",
                    str(output),
                    "--json",
                ],
                cwd=str(ROOT),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            result = json.loads(completed.stdout)

            self.assertEqual(result["output"], str(output))
            self.assertTrue(output.is_file())
            text = output.read_text(encoding="utf-8")
            self.assertIn("ChatGPT 协同消息", text)
            self.assertIn("可直接发送给 ChatGPT 的消息", text)
            self.assertNotIn("/mcp/remote/", text)

    def test_cli_output_message_hides_local_path_without_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "message.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--mode",
                    "task-brief",
                    "--title",
                    "任务单",
                    "--request",
                    "整理需求。",
                    "--output",
                    str(output),
                ],
                cwd=str(ROOT),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )

            self.assertTrue(output.is_file())
            self.assertIn("已生成 ChatGPT 协同消息。", completed.stdout)
            self.assertNotIn(str(output), completed.stdout)
            self.assertNotIn("已写入：", completed.stdout)


if __name__ == "__main__":
    unittest.main()
