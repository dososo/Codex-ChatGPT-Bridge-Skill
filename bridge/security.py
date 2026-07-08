from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from .errors import BridgeError
from .limits import FILE_READ_LIMIT, SEARCH_BYTES_LIMIT, SEARCH_MATCH_LIMIT, truncate_text
from .redaction import hash_for_log
from .secret_scan import scan_text


DENY_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
    "*.ppk",
    ".ssh/**",
    ".gnupg/**",
    ".git/**",
    ".ai-bridge/tokens/**",
    ".ai-bridge/logs/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    "coverage/**",
    ".DS_Store",
    "*.sqlite",
    "*.db",
    "*credentials*",
    "*secret*",
    "*token*",
]

DANGEROUS_COMMAND_PATTERNS = [
    re.compile(r"(?i)\brm\s+-rf\b"),
    re.compile(r"(?i)\b(del|rd|rmdir)\s+/(s|q)\b"),
    re.compile(r"(?i)\bRemove-Item\b.*\b-Recurse\b"),
    re.compile(r"(?i)\bmkfs\b"),
    re.compile(r"(?i)\bdd\s+"),
    re.compile(r"(?i)\b(curl|wget)\b.*\|\s*(sh|bash)"),
    re.compile(r"(?i)\biwr\b.*\|\s*iex"),
    re.compile(r"(?i)\b(ssh|scp|nc|telnet)\b"),
    re.compile(r"(?i)\bgit\s+(push|remote)\b"),
    re.compile(r"(?i)\b(npm\s+publish|pip\s+upload)\b"),
    re.compile(r"[;&]|&&|\|\||`|\$\("),
    re.compile(r"(?i)\b(sudo|runas)\b"),
]


def _contains_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 for ch in value)


def _contains_windows_short_name(raw_path: str) -> bool:
    return any(re.search(r"~[0-9]+(?:\.|$)", part) for part in raw_path.split("/"))


def normalize_relative_path(path_value: str) -> str:
    if not isinstance(path_value, str) or not path_value.strip():
        raise BridgeError("invalid_path", "path must be a non-empty string")
    if "\x00" in path_value or _contains_control_chars(path_value):
        raise BridgeError("invalid_path", "path contains control characters")

    raw = path_value.replace("\\", "/")
    if raw.startswith("//") or raw.startswith("\\\\"):
        raise BridgeError("invalid_path", "UNC paths are not allowed")
    if re.match(r"^[A-Za-z]:", raw):
        raise BridgeError("invalid_path", "absolute Windows drive paths are not allowed")
    if os.path.isabs(raw):
        raise BridgeError("invalid_path", "absolute paths are not allowed")
    if _contains_windows_short_name(raw):
        raise BridgeError("invalid_path", "Windows 8.3 short paths are not allowed")

    normalized = os.path.normpath(raw).replace("\\", "/")
    if normalized == "." or normalized.startswith("../") or normalized == "..":
        raise BridgeError("path_escape", "path escapes repo root")
    return normalized


def _is_denylisted(rel_path: str) -> bool:
    rel_lower = rel_path.replace("\\", "/").lower()
    name_lower = Path(rel_lower).name
    for pattern in DENY_PATTERNS:
        pat = pattern.lower()
        if fnmatch.fnmatch(rel_lower, pat) or fnmatch.fnmatch(name_lower, pat):
            return True
    return False


def validate_repo_file(repo_root: Path, path_value: str) -> tuple[str, Path]:
    rel = normalize_relative_path(path_value)
    candidate = (repo_root / rel).resolve()
    root = repo_root.resolve()
    try:
        common = os.path.commonpath([str(root), str(candidate)])
    except ValueError as exc:
        raise BridgeError("path_escape", "path escapes repo root") from exc
    if common != str(root):
        raise BridgeError("path_escape", "path escapes repo root")

    resolved_rel = candidate.relative_to(root).as_posix()
    if _is_denylisted(rel) or _is_denylisted(resolved_rel):
        raise BridgeError("path_denied", "path is denied by bridge policy")
    return resolved_rel, candidate


def filter_allowed_files(repo_root: Path, files: object, max_count: int) -> tuple[list[str], list[dict[str, object]]]:
    if files is None:
        return [], []
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        raise BridgeError("invalid_schema", "allowed_files must be a string list")

    accepted: list[str] = []
    rejected: list[dict[str, object]] = []
    for item in files[:max_count]:
        try:
            rel, _ = validate_repo_file(repo_root, item)
        except BridgeError as exc:
            rejected.append({"path_redacted": True, "path_hash": hash_for_log(item), "reason": exc.code})
            continue
        if rel not in accepted:
            accepted.append(rel)

    if len(files) > max_count:
        rejected.append({"path_redacted": True, "path_hash": hash_for_log("<extra>"), "reason": "allowed_files_limit"})
    return accepted, rejected


def read_allowed_file(repo_root: Path, allowed_files: list[str], path_value: str, *, offset: int = 0, limit: int = FILE_READ_LIMIT, token_values: list[str] | None = None) -> dict[str, object]:
    rel, path = validate_repo_file(repo_root, path_value)
    if rel not in allowed_files:
        raise BridgeError("path_not_allowed_for_task", "file is not in current task allowed_files")
    if not path.is_file():
        raise BridgeError("file_not_found", "allowed file does not exist", 404)
    content = path.read_text(encoding="utf-8", errors="replace")
    scan = scan_text(content, token_values)
    if scan["blocked"]:
        raise BridgeError("secret_blocked", "file contains high-confidence secrets")

    safe = str(scan["redacted"])
    offset = max(offset, 0)
    limit = max(1, min(limit, FILE_READ_LIMIT))
    sliced = safe[offset : offset + limit]
    truncated = offset + limit < len(safe)
    return {"path": rel, "offset": offset, "content": sliced, "truncated": truncated}


def search_allowed_files(repo_root: Path, allowed_files: list[str], query: str, *, token_values: list[str] | None = None) -> dict[str, object]:
    if not query:
        raise BridgeError("invalid_query", "query must not be empty")
    matches: list[dict[str, object]] = []
    used_bytes = 0
    for rel in allowed_files:
        _, path = validate_repo_file(repo_root, rel)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        scan = scan_text(text, token_values)
        if scan["blocked"]:
            continue
        for line_no, line in enumerate(str(scan["redacted"]).splitlines(), start=1):
            if query.lower() not in line.lower():
                continue
            line_bytes = len(line.encode("utf-8"))
            if len(matches) >= SEARCH_MATCH_LIMIT or used_bytes + line_bytes > SEARCH_BYTES_LIMIT:
                return {"matches": matches, "truncated": True}
            matches.append({"path": rel, "line": line_no, "text": line})
            used_bytes += line_bytes
    return {"matches": matches, "truncated": False}


def is_dangerous_command(command: str) -> bool:
    return any(pattern.search(command) for pattern in DANGEROUS_COMMAND_PATTERNS)


def sanitize_text_field(value: str, limit: int, token_values: list[str]) -> tuple[str, bool, list[dict[str, object]]]:
    scan = scan_text(value, token_values)
    if scan["blocked"]:
        raise BridgeError("secret_blocked", "content contains high-confidence secrets")
    truncated = truncate_text(str(scan["redacted"]), limit)
    return truncated.text, truncated.truncated, list(scan["findings"])
