from __future__ import annotations

from dataclasses import dataclass


DIFF_LIMIT = 60 * 1024
TEST_LOG_LIMIT = 20 * 1024
FILE_READ_LIMIT = 48 * 1024
TASK_JSON_LIMIT = 120 * 1024
RESULT_JSON_LIMIT = 80 * 1024
ALLOWED_FILES_LIMIT = 40
SEARCH_MATCH_LIMIT = 50
SEARCH_BYTES_LIMIT = 32 * 1024
CLAIM_TIMEOUT_SECONDS = 30 * 60
TASK_TTL_SECONDS = 24 * 60 * 60
MAX_CLAIM_RETRIES = 3


@dataclass(frozen=True)
class TruncatedText:
    text: str
    truncated: bool


def truncate_text(value: str, limit: int, marker: str = "\n...[truncated by bridge]...\n") -> TruncatedText:
    if len(value.encode("utf-8")) <= limit:
        return TruncatedText(value, False)

    marker_bytes = len(marker.encode("utf-8"))
    budget = max(limit - marker_bytes, 0)
    head_budget = budget // 2
    tail_budget = budget - head_budget

    encoded = value.encode("utf-8")
    head = encoded[:head_budget].decode("utf-8", errors="ignore")
    tail = encoded[-tail_budget:].decode("utf-8", errors="ignore") if tail_budget else ""
    return TruncatedText(f"{head}{marker}{tail}", True)
