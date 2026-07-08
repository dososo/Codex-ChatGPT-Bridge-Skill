from __future__ import annotations

import unittest

from bridge.state import BridgeState
from bridge.tools import BridgeTools, CHATGPT_REMOTE, CODEX_LOCAL

from tests.helpers import make_repo


class TaskFlowTest(unittest.TestCase):
    def test_push_pull_send_pull_result_flow(self) -> None:
        repo = make_repo("task-flow")
        tools = BridgeTools(BridgeState(repo))

        pushed = tools.call_tool(
            "bridge_push_task",
            {
                "title": "审查 demo",
                "goal": "检查 allowed file 和结果回传",
                "mode": "review",
                "context": {"allowed_files": ["src/app.py"], "diff_excerpt": "diff --git a/src/app.py b/src/app.py"},
            },
            CODEX_LOCAL,
        )
        self.assertEqual(pushed["status"], "queued")

        fetched = tools.call_tool("bridge_fetch_task_packet", {}, CHATGPT_REMOTE)
        self.assertEqual(fetched["task_id"], pushed["task_id"])
        self.assertIsNone(fetched["claim_id"])
        self.assertFalse(fetched["claim_required_for_writeback"])
        self.assertIn("codex-bridge-result-json", fetched["result_return_instructions"])
        self.assertIn("Codex Bridge Packet", fetched["packet_markdown"])

        queued = tools.state.load_task(pushed["task_id"])
        self.assertEqual(queued["status"], "queued")
        self.assertIsNone(queued["claim_id"])

        pulled = tools.call_tool("bridge_pull_task", {}, CHATGPT_REMOTE)
        self.assertEqual(pulled["task_id"], pushed["task_id"])
        self.assertNotIn("claim_id", pulled["task"])

        read = tools.call_tool(
            "bridge_read_allowed_file",
            {"task_id": pulled["task_id"], "claim_id": pulled["claim_id"], "path": "src/app.py"},
            CHATGPT_REMOTE,
        )
        self.assertIn("def add", read["content"])

        sent = tools.call_tool(
            "bridge_send_result",
            {
                "task_id": pulled["task_id"],
                "claim_id": pulled["claim_id"],
                "summary": "整体可用",
                "findings": [{"severity": "high", "title": "缺测试", "evidence": "只有示例", "recommendation": "补测试"}],
                "suggested_actions": [
                    {"label": "运行测试", "command": "python -m unittest discover -s tests", "risk": "low"},
                    {"label": "危险命令", "command": "rm -rf /", "risk": "high"},
                ],
                "confidence": "medium",
            },
            CHATGPT_REMOTE,
        )
        self.assertEqual(sent["status"], "result_saved")
        self.assertEqual(len(sent["removed_dangerous_commands"]), 1)

        result = tools.call_tool("bridge_pull_result", {"task_id": pushed["task_id"]}, CODEX_LOCAL)
        self.assertEqual(result["status"], "acknowledged")
        self.assertIn("整体可用", result["result_markdown"])
        self.assertTrue(result["suggested_actions"][0]["requires_user_confirmation"])


if __name__ == "__main__":
    unittest.main()
