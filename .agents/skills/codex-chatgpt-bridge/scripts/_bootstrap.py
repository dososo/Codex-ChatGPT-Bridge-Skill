from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "bridge").is_dir() and (parent / "pyproject.toml").is_file():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return parent
    raise SystemExit("cannot locate repository root")


ROOT = repo_root()
