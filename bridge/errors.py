from __future__ import annotations


class BridgeError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message}


def require_role(role: str, allowed: set[str]) -> None:
    if role not in allowed:
        raise BridgeError("permission_denied", f"tool not available for role {role}", 403)
