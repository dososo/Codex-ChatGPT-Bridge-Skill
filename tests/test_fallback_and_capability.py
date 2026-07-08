from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

from bridge.capabilities import FULL_CONNECTOR, PACKET_OR_MANUAL, READ_ONLY_CONNECTOR
from bridge.state import BridgeState
from bridge.tools import BridgeTools, CHATGPT_REMOTE, CODEX_LOCAL

from tests.helpers import make_repo


ROOT = Path(__file__).resolve().parents[1]


def load_import_result_script():
    scripts_dir = ROOT / ".agents" / "skills" / "codex-chatgpt-bridge" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    path = scripts_dir / "import_result.py"
    spec = importlib.util.spec_from_file_location("import_result_script", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load import_result.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FallbackCapabilityTest(unittest.TestCase):
    def test_capability_classification(self) -> None:
        repo = make_repo("capability")
        tools = BridgeTools(BridgeState(repo))
        self.assertEqual(tools.update_capability_mode(read_ok=True, write_ok=True), FULL_CONNECTOR)
        self.assertEqual(tools.update_capability_mode(read_ok=True, write_ok=False), READ_ONLY_CONNECTOR)
        self.assertEqual(tools.update_capability_mode(read_ok=False, write_ok=False), PACKET_OR_MANUAL)

    def test_import_result_and_packet(self) -> None:
        repo = make_repo("fallback")
        state = BridgeState(repo)
        tools = BridgeTools(state)
        pushed = tools.call_tool(
            "bridge_push_task",
            {"title": "fallback", "goal": "test fallback", "context": {"allowed_files": ["src/app.py"]}},
            CODEX_LOCAL,
        )
        pulled = tools.call_tool("bridge_pull_task", {}, CHATGPT_REMOTE)
        imported = tools.import_result(
            {
                "task_id": pushed["task_id"],
                "claim_id": pulled["claim_id"],
                "summary": "manual import ok",
                "findings": [],
                "suggested_actions": [],
            }
        )
        self.assertEqual(imported["status"], "result_saved")

        packet = tools.build_packet({"task_id": pushed["task_id"]})
        self.assertTrue((repo / packet["packet_markdown"]).exists())
        self.assertTrue((repo / packet["packet_zip"]).exists())

    def test_packet_uses_same_security_pipeline(self) -> None:
        repo = make_repo("packet-security")
        tools = BridgeTools(BridgeState(repo))
        gcp_key = "AIza" + ("A" * 35)
        connector_url = "https://bridge.example.invalid/mcp/remote/" + ("t" * 24)

        packet = tools.build_packet(
            {
                "title": "packet security",
                "goal": "verify packet security pipeline",
                "context": {
                    "allowed_files": [".env", "src/app.py"],
                    "diff_excerpt": f"{gcp_key}\n{connector_url}",
                },
            }
        )

        packet_text = (repo / packet["packet_markdown"]).read_text(encoding="utf-8")
        context_json = packet_text.split("```json\n", 1)[1].split("\n```", 1)[0]
        packet_context = json.loads(context_json)
        self.assertNotIn(gcp_key, packet_text)
        self.assertNotIn(connector_url, packet_text)
        self.assertNotIn(".env", json.dumps(packet_context, ensure_ascii=False))
        self.assertIn("[REDACTED]", packet_text)
        self.assertIn("path_hash", packet_context["rejected_files"][0])

    def test_manual_fenced_json_can_be_imported_without_claim(self) -> None:
        repo = make_repo("manual-fallback")
        state = BridgeState(repo)
        tools = BridgeTools(state)
        pushed = tools.call_tool(
            "bridge_push_task",
            {"title": "manual", "goal": "manual fallback", "context": {"allowed_files": []}},
            CODEX_LOCAL,
        )
        script = load_import_result_script()
        fenced = f"""
```codex-bridge-result-json
{{
  "schema_version": "1.1",
  "task_id": "{pushed["task_id"]}",
  "summary": "manual result imported",
  "findings": [],
  "suggested_actions": [],
  "confidence": "medium"
}}
```
"""
        payload = script.extract_json(fenced)
        imported = tools.import_result(payload)

        self.assertEqual(imported["status"], "result_saved")
        self.assertTrue((repo / imported["result_path"]).is_file())

    def test_low_level_import_and_pull_result_accept_repo_root(self) -> None:
        repo = make_repo("low-level-import-repo-root")
        state = BridgeState(repo)
        tools = BridgeTools(state)
        pushed = tools.call_tool(
            "bridge_push_task",
            {"title": "manual", "goal": "manual fallback", "context": {"allowed_files": []}},
            CODEX_LOCAL,
        )
        payload = f"""
```codex-bridge-result-json
{{
  "schema_version": "1.1",
  "task_id": "{pushed["task_id"]}",
  "summary": "manual result imported",
  "findings": [],
  "suggested_actions": [],
  "confidence": "medium"
}}
```
"""
        scripts_dir = ROOT / ".agents" / "skills" / "codex-chatgpt-bridge" / "scripts"
        imported = subprocess.run(
            [sys.executable, str(scripts_dir / "import_result.py"), "--stdin", "--repo-root", str(repo)],
            input=payload,
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        imported_payload = json.loads(imported.stdout)
        self.assertEqual(imported_payload["status"], "result_saved")

        pulled = subprocess.run(
            [sys.executable, str(scripts_dir / "pull_result.py"), "--task-id", str(pushed["task_id"]), "--repo-root", str(repo), "--json"],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        pulled_payload = json.loads(pulled.stdout)
        self.assertEqual(pulled_payload["task_id"], pushed["task_id"])
        self.assertIn("manual result imported", pulled_payload["result_markdown"])


if __name__ == "__main__":
    unittest.main()
