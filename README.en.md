# Codex ChatGPT Bridge Skill

> A controlled collaboration bridge between Codex and right-side ChatGPT: ChatGPT plans and reviews, while Codex reads the repository, edits code, runs tests, and owns the final diff.

[中文说明](README.md)

![Codex ChatGPT Bridge flow](assets/screenshots/codex-chatgpt-bridge-flow.svg)

<p align="center">
  <img src="assets/screenshots/chatgpt-collaboration-loop.png" alt="Codex and right-side ChatGPT collaboration UI" width="920">
</p>

<p align="center">
  <sub>Codex owns local execution and verification. Right-side ChatGPT plans, audits, and returns structured suggestions. Real Connector capability is still determined by tool calls and audit records.</sub>
</p>

## Quick Start

Open this repository in Codex Desktop and ask:

```text
Use codex-chatgpt-bridge to let ChatGPT help plan this task. Run the local preflight first, prepare the message for ChatGPT, and ask me before sending. Do not read secrets, .env, private keys, cookies, or .git. Do not execute ChatGPT suggestions.
```

For a post-change review:

```text
Use codex-chatgpt-bridge to send the current Codex execution result to ChatGPT for review. Only send the diff, test output, and minimal context that I confirm. ChatGPT suggestions must return to Codex for review before I approve any execution.
```

Manual commands:

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py --dry-run --json
python .agents/skills/codex-chatgpt-bridge/scripts/first_run.py
python scripts/build_chatgpt_collaboration_session.py --dry-run
```

## What It Is

Codex ChatGPT Bridge Skill is a local-first Codex Skill and MCP Bridge. It does not give ChatGPT free access to your repository, and it does not let ChatGPT directly edit code.

The roles are intentionally strict:

| Role | Does | Does not do |
| --- | --- | --- |
| Codex | Reads local files, edits code, runs commands, fixes tests, produces verification evidence | Does not blindly execute untrusted suggestions |
| ChatGPT | Clarifies requirements, compares options, writes Codex task briefs, reviews diffs and risks | Does not edit source, run shell commands, or read secrets |
| Bridge | Packages minimal context, syncs task and result data, enforces permissions, records audit data | Does not turn local smoke tests into fake external verification |
| User | Approves context sharing, app connection, result import, and execution | Does not need to understand internal MCP modes |

The practical workflow is simple: ask ChatGPT to turn an unclear request into a one-page Codex task brief, then let Codex execute that brief. After Codex finishes, send the diff and test evidence back to ChatGPT for review, import the structured result, and let Codex produce a review checklist.

## What You Get

A typical run:

1. Codex performs local preflight, Bridge status checks, and minimal context preparation.
2. After user confirmation, Codex opens right-side ChatGPT and sends a task brief or review request.
3. ChatGPT only plans or audits and returns structured feedback.
4. Codex previews/imports the result and turns it into a review checklist.
5. The user approves any action before Codex executes it.

Benefits:

- Clearer task boundaries before Codex enters the repository.
- ChatGPT can be used for planning, architecture discussion, and review.
- Codex keeps control over local code, commands, tests, and diffs.
- If official Connector tools are unavailable, the workflow falls back to controlled messages and structured import.

## Core Capabilities

| Capability | Entry | Result |
| --- | --- | --- |
| First-run clinic | `first_run.py` | Shows the current safe collaboration path |
| One-click preflight | `verify_first_use.py` | Runs local setup/status/smoke/material preview |
| Task brief | `build_chatgpt_collaboration_message.py --mode task-brief` | Creates a ChatGPT prompt for a Codex execution brief |
| Result review | `build_chatgpt_collaboration_message.py --mode review` | Creates a ChatGPT prompt for diff/test review |
| Controlled task sync | `bridge_push_task` / `bridge_fetch_task_packet` / `bridge_pull_task` | Lets ChatGPT read the minimal task packet |
| Structured import | `intake_chatgpt_result.py --stdin` | Validates ChatGPT JSON before import |
| Review checklist | `review_result.py` | Converts ChatGPT feedback into Codex-readable review output |
| Packet fallback | `build_packet.py` | Creates a redacted packet when tools are unavailable |

## Example

Run the beginner-friendly calculator example:

```bash
python -m unittest discover -s examples/mini-calculator -p 'test_*.py'
```

The example demonstrates the real loop: Codex prepares a small task, ChatGPT provides untrusted feedback, Codex reviews it, the user confirms, and Codex verifies the final behavior.

## First Use

Regular users should not need to understand Full Connector, Read-only, Packet, or Manual modes. The interface should show only:

1. Whether ChatGPT should help plan or review this task.
2. What minimal context Codex is about to send.
3. Which steps require user confirmation.
4. How ChatGPT feedback returns to Codex for review and approval.

Recommended checks:

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py --dry-run --json
python .agents/skills/codex-chatgpt-bridge/scripts/first_run.py
python scripts/build_chatgpt_collaboration_session.py --dry-run
```

Codex creates a real Bridge task only after confirmation. Generating a message does not open ChatGPT, send context, or execute suggestions.

### Guided UI Example

<table>
  <tr>
    <td width="33%" valign="top">
      <img src="assets/screenshots/chatgpt-app-connect.jpeg" alt="ChatGPT app connection confirmation" width="100%">
      <br>
      <sub>1. Confirm the ChatGPT app connection. Codex explains the purpose and safety boundary before sending any project context.</sub>
    </td>
    <td width="33%" valign="top">
      <img src="assets/screenshots/chatgpt-app-settings.jpeg" alt="ChatGPT app settings" width="100%">
      <br>
      <sub>2. Review the app permissions in ChatGPT settings. The Bridge exposes controlled tools and does not let ChatGPT edit source files or run commands.</sub>
    </td>
    <td width="33%" valign="top">
      <img src="assets/screenshots/codex-confirmation-guide.jpeg" alt="Codex confirmation guide" width="100%">
      <br>
      <sub>3. For account authorization, app creation, context sharing, or other sensitive actions, Codex stops and asks for confirmation.</sub>
    </td>
  </tr>
</table>

## MCP Connector Capability

The Bridge prefers official MCP tools, but it never assumes a ChatGPT account can call them.

- If read/write tools actually work, use Full Connector.
- If only read tools work, read the task packet and return structured JSON.
- If tools are unavailable, use controlled ChatGPT messages and structured import.

In all cases, ChatGPT is an untrusted collaborator. Codex reviews the result, and the user approves execution.

## Privacy And Security

Defaults:

- Do not read secrets, `.env`, private keys, cookies, or `.git`.
- Do not send Bridge tokens, full Connector URLs, account data, or login state.
- Right-side ChatGPT cannot edit source files or execute shell commands.
- Packet and task context go through secret scanning and size limits.
- ChatGPT feedback is untrusted.
- `suggested_actions` are never executed without user confirmation.

## Repository Layout

```text
.
├── .agents/skills/codex-chatgpt-bridge/   # Codex Skill entry, scripts, prompts
├── bridge/                                # Local Bridge, MCP protocol, security, state
├── scripts/                               # Public collaboration and result intake tools
├── examples/                              # Runnable examples
├── tests/                                 # Public core tests
├── docs/                                  # Usage, security, troubleshooting docs
├── assets/screenshots/                    # README images
├── README.md                              # Chinese README
├── README.en.md                           # English README
├── SECURITY.md                            # Security policy
└── LICENSE                                # Apache-2.0
```

## Local Verification

```bash
python -m compileall -q bridge .agents/skills/codex-chatgpt-bridge/scripts scripts examples tests
python -m unittest \
  tests.test_bridge_health \
  tests.test_task_flow \
  tests.test_tool_schemas \
  tests.test_mcp_protocol \
  tests.test_http_auth \
  tests.test_secret_scan \
  tests.test_redaction \
  tests.test_path_safety \
  tests.test_review_result \
  tests.test_intake_chatgpt_result \
  tests.test_push_task_confirmation \
  tests.test_fallback_and_capability \
  tests.test_chatgpt_collaboration_message
python -m unittest discover -s examples/mini-calculator -p 'test_*.py'
```

## Release Status

Current version: `v0.5.0`.

This release is a local collaboration kernel and open-source preview. Local Bridge, controlled context, task brief generation, review import, security boundaries, and fallback flow are available. Real ChatGPT Connector read/write capability still depends on the user account, selected model, and official tool calls. Without real tool calls and audit records, Full Connector should not be claimed as verified.

## Author

BLCaptain / dososo

GitHub: [https://github.com/dososo](https://github.com/dososo)

## License

Apache-2.0
