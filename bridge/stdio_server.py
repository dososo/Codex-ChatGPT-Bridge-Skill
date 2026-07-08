from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from .errors import BridgeError
from .mcp_protocol import JSONRPC_PARSE_ERROR, McpResponse, handle_mcp_message
from .state import BridgeState
from .tools import CODEX_LOCAL, BridgeTools


def serve_stdio(repo_root: Path | str, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    """Serve the local Codex MCP surface over newline-delimited stdio JSON-RPC."""
    tools = BridgeTools(BridgeState(Path(repo_root).resolve()))
    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            _write_response(stdout, _parse_error())
            continue
        if not isinstance(payload, dict):
            _write_response(stdout, _parse_error("JSON-RPC message must be an object"))
            continue
        response = handle_mcp_message(tools, payload, CODEX_LOCAL)
        if response.body is not None:
            _write_response(stdout, response)
    return 0


def _write_response(stdout: TextIO, response: McpResponse) -> None:
    if response.body is None:
        return
    stdout.write(json.dumps(response.body, ensure_ascii=False, separators=(",", ":")) + "\n")
    stdout.flush()


def _parse_error(message: str = "parse error") -> McpResponse:
    return McpResponse(
        status=200,
        headers={"Content-Type": "application/json; charset=utf-8"},
        body={"jsonrpc": "2.0", "id": None, "error": {"code": JSONRPC_PARSE_ERROR, "message": message}},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Codex ChatGPT Bridge local MCP server over stdio.")
    parser.add_argument("--repo-root", default=str(Path.cwd()), help="Repository root served by this Bridge instance.")
    args = parser.parse_args(argv)
    try:
        return serve_stdio(args.repo_root)
    except BridgeError as exc:
        print(f"codex-chatgpt-bridge stdio error: {exc.code}: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
