from __future__ import annotations

import unittest

from bridge.state import BridgeState
from bridge.tools import BridgeTools, CHATGPT_REMOTE, CODEX_LOCAL

from tests.helpers import make_repo


class BridgeHealthTest(unittest.TestCase):
    def test_health_and_remote_roots_are_role_scoped(self) -> None:
        repo = make_repo("bridge-health")
        tools = BridgeTools(BridgeState(repo))

        health = tools.call_tool("bridge_health", {}, CODEX_LOCAL)
        self.assertEqual(health["repo"]["root"], str(repo))

        roots = tools.call_tool("bridge_list_allowed_roots_redacted", {}, CHATGPT_REMOTE)
        self.assertTrue(roots["roots"][0]["path_redacted"])
        self.assertNotIn(str(repo), str(roots))


if __name__ == "__main__":
    unittest.main()
