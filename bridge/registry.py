from __future__ import annotations

import json
from pathlib import Path

from .state import now_iso


def default_registry_path(repo_root: Path) -> Path:
    return repo_root / ".ai-bridge" / "registry.json"


def load_registry(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": "1.1", "repos": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"schema_version": "1.1", "repos": []}
    if not isinstance(payload.get("repos"), list):
        payload["repos"] = []
    payload.setdefault("schema_version", "1.1")
    return payload


def save_registry(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def register_repo(registry_path: Path, config: dict[str, object]) -> None:
    payload = load_registry(registry_path)
    repos = payload["repos"]
    assert isinstance(repos, list)
    repo_root = config.get("repo_root")
    if not isinstance(repo_root, str):
        return
    entry = {
        "repo_root": repo_root,
        "repo_display_name": config.get("repo_display_name", Path(repo_root).name),
        "root_alias": config.get("root_alias", "current_repo"),
        "host": config.get("host", "127.0.0.1"),
        "port": config.get("port", 8765),
        "config_path": str(Path(repo_root) / ".ai-bridge" / "config.json"),
        "updated_at": now_iso(),
    }
    for index, existing in enumerate(repos):
        if isinstance(existing, dict) and existing.get("repo_root") == repo_root:
            repos[index] = entry
            break
    else:
        repos.append(entry)
    save_registry(registry_path, payload)


def registered_ports(registry_path: Path, *, exclude_repo_root: Path | None = None) -> set[int]:
    payload = load_registry(registry_path)
    repos = payload.get("repos", [])
    ports: set[int] = set()
    if not isinstance(repos, list):
        return ports
    exclude = str(exclude_repo_root.resolve()) if exclude_repo_root else None
    for entry in repos:
        if not isinstance(entry, dict):
            continue
        if exclude and entry.get("repo_root") == exclude:
            continue
        port = entry.get("port")
        if isinstance(port, int):
            ports.add(port)
    return ports
