"""
ISA tool discovery endpoint.

Returns the list of tools available to the caller.
In a full implementation, this would filter by user identity and workspace.
For now, returns all registered tools.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.registry.connector_registry import registry

router = APIRouter(tags=["tools"])


@router.get("/api/tools")
async def list_tools():
    """
    Return all registered tool definitions.

    Each tool includes:
    - name (fully-qualified, e.g. "cg_health")
    - project_id
    - description
    - input_schema (JSON Schema)
    - permission level
    - whether confirmation is required
    - timeout
    """
    tools = []
    for conn in registry.list():
        for tool in conn.capabilities():
            tools.append({
                "name": tool.name,
                "project_id": tool.project_id,
                "project_name": conn.project_name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
                "permission": tool.permission,
                "requires_confirmation": tool.requires_confirmation,
                "timeout_seconds": tool.timeout_seconds,
                "enabled": tool.enabled,
            })
    return {
        "tools": tools,
        "count": len(tools),
    }
