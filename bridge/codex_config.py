from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path


SERVER_NAME = "codex_chatgpt_bridge"
TOKEN_ENV_VAR = "CODEX_BRIDGE_LOCAL_TOKEN"
ACTIVE_CONFIG_REL = Path(".codex") / "config.toml"
SNIPPET_REL = Path(".codex") / "codex-chatgpt-bridge.config.toml"
USER_ACTIVE_CONFIG_REL = Path(".codex") / "config.toml"
ENABLED_TOOLS = [
    "bridge_health",
    "bridge_push_task",
    "bridge_pull_result",
    "bridge_list_my_artifacts",
    "bridge_cancel_task",
]


def render_codex_mcp_snippet(port: int, repo_root: Path | str | None = None, python_executable: str | None = None) -> str:
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    script = root / "scripts" / "codex_bridge_stdio_mcp.py"
    python = python_executable or sys.executable or "python3"
    tools = ",\n".join(f'  "{tool}"' for tool in ENABLED_TOOLS)
    return f"""[mcp_servers.{SERVER_NAME}]
command = "{_toml_string(python)}"
args = [
  "{_toml_string(str(script))}",
  "--repo-root",
  "{_toml_string(str(root))}"
]
enabled = true
default_tools_approval_mode = "prompt"
enabled_tools = [
{tools}
]
tool_timeout_sec = 45
startup_timeout_sec = 10
"""


def write_codex_mcp_snippet(repo_root: Path | str, port: int) -> Path:
    root = Path(repo_root)
    path = root / SNIPPET_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_codex_mcp_snippet(port, root), encoding="utf-8")
    return path


def user_codex_config_path(home: Path | str | None = None) -> Path:
    root = Path(home).expanduser() if home is not None else Path.home()
    return root / USER_ACTIVE_CONFIG_REL


def install_codex_mcp_active_config(
    repo_root: Path | str,
    port: int,
    *,
    active_config_path: Path | str | None = None,
    write: bool = False,
    python_executable: str | None = None,
) -> dict[str, object]:
    root = Path(repo_root).resolve()
    target = Path(active_config_path).expanduser() if active_config_path is not None else user_codex_config_path()
    snippet = render_codex_mcp_snippet(port, root, python_executable=python_executable)
    original = target.read_text(encoding="utf-8") if target.exists() else ""
    section = _server_section_text(original)
    token_in_bridge_section = _contains_token_in_url(section)
    already_ok = bool(section and _contains_stdio_config(section, root))

    if token_in_bridge_section:
        return {
            "ok": False,
            "target_path": str(target),
            "write": write,
            "action": "blocked",
            "changed": False,
            "backup_path": None,
            "required_user_confirmation": True,
            "active_config_exists": target.exists(),
            "active_has_bridge_server": bool(section),
            "active_uses_stdio_command": already_ok,
            "active_token_in_url_detected": True,
            "summary": "检测到现有 Bridge MCP 配置 URL 里可能包含 token，未自动修改；需要用户确认后清理。",
        }

    if already_ok:
        return {
            "ok": True,
            "target_path": str(target),
            "write": write,
            "action": "noop",
            "changed": False,
            "backup_path": None,
            "required_user_confirmation": False,
            "active_config_exists": target.exists(),
            "active_has_bridge_server": True,
            "active_uses_stdio_command": True,
            "active_token_in_url_detected": False,
            "summary": "活跃 Codex MCP 配置已使用 stdio Bridge server。",
        }

    action = "replace" if section else "append"
    updated = _replace_or_append_server_section(original, snippet)
    backup_path: Path | None = None
    if write:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup_path = _backup_path(target)
            backup_path.write_text(original, encoding="utf-8")
        target.write_text(updated, encoding="utf-8")

    return {
        "ok": True,
        "target_path": str(target),
        "write": write,
        "action": action,
        "changed": True,
        "backup_path": str(backup_path) if backup_path else None,
        "required_user_confirmation": False,
        "active_config_exists": target.exists() or write,
        "active_has_bridge_server": True,
        "active_uses_stdio_command": True,
        "active_token_in_url_detected": False,
        "summary": (
            "已更新活跃 Codex MCP 配置为 stdio Bridge server。"
            if write
            else "可安全更新活跃 Codex MCP 配置为 stdio Bridge server。"
        ),
    }


def inspect_codex_mcp_config(repo_root: Path | str, port: int) -> dict[str, object]:
    root = Path(repo_root)
    active_path = root / ACTIVE_CONFIG_REL
    snippet_path = root / SNIPPET_REL
    active_text = active_path.read_text(encoding="utf-8") if active_path.exists() else ""
    snippet_text = snippet_path.read_text(encoding="utf-8") if snippet_path.exists() else ""

    active_has_server = f"[mcp_servers.{SERVER_NAME}]" in active_text
    active_uses_stdio = active_has_server and _contains_stdio_config(active_text, root)
    active_uses_bearer = TOKEN_ENV_VAR in active_text and "bearer_token_env_var" in active_text
    active_url_ok = f'url = "http://127.0.0.1:{port}/mcp"' in active_text
    active_token_in_url = _contains_token_in_url(active_text)

    snippet_valid = (
        f"[mcp_servers.{SERVER_NAME}]" in snippet_text
        and _contains_stdio_config(snippet_text, root)
        and not _contains_token_in_url(snippet_text)
    )

    required_actions: list[str] = []
    if active_token_in_url:
        required_actions.append("remove_token_from_codex_mcp_url")
    if not snippet_valid:
        required_actions.append("generate_codex_mcp_config_snippet")
    if not active_has_server:
        required_actions.append("review_and_copy_codex_mcp_config_snippet")
    elif not active_uses_stdio:
        required_actions.append("switch_codex_mcp_config_to_stdio")

    return {
        "active_config_path": str(ACTIVE_CONFIG_REL),
        "active_config_exists": active_path.exists(),
        "active_has_bridge_server": active_has_server,
        "active_uses_stdio_command": active_uses_stdio,
        "active_uses_bearer_token_env_var": active_uses_bearer,
        "active_url_matches_bridge_port": active_url_ok,
        "active_token_in_url_detected": active_token_in_url,
        "snippet_path": str(SNIPPET_REL),
        "snippet_exists": snippet_path.exists(),
        "snippet_valid": snippet_valid,
        "required_actions": required_actions,
        "message": (
            "Codex 本地 MCP 配置使用 stdio command，由 Codex 启动本地 server；"
            "HTTP /mcp 继续保留给 ChatGPT Connector 或外部 MCP 客户端。"
        ),
    }


def _contains_token_in_url(text: str) -> bool:
    if not text:
        return False
    token_url_patterns = [
        re.compile(r"https?://[^\"]*/mcp/remote/[A-Za-z0-9_\-]{16,}"),
        re.compile(r"https?://[^\"]*[?&](token|bearer|api_key)=[A-Za-z0-9._\-]{12,}", re.IGNORECASE),
    ]
    return any(pattern.search(text) for pattern in token_url_patterns)


def _contains_stdio_config(text: str, repo_root: Path) -> bool:
    script = repo_root.resolve() / "scripts" / "codex_bridge_stdio_mcp.py"
    return (
        f"[mcp_servers.{SERVER_NAME}]" in text
        and "command =" in text
        and "args =" in text
        and str(script) in text
        and "--repo-root" in text
        and str(repo_root.resolve()) in text
    )


def _server_section_match(text: str) -> re.Match[str] | None:
    return re.search(rf"(?m)^\[mcp_servers\.{re.escape(SERVER_NAME)}\]\s*$", text)


def _server_section_text(text: str) -> str:
    match = _server_section_match(text)
    if not match:
        return ""
    next_section = re.search(r"(?m)^\[[^\n]+\]\s*$", text[match.end():])
    end = match.end() + next_section.start() if next_section else len(text)
    return text[match.start():end]


def _replace_or_append_server_section(text: str, snippet: str) -> str:
    snippet = snippet.strip() + "\n"
    match = _server_section_match(text)
    if not match:
        prefix = text.rstrip()
        return f"{prefix}\n\n{snippet}" if prefix else snippet
    next_section = re.search(r"(?m)^\[[^\n]+\]\s*$", text[match.end():])
    end = match.end() + next_section.start() if next_section else len(text)
    before = text[:match.start()].rstrip()
    after = text[end:].lstrip("\n")
    parts = []
    if before:
        parts.append(before)
    parts.append(snippet.rstrip())
    if after:
        parts.append(after.rstrip())
    return "\n\n".join(parts) + "\n"


def _backup_path(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.bak-codex-chatgpt-bridge-{timestamp}")
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-codex-chatgpt-bridge-{timestamp}-{suffix}")
        suffix += 1
    return candidate


def _toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
