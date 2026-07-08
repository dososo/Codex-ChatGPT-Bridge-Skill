#!/usr/bin/env python3
from __future__ import annotations

import os
import signal

from _bootstrap import ROOT
from bridge.state import BridgeState


def main() -> int:
    state = BridgeState(ROOT)
    pid = state.read_pid()
    if not pid:
        print("Bridge pid not found.")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Bridge stopped: {pid}")
    except ProcessLookupError:
        print(f"Bridge process not running: {pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
