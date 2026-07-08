from __future__ import annotations

import os
import json
import unittest

from bridge.errors import BridgeError
from bridge.state import BridgeState
from bridge.security import validate_repo_file
from bridge.tools import BridgeTools, CODEX_LOCAL

from tests.helpers import make_repo


class PathSafetyTest(unittest.TestCase):
    def test_denies_env_git_and_traversal(self) -> None:
        repo = make_repo("path-safety")
        (repo / ".env").write_text("OPENAI_API_KEY=sk-test", encoding="utf-8")
        (repo / ".git").mkdir()

        for path in [".env", ".git/config", "../outside.txt"]:
            with self.assertRaises(BridgeError):
                validate_repo_file(repo, path)

    def test_denies_windows_path_variants(self) -> None:
        repo = make_repo("path-windows")
        for path in [
            "..\\outside.txt",
            "\\\\server\\share\\secret.txt",
            "//server/share/secret.txt",
            "C:\\Users\\user\\.env",
            ".ENV",
            "PROGRA~1/secret.txt",
            "src/SECRET~1.TXT",
        ]:
            with self.assertRaises(BridgeError):
                validate_repo_file(repo, path)

    def test_denies_symlink_to_secret(self) -> None:
        repo = make_repo("path-symlink")
        (repo / ".env").write_text("secret=value", encoding="utf-8")
        link = repo / "src" / "link_env"
        try:
            os.symlink(repo / ".env", link)
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaises(BridgeError) as ctx:
            validate_repo_file(repo, "src/link_env")
        self.assertEqual(ctx.exception.code, "path_denied")

    def test_rejected_allowed_files_are_hashed_in_task_and_audit(self) -> None:
        repo = make_repo("path-audit")
        (repo / ".env").write_text("secret=value", encoding="utf-8")
        state = BridgeState(repo)
        tools = BridgeTools(state)

        result = tools.call_tool(
            "bridge_push_task",
            {
                "title": "路径审计",
                "goal": "验证拒绝路径不落原文",
                "context": {"allowed_files": [".env", "../outside.txt", "src/app.py"]},
            },
            CODEX_LOCAL,
        )

        rejected = result["rejected_files"]
        self.assertEqual(len(rejected), 2)
        for item in rejected:
            self.assertTrue(item["path_redacted"])
            self.assertIn("path_hash", item)
            self.assertNotIn("path", item)

        task = json.loads(state.task_path(result["task_id"]).read_text(encoding="utf-8"))
        task_text = json.dumps(task, ensure_ascii=False)
        audit = (state.bridge_dir / "logs" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(".env", task_text)
        self.assertNotIn("../outside.txt", task_text)
        self.assertNotIn(".env", audit)
        self.assertNotIn("../outside.txt", audit)
        self.assertIn('"kind": "path_rejection"', audit)
        self.assertIn('"path_hash"', audit)


if __name__ == "__main__":
    unittest.main()
