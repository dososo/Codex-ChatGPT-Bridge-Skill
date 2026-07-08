from __future__ import annotations

import unittest

from bridge.errors import BridgeError
from bridge.mcp_protocol import tool_descriptors_for_role
from bridge.state import BridgeState
from bridge.tools import BridgeTools, CHATGPT_REMOTE, CODEX_LOCAL

from tests.helpers import make_repo


class ToolSchemasTest(unittest.TestCase):
    def test_unknown_tool_is_rejected(self) -> None:
        tools = BridgeTools(BridgeState(make_repo("tool-schema")))
        with self.assertRaises(BridgeError) as ctx:
            tools.call_tool("bridge_run_safe_command", {}, CODEX_LOCAL)
        self.assertEqual(ctx.exception.code, "unknown_tool")

    def test_chatgpt_apps_required_tool_annotations_are_complete(self) -> None:
        descriptors = tool_descriptors_for_role(CODEX_LOCAL) + tool_descriptors_for_role(CHATGPT_REMOTE)
        self.assertGreater(len(descriptors), 0)

        writable = {
            "bridge_push_task",
            "bridge_pull_task",
            "bridge_send_result",
            "bridge_pull_result",
            "bridge_cancel_task",
            "bridge_write_patch_suggestion",
        }
        destructive = {"bridge_cancel_task"}

        for descriptor in descriptors:
            name = str(descriptor["name"])
            annotations = descriptor.get("annotations", {})
            self.assertIsInstance(annotations.get("readOnlyHint"), bool, name)
            self.assertIsInstance(annotations.get("destructiveHint"), bool, name)
            self.assertIsInstance(annotations.get("openWorldHint"), bool, name)
            self.assertIsInstance(annotations.get("idempotentHint"), bool, name)
            self.assertEqual(annotations["readOnlyHint"], name not in writable, name)
            self.assertEqual(annotations["destructiveHint"], name in destructive, name)
            self.assertFalse(annotations["openWorldHint"], name)
            self.assertEqual(annotations["idempotentHint"], name not in writable, name)
            self.assertEqual(descriptor.get("securitySchemes"), [{"type": "noauth"}], name)
            meta = descriptor.get("_meta", {})
            self.assertEqual(meta.get("securitySchemes"), [{"type": "noauth"}], name)
            self.assertEqual(meta.get("ui", {}).get("visibility"), ["model"], name)

        remote_names = {descriptor["name"] for descriptor in tool_descriptors_for_role(CHATGPT_REMOTE)}
        self.assertIn("bridge_fetch_task_packet", remote_names)

    def test_send_result_schema_exposes_task_brief(self) -> None:
        descriptors = {descriptor["name"]: descriptor for descriptor in tool_descriptors_for_role(CHATGPT_REMOTE)}
        schema = descriptors["bridge_send_result"]["inputSchema"]
        properties = schema["properties"]

        self.assertIn("task_brief", properties)
        task_brief = properties["task_brief"]
        self.assertIn("codex_execution_prompt", task_brief["properties"])
        self.assertIn("validation_commands", task_brief["properties"])


if __name__ == "__main__":
    unittest.main()
