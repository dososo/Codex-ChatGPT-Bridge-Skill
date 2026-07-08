from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from bridge.state import BridgeState
from bridge.tools import BridgeTools, CODEX_LOCAL
from tests.helpers import make_repo


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "intake_chatgpt_result.py"


def load_intake():
    spec = importlib.util.spec_from_file_location("intake_chatgpt_result", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load intake_chatgpt_result.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_task_repo() -> tuple[Path, str]:
    repo = make_repo("intake-chatgpt-result")
    state = BridgeState(repo)
    tools = BridgeTools(state)
    pushed = tools.call_tool(
        "bridge_push_task",
        {"title": "intake", "goal": "preview import", "context": {"allowed_files": []}},
        CODEX_LOCAL,
    )
    return repo, str(pushed["task_id"])


def fenced_result(task_id: str) -> str:
    return f"""
```codex-bridge-result-json
{{
  "schema_version": "1.1",
  "task_id": "{task_id}",
  "summary": "ChatGPT 建议先审阅",
  "findings": [
    {{"severity": "low", "title": "检查", "evidence": "用户提供", "recommendation": "先确认"}}
  ],
  "suggested_actions": [
    {{"label": "运行测试", "command": "python3 -m unittest discover -s tests", "risk": "low"}},
    {{"label": "危险删除", "command": "rm -rf /", "risk": "critical"}}
  ],
  "confidence": "medium"
}}
```
"""


class IntakeChatGPTResultTest(unittest.TestCase):
    def test_preview_valid_result_without_saving(self) -> None:
        repo, task_id = make_task_repo()
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--stdin", "--json", "--repo-root", str(repo)],
            input=fenced_result(task_id),
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        result = json.loads(completed.stdout)

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["preview_only"])
        self.assertFalse(result["imported"])
        self.assertTrue(result["import_ready"])
        self.assertEqual(result["task_id"], task_id)
        self.assertTrue(result["task_exists"])
        self.assertEqual(result["sanitized_preview"]["suggested_actions_count"], 1)
        self.assertEqual(result["sanitized_preview"]["removed_dangerous_commands_count"], 1)
        self.assertTrue(result["ui_actions"]["confirm_import_result"]["enabled"])
        self.assertIn("--repo-root", result["ui_actions"]["preview_intake_result"]["command_argv"])
        self.assertIn(str(repo), result["ui_actions"]["preview_intake_result"]["command_argv"])
        self.assertIn("--repo-root", result["ui_actions"]["confirm_import_result"]["command_argv"])
        self.assertIn(str(repo), result["ui_actions"]["confirm_import_result"]["command_argv"])
        self.assertIn("--repo-root", result["ui_actions"]["review_imported_result"]["command_argv"])
        self.assertIn(str(repo), result["ui_actions"]["review_imported_result"]["command_argv"])
        self.assertFalse(result["ui_actions"]["confirm_import_result"]["auto_execute"])
        self.assertFalse(result["ui_actions"]["review_imported_result"]["enabled"])
        self.assertEqual(BridgeState(repo).result_versions(task_id), [])

    def test_yes_imports_then_enables_review_action(self) -> None:
        repo, task_id = make_task_repo()
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--stdin", "--yes", "--json", "--repo-root", str(repo)],
            input=fenced_result(task_id),
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        result = json.loads(completed.stdout)

        self.assertTrue(result["ok"], result)
        self.assertFalse(result["preview_only"])
        self.assertTrue(result["imported"])
        self.assertEqual(result["import_result"]["status"], "result_saved")
        self.assertTrue(result["ui_actions"]["review_imported_result"]["enabled"])
        self.assertIn("review_result.py", " ".join(result["ui_actions"]["review_imported_result"]["command_argv"]))
        self.assertEqual(BridgeState(repo).result_versions(task_id), [1])

    def test_unknown_task_id_is_rejected_without_import(self) -> None:
        repo, _ = make_task_repo()
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--stdin", "--json", "--repo-root", str(repo)],
            input=fenced_result("unknown"),
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        result = json.loads(completed.stdout)

        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(result["ok"])
        self.assertFalse(result["import_ready"])
        self.assertIn("task_id_missing_or_unknown", result["errors"])
        self.assertIsNone(result["task_id"])
        self.assertNotIn("unknown", result["ui_actions"]["review_imported_result"]["command_argv"])
        self.assertFalse(result["ui_actions"]["confirm_import_result"]["enabled"])
        self.assertTrue(result["safety"]["requires_user_confirmation_before_import"])

    def test_non_string_task_id_is_rejected_without_crashing(self) -> None:
        repo, _ = make_task_repo()
        payload = """
```codex-bridge-result-json
{
  "schema_version": "1.1",
  "task_id": ["not", "a", "string"],
  "summary": "bad id",
  "findings": [],
  "suggested_actions": []
}
```
"""
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--stdin", "--json", "--repo-root", str(repo)],
            input=payload,
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        result = json.loads(completed.stdout)

        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(result["ok"])
        self.assertIn("task_id_missing_or_unknown", result["errors"])
        self.assertFalse(result["ui_actions"]["confirm_import_result"]["enabled"])

    def test_default_repo_actions_still_include_repo_root(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--stdin", "--json"],
            input=fenced_result("unknown"),
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        result = json.loads(completed.stdout)

        self.assertNotEqual(completed.returncode, 0)
        for action_id in ("preview_intake_result", "confirm_import_result", "review_imported_result"):
            command = result["ui_actions"][action_id]["command_argv"]
            self.assertIn("--repo-root", command)
            self.assertIn(str(ROOT), command)


if __name__ == "__main__":
    unittest.main()
