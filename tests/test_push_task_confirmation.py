from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUSH_TASK = ROOT / ".agents" / "skills" / "codex-chatgpt-bridge" / "scripts" / "push_task.py"


class PushTaskConfirmationTest(unittest.TestCase):
    def test_preview_does_not_require_confirmation_or_send(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PUSH_TASK),
                "--title",
                "preview",
                "--goal",
                "确认发送预览",
                "--allowed-file",
                "README.md",
                "--preview",
            ],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        preview = json.loads(completed.stdout)

        self.assertTrue(preview["would_send"])
        self.assertTrue(preview["requires_user_confirmation"])
        self.assertTrue(preview["send_requires_yes"])
        self.assertEqual(preview["mode"], "review")
        self.assertEqual(preview["allowed_files"], ["README.md"])
        self.assertFalse(preview["safety"]["right_side_chatgpt_can_edit_source"])
        self.assertTrue(preview["safety"]["suggested_actions_require_user_confirmation"])

    def test_preview_can_use_plan_mode_for_task_brief(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PUSH_TASK),
                "--title",
                "task brief",
                "--goal",
                "生成 Codex 任务单",
                "--mode",
                "plan",
                "--preview",
            ],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        preview = json.loads(completed.stdout)

        self.assertEqual(preview["mode"], "plan")
        self.assertTrue(preview["requires_user_confirmation"])
        self.assertTrue(preview["send_requires_yes"])

    def test_preview_declares_post_confirmation_chatgpt_message_without_sending(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PUSH_TASK),
                "--title",
                "task brief",
                "--goal",
                "生成 Codex 任务单",
                "--mode",
                "plan",
                "--chatgpt-message-mode",
                "task-brief",
                "--chatgpt-message-output",
                ".ai-bridge-test-runs/test-push-task-preview-message.md",
                "--preview",
            ],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        preview = json.loads(completed.stdout)

        message = preview["post_confirmation_chatgpt_message"]
        self.assertTrue(message["available"])
        self.assertEqual(message["mode"], "task-brief")
        self.assertTrue(message["requires_real_task_id"])
        self.assertTrue(message["requires_user_confirmation_before_send"])
        self.assertFalse(message["auto_send_to_chatgpt"])

    def test_confirmed_send_can_generate_task_bound_chatgpt_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "task-bound-message.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PUSH_TASK),
                    "--title",
                    "confirmed task",
                    "--goal",
                    "生成带真实 task_id 的任务单消息。",
                    "--mode",
                    "plan",
                    "--allowed-file",
                    "README.md",
                    "--chatgpt-message-mode",
                    "task-brief",
                    "--chatgpt-message-output",
                    str(output),
                    "--yes",
                ],
                cwd=str(ROOT),
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            result = json.loads(completed.stdout)

            self.assertEqual(result["status"], "queued")
            task_id = result["task_id"]
            message = result["chatgpt_message"]
            self.assertTrue(message["generated"])
            self.assertEqual(message["mode"], "task-brief")
            self.assertEqual(message["task_id"], task_id)
            self.assertEqual(message["task_id_status"], "provided")
            self.assertTrue(message["structured_import_ready"])
            self.assertTrue(message["requires_real_task_id_for_import"])
            self.assertTrue(message["requires_user_confirmation_before_send"])
            self.assertFalse(message["auto_send_to_chatgpt"])
            self.assertFalse(message["auto_execute"])
            self.assertEqual(message["output"], str(output))
            self.assertIsNone(message["copyable_message"])
            text = output.read_text(encoding="utf-8")
            self.assertIn(task_id, text)
            self.assertIn(f"task_id 字段必须是：{task_id}", text)
            self.assertNotIn("/mcp/remote/", text)

    def test_non_interactive_send_requires_explicit_yes(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PUSH_TASK),
                "--title",
                "no confirm",
                "--goal",
                "should fail without yes",
            ],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("user_confirmation_required", completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
