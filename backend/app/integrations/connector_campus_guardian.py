"""
ISA Campus Guardian connector.

All endpoints verified against the actual repository source code in Phase 0.
Auth: X-API-Key header on REST; ?key= query param on WebSocket.
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field

from app.core.connector_base import (
    BaseHTTPConnector,
    ToolDefinition,
    ConnectorResult,
    ConnectorStatus,
)
from app.core.config import get_settings


# ── Settings for this connector ──────────────────────────────────────────────────

class CGSettings:
    def __init__(self):
        s = get_settings()
        self.base_url = s.cg_api_base_url.rstrip("/")
        self.api_key = s.cg_api_key

    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Accept": "application/json"}


# ── Request/Response models (mirror upstream Pydantic models where useful) ───────

class CGHealthResponse(BaseModel):
    status: str
    sources_total: int
    sources_online: int
    sources_errored: list[str]
    sources_stalled: list[str]
    ws_connected_clients: int
    sources: list[dict]


class CGIncidentListItem(BaseModel):
    incident_id: str
    source_id: str
    location: str
    started_at: str | None
    resolved_at: str | None
    state: str
    people_involved: list
    peak_movement: float
    min_distance: float | None
    description: str
    has_snapshot: bool
    telegram_status: str
    zone: str | None
    group_id: str | None
    is_additional_angle: bool
    reviewed_at: str | None
    escalated_at: str | None


class CGIncidentDetail(BaseModel):
    incident_id: str
    source_id: str
    location: str
    started_at: str | None
    resolved_at: str | None
    state: str
    people_involved: list
    peak_movement: float
    min_distance: float | None
    description: str
    has_snapshot: bool
    telegram_status: str
    zone: str | None
    group_id: str | None
    is_additional_angle: bool
    reviewed_at: str | None
    escalated_at: str | None
    angles: list[dict]
    timeline: list[dict]


# ── Connector implementation ─────────────────────────────────────────────────────

class CampusGuardianConnector(BaseHTTPConnector):
    """
    Connector for Campus Guardian (FastAPI backend, port 8000).

    Tools:
    - cg_health             READ         Get health + source liveness
    - cg_list_sources       READ         List all camera/source statuses
    - cg_get_source         READ         Single source detail
    - cg_list_incidents     READ         Paginated incident list
    - cg_get_incident       READ         Full incident with angles + timeline
    - cg_review_incident    CONTROLLED   Mark incident reviewed (stops escalation)
    - cg_get_snapshot       READ         Get incident snapshot JPEG
    - cg_get_clip           READ         Get evidence clip MP4
    - cg_add_source         CONTROLLED   Register a new camera/source
    - cg_remove_source      RESTRICTED   Remove a camera/source
    """

    project_id = "campus-guardian"
    project_name = "Campus Guardian"
    version = "2.0.0"

    def __init__(self):
        super().__init__()
        cg = CGSettings()
        self.base_url = cg.base_url
        self.default_headers = cg.headers()

    # ── Tools ───────────────────────────────────────────────────────────────────

    def capabilities(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="cg_health",
                project_id=self.project_id,
                description="Get Campus Guardian health status and source liveness. Returns overall status (ok/degraded/down), counts of online/errored/stalled sources, and per-source status details.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["ok", "degraded", "down", "starting"]},
                        "sources_total": {"type": "integer"},
                        "sources_online": {"type": "integer"},
                        "sources_errored": {"type": "array", "items": {"type": "string"}},
                        "sources_stalled": {"type": "array", "items": {"type": "string"}},
                        "sources": {"type": "array"},
                    },
                },
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="cg_list_sources",
                project_id=self.project_id,
                description="List all registered camera/video sources with their live status (online/offline/error/starting), person count, movement metrics, and active incident ID.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={
                    "type": "object",
                    "properties": {
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source_id": {"type": "string"},
                                    "source_type": {"type": "string"},
                                    "location": {"type": "string"},
                                    "zone": {"type": "string"},
                                    "status": {"type": "string"},
                                    "person_count": {"type": "integer"},
                                    "max_movement": {"type": "number"},
                                    "closest_distance": {"type": "number"},
                                    "activity_status": {"type": "string"},
                                    "active_incident_id": {"type": "string"},
                                },
                            },
                        },
                    },
                },
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="cg_get_source",
                project_id=self.project_id,
                description="Get detailed status for a single camera/source by its source_id.",
                input_schema={
                    "type": "object",
                    "properties": {"source_id": {"type": "string", "minLength": 1}},
                    "required": ["source_id"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="cg_list_incidents",
                project_id=self.project_id,
                description="List recent incidents with pagination, filtering by source_id and/or state (e.g. ALERT_SENT, INCIDENT_RESOLVED). Returns total count, active incident count, and full metadata for each incident.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                        "offset": {"type": "integer", "minimum": 0},
                        "source_id": {"type": "string"},
                        "state": {"type": "string", "enum": ["ALERT_SENT", "INCIDENT_RESOLVED", "REVIEWED"]},
                    },
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "total": {"type": "integer"},
                        "active_incidents": {"type": "integer"},
                        "limit": {"type": "integer"},
                        "offset": {"type": "integer"},
                        "items": {"type": "array"},
                    },
                },
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="cg_get_incident",
                project_id=self.project_id,
                description="Get full details for one incident: status, timeline, and all correlated camera angles (multi-camera incidents). Safe for IASA to display — includes evidence references but not the actual images.",
                input_schema={
                    "type": "object",
                    "properties": {"incident_id": {"type": "string", "minLength": 1}},
                    "required": ["incident_id"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="cg_review_incident",
                project_id=self.project_id,
                description="Mark an incident as reviewed by an operator. This stops the escalation timer and also reviews correlated camera angles of the same event. Requires confirmation before execution.",
                input_schema={
                    "type": "object",
                    "properties": {"incident_id": {"type": "string", "minLength": 1}},
                    "required": ["incident_id"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "incident_id": {"type": "string"},
                        "reviewed_at": {"type": "string"},
                    },
                },
                permission="CONTROLLED",
                requires_confirmation=True,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="cg_get_snapshot",
                project_id=self.project_id,
                description="Retrieve the confirmed snapshot JPEG for an incident. The IASA UI must protect sensitive imagery — only display when explicitly requested by an authorized user.",
                input_schema={
                    "type": "object",
                    "properties": {"incident_id": {"type": "string", "minLength": 1}},
                    "required": ["incident_id"],
                    "additionalProperties": False,
                },
                output_schema={"type": "string", "description": "Base64-encoded JPEG image data"},
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=30.0,
            ),
            ToolDefinition(
                name="cg_get_clip",
                project_id=self.project_id,
                description="Retrieve the annotated evidence clip (pre + post event) for an incident as an MP4. The clip may not be ready immediately — it becomes available after the post-event recording window (~10 seconds).",
                input_schema={
                    "type": "object",
                    "properties": {"incident_id": {"type": "string", "minLength": 1}},
                    "required": ["incident_id"],
                    "additionalProperties": False,
                },
                output_schema={"type": "string", "description": "Base64-encoded MP4 video data"},
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=60.0,
            ),
            ToolDefinition(
                name="cg_add_source",
                project_id=self.project_id,
                description="Register a new video source at runtime (webcam, RTSP camera, uploaded video, or phone camera). Changes the operational configuration of Campus Guardian — requires confirmation.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string", "minLength": 1, "maxLength": 64},
                        "source_type": {
                            "type": "string",
                            "enum": ["WEBCAM", "UPLOADED_VIDEO", "RTSP", "RUNTIME_STREAM", "CCTV"],
                        },
                        "location": {"type": "string", "minLength": 1, "maxLength": 128},
                        "uri": {"type": "string", "minLength": 1},
                        "enabled": {"type": "boolean", "default": True},
                        "zone": {"type": "string", "maxLength": 64, "default": ""},
                    },
                    "required": ["source_id", "source_type", "location", "uri"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "source_id": {"type": "string"},
                    },
                },
                permission="CONTROLLED",
                requires_confirmation=True,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="cg_remove_source",
                project_id=self.project_id,
                description="Remove a registered camera/source from Campus Guardian. This is a destructive operational action — requires confirmation and is classified as RESTRICTED.",
                input_schema={
                    "type": "object",
                    "properties": {"source_id": {"type": "string", "minLength": 1}},
                    "required": ["source_id"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "source_id": {"type": "string"},
                    },
                },
                permission="RESTRICTED",
                requires_confirmation=True,
                timeout_seconds=15.0,
            ),
        ]

    # ── Health ──────────────────────────────────────────────────────────────────

    async def health(self) -> ConnectorResult:
        """GET /api/health — no auth required, safe to poll."""
        result = await self._http_get("/api/health", timeout_seconds=15.0)
        # /api/health returns 200 with status payload even when sources are down
        if result.status == ConnectorStatus.HEALTHY:
            data = result.data or {}
            overall = data.get("status", "unknown")
            if overall == "down":
                result.status = ConnectorStatus.DEGRADED
                result.error = "All sources are down"
            elif overall == "degraded":
                result.status = ConnectorStatus.DEGRADED
        return result

    # ── Execute (tool dispatch) ──────────────────────────────────────────────────

    async def execute(
        self,
        tool_name: str,
        arguments: dict,
        timeout_seconds: float = 30.0,
    ) -> ConnectorResult:
        # Validate tool exists
        tool = next((t for t in self.capabilities() if t.name == tool_name), None)
        if tool is None:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Tool not found: {tool_name}",
            )

        # Route to the correct endpoint
        path_map = {
            "cg_health": "/api/health",
            "cg_list_sources": "/api/sources",
            "cg_get_source": "/api/sources/{source_id}",
            "cg_list_incidents": "/api/incidents",
            "cg_get_incident": "/api/incidents/{incident_id}",
            "cg_review_incident": "/api/incidents/{incident_id}/review",
            "cg_add_source": "/api/sources",
            "cg_remove_source": "/api/sources/{source_id}",
            "cg_get_snapshot": "/api/incidents/{incident_id}/snapshot",
            "cg_get_clip": "/api/incidents/{incident_id}/clip",
        }

        path_template = path_map.get(tool_name)
        if path_template is None:
            return ConnectorResult.unavailable(
                self.project_id,
                f"No endpoint mapping for tool: {tool_name}",
            )

        path = path_template.format(**arguments)

        if tool_name in ("cg_add_source",):
            return await self._http_post(
                path,
                json_body=arguments,
                timeout_seconds=tool.timeout_seconds,
            )

        if tool_name in ("cg_get_snapshot", "cg_get_clip"):
            # These return binary; our HTTP client returns JSON by default.
            # For now, mark as healthy with a note that the IASA API layer
            # should proxy the binary response.
            result = await self._http_get(path, timeout_seconds=tool.timeout_seconds)
            if result.status == ConnectorStatus.HEALTHY:
                result.data = {"_binary_endpoint": path, "incident_id": arguments.get("incident_id")}
            return result

        return await self._http_get(path, timeout_seconds=tool.timeout_seconds)


# ── Factory function for the registry ────────────────────────────────────────────

def create_cg_connector() -> CampusGuardianConnector:
    return CampusGuardianConnector()
