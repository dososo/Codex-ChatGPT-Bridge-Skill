from __future__ import annotations

import unittest

from bridge.errors import BridgeError
from bridge.secret_scan import scan_text
from bridge.state import BridgeState
from bridge.tools import BridgeTools, CODEX_LOCAL

from tests.helpers import make_repo


class SecretScanTest(unittest.TestCase):
    def test_redacts_common_tokens_and_blocks_private_keys(self) -> None:
        sample_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
        redacted = scan_text(f"key={sample_key}")
        self.assertFalse(redacted["blocked"])
        self.assertIn("[REDACTED]", redacted["redacted"])

        private_key = "-----BEGIN " + "PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
        blocked = scan_text(private_key)
        self.assertTrue(blocked["blocked"])

    def test_redacts_cloud_keys_and_connector_urls(self) -> None:
        gcp_key = "AIza" + ("A" * 35)
        azure_key = "AccountKey=" + ("b" * 44)
        sas_url = "https://acct.blob.core.windows.net/container?sv=2024-01-01&sig=" + ("c" * 32)
        connector_url = "https://bridge.example.invalid/mcp/remote/" + ("r" * 24)
        payload = "\n".join([gcp_key, azure_key, sas_url, connector_url])

        scan = scan_text(payload)
        finding_types = {item["type"] for item in scan["findings"]}

        self.assertFalse(scan["blocked"])
        self.assertIn("gcp_api_key", finding_types)
        self.assertIn("azure_storage_account_key", finding_types)
        self.assertIn("azure_sas_signature", finding_types)
        self.assertIn("connector_url", finding_types)
        self.assertNotIn(gcp_key, scan["redacted"])
        self.assertNotIn(azure_key, scan["redacted"])
        self.assertNotIn("sig=" + ("c" * 32), scan["redacted"])
        self.assertNotIn(connector_url, scan["redacted"])

    def test_push_blocks_bridge_token_value(self) -> None:
        repo = make_repo("secret-push")
        state = BridgeState(repo)
        state.init_state()
        token = state.read_token("remote")
        tools = BridgeTools(state)
        with self.assertRaises(BridgeError) as ctx:
            tools.call_tool(
                "bridge_push_task",
                {"title": "secret", "goal": "must block", "context": {"diff_excerpt": token, "allowed_files": []}},
                CODEX_LOCAL,
            )
        self.assertEqual(ctx.exception.code, "secret_blocked")


if __name__ == "__main__":
    unittest.main()
