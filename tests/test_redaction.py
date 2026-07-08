from __future__ import annotations

import unittest

from bridge.state import BridgeState
from bridge.tools import BridgeTools, CODEX_LOCAL

from tests.helpers import make_repo


class RedactionTest(unittest.TestCase):
    def test_audit_log_does_not_include_token_values(self) -> None:
        repo = make_repo("redaction")
        state = BridgeState(repo)
        state.init_state()
        token = state.read_token("local")
        tools = BridgeTools(state)

        tools.call_tool("bridge_health", {}, CODEX_LOCAL)
        audit = (state.bridge_dir / "logs" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(token, audit)


if __name__ == "__main__":
    unittest.main()
