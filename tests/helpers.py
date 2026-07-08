from __future__ import annotations

import uuid
from pathlib import Path


def make_repo(name: str) -> Path:
    root = Path.cwd() / ".ai-bridge-test-runs" / f"{name}-{uuid.uuid4().hex}"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "tests" / "test_app.py").write_text("from src.app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    return root
