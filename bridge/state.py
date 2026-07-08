from __future__ import annotations

import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from . import CONNECTOR_TOOL_SCHEMA_VERSION, DEFAULT_PORT, SCHEMA_VERSION, VERSION
from .capabilities import UNKNOWN
from .errors import BridgeError
from .lock import FileLock
from .redaction import hash_for_log


class BridgeState:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()
        self.bridge_dir = self.repo_root / ".ai-bridge"
        self.config_path = self.bridge_dir / "config.json"
        self.lock_path = self.bridge_dir / "state.lock"

    @contextmanager
    def locked(self) -> Iterator[None]:
        with FileLock(self.lock_path):
            yield

    @property
    def task_dir(self) -> Path:
        return self.bridge_dir / "tasks"

    @property
    def result_dir(self) -> Path:
        return self.bridge_dir / "results"

    @property
    def packet_dir(self) -> Path:
        return self.bridge_dir / "packets"

    @property
    def patch_dir(self) -> Path:
        return self.bridge_dir / "patches"

    @property
    def plan_dir(self) -> Path:
        return self.bridge_dir / "plans"

    def init_state(self, *, port: int = DEFAULT_PORT) -> dict[str, object]:
        with self.locked():
            for rel in ["tasks", "results", "packets", "patches", "plans", "logs", "tokens", "tmp"]:
                (self.bridge_dir / rel).mkdir(parents=True, exist_ok=True)

            if not (self.bridge_dir / "tokens" / "local.token").exists():
                self.write_token("local", secrets.token_urlsafe(32))
            if not (self.bridge_dir / "tokens" / "remote.token").exists():
                self.write_token("remote", secrets.token_urlsafe(32))

            config = self.load_config(default={})
            if not config:
                config = {
                    "bridge_version": VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "repo_root": str(self.repo_root),
                    "repo_display_name": self.repo_root.name,
                    "root_alias": "current_repo",
                    "port": port,
                    "host": "127.0.0.1",
                    "capability_mode": UNKNOWN,
                    "connector_tool_schema_version": CONNECTOR_TOOL_SCHEMA_VERSION,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "remote_token_expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                }
            else:
                existing_root = config.get("repo_root")
                if isinstance(existing_root, str) and Path(existing_root).resolve() != self.repo_root:
                    raise BridgeError("repo_root_mismatch", "existing Bridge config belongs to another repo root")
                config.setdefault("bridge_version", VERSION)
                config.setdefault("schema_version", SCHEMA_VERSION)
                config.setdefault("repo_root", str(self.repo_root))
                config.setdefault("repo_display_name", self.repo_root.name)
                config.setdefault("port", port)
                config.setdefault("host", "127.0.0.1")
                config.setdefault("capability_mode", UNKNOWN)
                config.setdefault("root_alias", "current_repo")
                config["updated_at"] = now_iso()
            config["last_recovery"] = self.recover_startup_artifacts()
            self.atomic_write_json(self.config_path, config)
            self.ensure_gitignore_entries()
            self.register_current_repo(config)
            return config

    def recover_startup_artifacts(self) -> dict[str, object]:
        recovery: dict[str, object] = {
            "ran_at": now_iso(),
            "orphan_tmp_count": 0,
            "orphan_tmp_files": [],
            "current_task_rebuilt": False,
            "current_result_rebuilt": False,
            "incomplete_result_pairs": [],
        }

        tmp_dir = self.bridge_dir / "tmp"
        orphan_tmp_files = []
        if tmp_dir.exists():
            for path in sorted(tmp_dir.glob("*.tmp")):
                if not path.is_file():
                    continue
                orphan_tmp_files.append(
                    {
                        "path_hash": hash_for_log(str(path.relative_to(self.bridge_dir))),
                        "size_bytes": path.stat().st_size,
                    }
                )
        recovery["orphan_tmp_count"] = len(orphan_tmp_files)
        recovery["orphan_tmp_files"] = orphan_tmp_files

        latest_task = self._latest_json_file(self.task_files())
        if latest_task is not None and self._current_task_needs_rebuild(latest_task):
            task = json.loads(latest_task.read_text(encoding="utf-8"))
            self.atomic_write_json(self.bridge_dir / "current-task.json", task)
            recovery["current_task_rebuilt"] = True

        result_pairs, incomplete_pairs = self._result_pairs()
        recovery["incomplete_result_pairs"] = incomplete_pairs
        if result_pairs:
            latest = max(result_pairs, key=lambda item: item["mtime_ns"])
            md_path = latest["md_path"]
            json_path = latest["json_path"]
            if isinstance(md_path, Path) and self._current_result_needs_rebuild(md_path):
                self.atomic_write_text(self.bridge_dir / "current-result.md", md_path.read_text(encoding="utf-8"))
                recovery["current_result_rebuilt"] = True
            if isinstance(json_path, Path):
                self.atomic_write_text(self.bridge_dir / "current-result.json", json_path.read_text(encoding="utf-8"))

        return recovery

    def register_current_repo(self, config: dict[str, object]) -> None:
        from .registry import default_registry_path, register_repo

        register_repo(default_registry_path(self.repo_root), config)

    def ensure_gitignore_entries(self) -> None:
        path = self.repo_root / ".gitignore"
        required = [
            ".ai-bridge/",
            ".ai-bridge/tokens/",
            ".ai-bridge/logs/",
            ".ai-bridge/tmp/",
            ".ai-bridge/*.secret",
            ".ai-bridge/*.token",
            ".codex/config.toml",
        ]
        existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        updated = list(existing)
        for entry in required:
            if entry not in updated:
                updated.append(entry)
        if updated != existing:
            path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    def load_config(self, *, default: dict[str, object] | None = None) -> dict[str, object]:
        if not self.config_path.exists():
            return dict(default or {})
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def save_config(self, config: dict[str, object]) -> None:
        config["updated_at"] = now_iso()
        self.atomic_write_json(self.config_path, config)

    def token_path(self, kind: str) -> Path:
        if kind not in {"local", "remote"}:
            raise ValueError("token kind must be local or remote")
        return self.bridge_dir / "tokens" / f"{kind}.token"

    def read_token(self, kind: str) -> str:
        return self.token_path(kind).read_text(encoding="utf-8").strip()

    def write_token(self, kind: str, value: str) -> None:
        path = self.token_path(kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.atomic_write_text(path, value + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def token_values(self) -> list[str]:
        values: list[str] = []
        for kind in ["local", "remote"]:
            path = self.token_path(kind)
            if path.exists():
                values.append(path.read_text(encoding="utf-8").strip())
        return values

    def atomic_write_json(self, path: Path, data: dict[str, object]) -> None:
        self.atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def atomic_write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.bridge_dir / "tmp" / f"{path.name}.{secrets.token_hex(6)}.tmp"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def task_path(self, task_id: str) -> Path:
        return self.task_dir / f"{task_id}.json"

    def result_json_path(self, task_id: str, version: int) -> Path:
        return self.result_dir / f"{task_id}.r{version}.json"

    def result_md_path(self, task_id: str, version: int) -> Path:
        return self.result_dir / f"{task_id}.r{version}.md"

    def load_task(self, task_id: str) -> dict[str, object]:
        return json.loads(self.task_path(task_id).read_text(encoding="utf-8"))

    def save_task(self, task: dict[str, object]) -> None:
        task_id = str(task["task_id"])
        self.atomic_write_json(self.task_path(task_id), task)
        self.atomic_write_json(self.bridge_dir / "current-task.json", task)

    def task_files(self) -> list[Path]:
        if not self.task_dir.exists():
            return []
        return sorted(self.task_dir.glob("task_*.json"))

    def _latest_json_file(self, paths: list[Path]) -> Path | None:
        valid_paths = []
        for path in paths:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            valid_paths.append(path)
        if not valid_paths:
            return None
        return max(valid_paths, key=lambda item: item.stat().st_mtime_ns)

    def _current_task_needs_rebuild(self, latest_task_path: Path) -> bool:
        current_path = self.bridge_dir / "current-task.json"
        if not current_path.exists():
            return True
        try:
            current = json.loads(current_path.read_text(encoding="utf-8"))
            latest = json.loads(latest_task_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        return current.get("task_id") != latest.get("task_id") or current.get("status") != latest.get("status")

    def _current_result_needs_rebuild(self, latest_result_path: Path) -> bool:
        current_path = self.bridge_dir / "current-result.md"
        if not current_path.exists():
            return True
        try:
            return current_path.read_text(encoding="utf-8") != latest_result_path.read_text(encoding="utf-8")
        except OSError:
            return True

    def _result_pairs(self) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        pairs: list[dict[str, object]] = []
        incomplete: list[dict[str, object]] = []
        if not self.result_dir.exists():
            return pairs, incomplete
        for json_path in sorted(self.result_dir.glob("task_*.r*.json")):
            md_path = json_path.with_suffix(".md")
            if not md_path.exists():
                incomplete.append(
                    {
                        "result_hash": hash_for_log(str(json_path.relative_to(self.bridge_dir))),
                        "missing": "markdown",
                    }
                )
                continue
            pairs.append(
                {
                    "json_path": json_path,
                    "md_path": md_path,
                    "mtime_ns": max(json_path.stat().st_mtime_ns, md_path.stat().st_mtime_ns),
                }
            )
        for md_path in sorted(self.result_dir.glob("task_*.r*.md")):
            json_path = md_path.with_suffix(".json")
            if not json_path.exists():
                incomplete.append(
                    {
                        "result_hash": hash_for_log(str(md_path.relative_to(self.bridge_dir))),
                        "missing": "json",
                    }
                )
        return pairs, incomplete

    def result_versions(self, task_id: str) -> list[int]:
        versions: list[int] = []
        for path in self.result_dir.glob(f"{task_id}.r*.json"):
            stem = path.stem
            marker = stem.rsplit(".r", 1)[-1]
            if marker.isdigit():
                versions.append(int(marker))
        return sorted(versions)

    def write_pid(self, pid: int) -> None:
        self.atomic_write_text(self.bridge_dir / "bridge.pid", f"{pid}\n")

    def read_pid(self) -> int | None:
        path = self.bridge_dir / "bridge.pid"
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8").strip()
        return int(raw) if raw.isdigit() else None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_task_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"task_{stamp}_{secrets.token_hex(3)}"


def make_claim_id() -> str:
    return f"claim_{secrets.token_urlsafe(12)}"
