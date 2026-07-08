from __future__ import annotations

import re


REDACTION = "[REDACTED]"


TOKENISH_PATTERNS = [
    re.compile(r"https://[A-Za-z0-9.-]+/mcp/remote/[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"npm_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"(?i)(AccountKey=)[A-Za-z0-9+/=]{20,}"),
    re.compile(r"(?i)(sig=)[A-Za-z0-9%+/=]{20,}"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._\-]{12,}"),
    re.compile(r"(?i)((api[_-]?key|secret|token|password)\s*[:=]\s*)[\"']?[^\"'\s]{8,}"),
    re.compile(r"/mcp/remote/[A-Za-z0-9_\-]{16,}"),
]


def mask_secret(value: str, keep: int = 6) -> str:
    if not value:
        return REDACTION
    suffix = value[-keep:] if len(value) > keep else value
    return f"{REDACTION}...{suffix}"


def redact_text(text: str, token_values: list[str] | None = None) -> str:
    redacted = text
    for token in token_values or []:
        if token:
            redacted = redacted.replace(token, mask_secret(token))
    for pattern in TOKENISH_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}{REDACTION}" if m.lastindex else REDACTION, redacted)
    return redacted


def hash_for_log(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
