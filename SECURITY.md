# Security Policy

Codex ChatGPT Bridge Skill treats right-side ChatGPT as an untrusted collaborator.

## Default Boundary

- The right-side ChatGPT connector cannot edit source files.
- Shell execution is disabled for right-side ChatGPT.
- `.env`, private keys, cookies, `.git`, Bridge tokens, build caches, and common local runtime files are denied.
- Task content, result content, and Packet fallback content pass through secret redaction.
- High-confidence private keys, API keys, OAuth refresh tokens, Bridge token values, and full Connector URLs are blocked or redacted.
- Suggested commands are suggestions only and require user confirmation before Codex may run them.
- Remote MCP endpoint paths are redacted in audit logs.
- Codex owns local execution, tests, and diffs.

## Reporting

Do not include secrets, full Connector URLs, tokens, private keys, private repository content, cookies, or account screenshots in reports.

Useful reports include:

- Sanitized command output.
- The operating system and Python version.
- The selected workflow: task brief, review, Connector, read-only, or Packet fallback.
- Whether ChatGPT UI showed a real tool call.

## Known External Limits

Local tests cannot prove that a specific ChatGPT account or model can call MCP tools. Full Connector capability must be verified with real official tool calls and audit evidence in the user's environment.
