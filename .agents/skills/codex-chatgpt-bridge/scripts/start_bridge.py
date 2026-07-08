#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys

from _bootstrap import ROOT
from bridge.server import serve
from bridge.state import BridgeState


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--foreground", action="store_true")
    parser.add_argument("--restart-tunnel", action="store_true", help="保留参数；真实 tunnel 需人工配置")
    args = parser.parse_args()
    state = BridgeState(ROOT)
    config = state.init_state()
    port = int(config.get("port", 8765))

    if args.foreground:
        serve(ROOT, port=port)
        return 0

    log_path = state.bridge_dir / "logs" / "bridge-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, __file__, "--foreground"],
        stdout=handle,
        stderr=handle,
        cwd=str(ROOT),
        start_new_session=True,
    )
    state.write_pid(proc.pid)
    print(f"Bridge started on http://127.0.0.1:{port}/mcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
