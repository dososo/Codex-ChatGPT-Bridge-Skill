from __future__ import annotations

from . import CONNECTOR_TOOL_SCHEMA_VERSION, SCHEMA_VERSION


def connector_schema_status(config: dict[str, object]) -> dict[str, object]:
    connector_version = config.get("connector_tool_schema_version")
    if not isinstance(connector_version, str) or not connector_version.strip():
        return {
            "bridge_schema_version": SCHEMA_VERSION,
            "bridge_connector_tool_schema_version": CONNECTOR_TOOL_SCHEMA_VERSION,
            "connector_tool_schema_version": None,
            "status": "unknown",
            "refresh_required": True,
            "message": "Connector 工具快照版本未知；请在 ChatGPT Connector 中 Refresh/Scan Tools 后重跑 smoke test。",
        }

    if connector_version == CONNECTOR_TOOL_SCHEMA_VERSION:
        return {
            "bridge_schema_version": SCHEMA_VERSION,
            "bridge_connector_tool_schema_version": CONNECTOR_TOOL_SCHEMA_VERSION,
            "connector_tool_schema_version": connector_version,
            "status": "in_sync",
            "refresh_required": False,
            "message": "Connector 工具快照与当前 Bridge schema 一致。",
        }

    return {
        "bridge_schema_version": SCHEMA_VERSION,
        "bridge_connector_tool_schema_version": CONNECTOR_TOOL_SCHEMA_VERSION,
        "connector_tool_schema_version": connector_version,
        "status": "refresh_required",
        "refresh_required": True,
        "message": "Connector 工具快照版本与当前 Bridge schema 不一致；请在 ChatGPT Connector 中 Refresh/Scan Tools 后重跑 read/write smoke test。",
    }
