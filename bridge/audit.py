from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .redaction import hash_for_log


def append_audit(
    bridge_dir: Path,
    *,
    tool: str,
    role: str,
    status: str,
    task_id: str | None = None,
    claim_id: str | None = None,
    error_code: str | None = None,
) -> None:
    log_dir = bridge_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "role": role,
        "status": status,
        "task_id": task_id,
        "claim_id_hash": hash_for_log(claim_id) if claim_id else None,
        "error_code": error_code,
    }
    with (log_dir / "audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def append_http_audit(
    bridge_dir: Path,
    *,
    endpoint: str,
    status: str,
    status_code: int,
    duration_ms: int,
    role: str | None = None,
    mcp_method: str | None = None,
    error_code: str | None = None,
    auth_failure_count: int | None = None,
) -> None:
    log_dir = bridge_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "http",
        "endpoint": endpoint,
        "role": role,
        "mcp_method": mcp_method,
        "status": status,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "error_code": error_code,
        "auth_failure_count": auth_failure_count,
    }
    with (log_dir / "audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def append_path_rejection_audit(
    bridge_dir: Path,
    *,
    tool: str,
    role: str,
    path_value: str,
    reason: str,
    task_id: str | None = None,
) -> None:
    log_dir = bridge_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "path_rejection",
        "tool": tool,
        "role": role,
        "status": "blocked",
        "task_id": task_id,
        "path_hash": hash_for_log(path_value),
        "error_code": reason,
    }
    with (log_dir / "audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
