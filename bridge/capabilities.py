from __future__ import annotations


UNKNOWN = "unknown"
FULL_CONNECTOR = "full_connector"
READ_ONLY_CONNECTOR = "read_only_connector"
PACKET_OR_MANUAL = "packet_or_manual"
REAL_READ_SMOKE_ID = "real_read_smoke"
REAL_WRITE_SMOKE_ID = "real_write_smoke"


def classify(read_ok: bool, write_ok: bool) -> str:
    if read_ok and write_ok:
        return FULL_CONNECTOR
    if read_ok:
        return READ_ONLY_CONNECTOR
    return PACKET_OR_MANUAL


def capability_evidence_status(config: dict[str, object]) -> dict[str, object]:
    mode = config.get("capability_mode", UNKNOWN)
    evidence = config.get("capability_evidence")
    real_verified = (
        isinstance(evidence, dict)
        and evidence.get("evidence_level") == "real_connector"
        and evidence.get("real_connector_verified") is True
    )
    if mode in {FULL_CONNECTOR, READ_ONLY_CONNECTOR} and not real_verified:
        return {
            "status": "unverified",
            "real_connector_verified": False,
            "message": "当前 capability_mode 没有真实 ChatGPT Connector smoke 证据支撑；请运行真实 read/write smoke 并用 evidence 文件记录。",
        }
    if mode == UNKNOWN:
        return {
            "status": "unknown",
            "real_connector_verified": False,
            "message": "尚未完成真实 ChatGPT Connector capability gate。",
        }
    return {
        "status": "verified" if real_verified else "fallback",
        "real_connector_verified": real_verified,
        "message": "capability_mode 已由真实 Connector 证据支撑。" if real_verified else "当前模式不需要真实 Connector 写回能力。",
    }


def real_smoke_status_from_evidence(payload: dict[str, object]) -> dict[str, object]:
    items = payload.get("items")
    if not isinstance(items, list):
        return {"read_verified": False, "write_verified": False, "errors": ["items must be a list"]}

    by_id: dict[str, dict[str, object]] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            by_id[str(item["id"])] = item

    errors: list[str] = []
    read_verified = _item_verified(by_id.get(REAL_READ_SMOKE_ID))
    write_verified = _item_verified(by_id.get(REAL_WRITE_SMOKE_ID))
    if REAL_READ_SMOKE_ID not in by_id:
        errors.append(f"missing {REAL_READ_SMOKE_ID}")
    if REAL_WRITE_SMOKE_ID not in by_id:
        errors.append(f"missing {REAL_WRITE_SMOKE_ID}")
    if write_verified:
        read_verified = True
    return {
        "read_verified": read_verified,
        "write_verified": write_verified,
        "capability_mode": classify(read_verified, write_verified),
        "errors": errors,
    }


def _item_verified(item: dict[str, object] | None) -> bool:
    if not item or item.get("status") != "verified":
        return False
    evidence = item.get("evidence")
    return isinstance(evidence, list) and bool(evidence)
