from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from bridge.state import BridgeState
from bridge.tools import BridgeTools, CHATGPT_REMOTE, CODEX_LOCAL
from tests.helpers import make_repo


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / ".agents" / "skills" / "codex-chatgpt-bridge" / "scripts"


def load_review_result():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    path = SCRIPTS_DIR / "review_result.py"
    spec = importlib.util.spec_from_file_location("review_result", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load review_result.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_result_repo() -> tuple[Path, str]:
    repo = make_repo("review-result")
    state = BridgeState(repo)
    tools = BridgeTools(state)
    pushed = tools.call_tool(
        "bridge_push_task",
        {"title": "review", "goal": "review result", "context": {"allowed_files": []}},
        CODEX_LOCAL,
    )
    pulled = tools.call_tool("bridge_pull_task", {}, CHATGPT_REMOTE)
    tools.call_tool(
        "bridge_send_result",
        {
            "task_id": pulled["task_id"],
            "claim_id": pulled["claim_id"],
            "summary": "结果需要人工确认",
            "findings": [{"severity": "medium", "title": "测试缺口", "evidence": "无", "recommendation": "补测试"}],
            "suggested_actions": [
                {"label": "运行单测", "command": "python3 -m unittest discover -s tests", "risk": "low"},
                {"label": "危险删除", "command": "rm -rf .", "risk": "critical"},
            ],
            "confidence": "medium",
        },
        CHATGPT_REMOTE,
    )
    return repo, str(pushed["task_id"])


class ReviewResultTest(unittest.TestCase):
    def test_review_latest_marks_actions_for_user_confirmation(self) -> None:
        script = load_review_result()
        repo, task_id = make_result_repo()

        review = script.review_latest(repo, task_id)

        self.assertTrue(review["ok"])
        self.assertFalse(review["execution_allowed_by_this_script"])
        self.assertEqual(review["suggested_actions_count"], 1)
        self.assertEqual(review["removed_dangerous_commands_count"], 1)
        action = review["suggested_actions_review"][0]
        self.assertTrue(action["requires_user_confirmation"])
        self.assertFalse(action["execution_allowed_by_this_script"])
        self.assertEqual(action["approval_status"], "needs_user_review")

    def test_render_text_states_no_execution(self) -> None:
        script = load_review_result()
        repo, task_id = make_result_repo()
        text = script.render_text(script.review_latest(repo, task_id))

        self.assertIn("本脚本不会执行", text)
        self.assertIn("已剔除危险命令", text)
        self.assertIn("确认清单", text)

    def test_cli_json_reads_current_result(self) -> None:
        repo, _ = make_result_repo()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "review_result.py"), "--repo-root", str(repo), "--json"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=True,
        )
        result = json.loads(completed.stdout)

        self.assertEqual(result["summary"], "结果需要人工确认")
        self.assertFalse(result["execution_allowed_by_this_script"])

    def test_manual_import_preserves_text_actions_and_patch_suggestion(self) -> None:
        script = load_review_result()
        repo = make_repo("review-result-manual-import")
        state = BridgeState(repo)
        tools = BridgeTools(state)
        pushed = tools.call_tool(
            "bridge_push_task",
            {"title": "manual", "goal": "review manual result", "context": {"allowed_files": []}},
            CODEX_LOCAL,
        )

        tools.import_result(
            {
                "task_id": pushed["task_id"],
                "summary": "需要把整数整除改为普通除法",
                "suggested_patch": {
                    "file": "examples/mini-calculator/calculator.py",
                    "minimal_change": "将 return left // right 修改为 return left / right",
                    "proposed_diff": "-    return left // right\n+    return left / right\n",
                },
                "suggested_actions": ["用户确认后只修改 divide 的返回语句"],
            }
        )

        review = script.review_latest(repo, str(pushed["task_id"]))

        self.assertEqual(review["suggested_actions_count"], 2)
        self.assertFalse(review["execution_allowed_by_this_script"])
        actions = review["suggested_actions_review"]
        self.assertEqual(actions[0]["type"], "manual_instruction")
        self.assertIn("用户确认后", actions[0]["label"])
        self.assertEqual(actions[1]["type"], "patch_suggestion")
        self.assertIn("return left / right", actions[1]["details"])

    def test_task_brief_import_gets_reviewed_without_execution(self) -> None:
        script = load_review_result()
        repo = make_repo("review-result-task-brief")
        state = BridgeState(repo)
        tools = BridgeTools(state)
        pushed = tools.call_tool(
            "bridge_push_task",
            {"title": "task brief", "goal": "make a plan", "context": {"allowed_files": []}},
            CODEX_LOCAL,
        )

        tools.import_result(
            {
                "task_id": pushed["task_id"],
                "result_type": "task_brief",
                "summary": "建议按最小修改执行",
                "task_brief": {
                    "original_problem": "修复 divide 行为。",
                    "expected_result": "除法返回普通除法结果。",
                    "unchanged_behaviors": ["add/subtract 不变"],
                    "possible_files": ["examples/mini-calculator/calculator.py"],
                    "minimal_plan": ["只改 divide 返回表达式"],
                    "validation_commands": [
                        {"label": "运行 mini-calculator 测试", "command": "python3 -m unittest discover -s examples/mini-calculator -p 'test_*.py'", "risk": "low"},
                        {"label": "危险验证", "command": "rm -rf .", "risk": "critical"},
                    ],
                    "stop_conditions": ["需要读取 secrets 时停止"],
                    "codex_execution_prompt": "请严格按任务单执行，只修改必要文件。",
                },
                "suggested_actions": [],
            }
        )

        review = script.review_latest(repo, str(pushed["task_id"]))
        text = script.render_text(review)

        self.assertEqual(review["result_type"], "task_brief")
        self.assertTrue(review["task_brief_present"])
        self.assertEqual(review["task_brief_validation_commands_count"], 1)
        self.assertEqual(review["removed_dangerous_commands_count"], 1)
        validation_action = review["task_brief_validation_commands_review"][0]
        self.assertTrue(validation_action["requires_user_confirmation"])
        self.assertFalse(validation_action["execution_allowed_by_this_script"])
        self.assertIn("ChatGPT 任务单", text)
        self.assertIn("待用户确认的 Codex 执行提示词", text)
        self.assertIn("本脚本不会执行", text)


if __name__ == "__main__":
    unittest.main()
