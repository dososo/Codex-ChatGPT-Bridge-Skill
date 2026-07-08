from __future__ import annotations

import re
from dataclasses import dataclass

from .redaction import redact_text


@dataclass(frozen=True)
class SecretFinding:
    type: str
    blocked: bool


PATTERNS: list[tuple[str, re.Pattern[str], bool]] = [
    ("pem_private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"), True),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), False),
    ("github_token", re.compile(r"(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,})"), False),
    ("npm_token", re.compile(r"npm_[A-Za-z0-9_]{20,}"), False),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}"), False),
    ("gcp_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{35}"), False),
    ("azure_storage_account_key", re.compile(r"(?i)AccountKey=[A-Za-z0-9+/=]{20,}"), False),
    ("azure_sas_signature", re.compile(r"(?i)(?:[?&]|^)sig=[A-Za-z0-9%+/=]{20,}"), False),
    ("connector_url", re.compile(r"https://[A-Za-z0-9.-]+/mcp/remote/[A-Za-z0-9_\-]{16,}"), False),
    ("connector_url_token", re.compile(r"/mcp/remote/[A-Za-z0-9_\-]{16,}"), False),
    ("oauth_refresh_token", re.compile(r"(?i)refresh[_-]?token\s*[:=]\s*[\"']?[^\"'\s]{12,}"), False),
]


def scan_text(text: str, token_values: list[str] | None = None) -> dict[str, object]:
    findings: list[SecretFinding] = []
    for token in token_values or []:
        if token and token in text:
            findings.append(SecretFinding("bridge_token_value", True))
    for name, pattern, blocked in PATTERNS:
        if pattern.search(text):
            findings.append(SecretFinding(name, blocked))

    return {
        "blocked": any(f.blocked for f in findings),
        "findings": [{"type": f.type, "blocked": f.blocked} for f in findings],
        "redacted": redact_text(text, token_values),
    }
