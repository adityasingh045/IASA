"""
ISA chat/orchestration endpoint.

This is the core entry point for the LLM orchestration loop:

1. Receive user message
2. Resolve user identity + workspace + permissions (stub for now)
3. Send message + available tool schemas to LLM
4. If LLM proposes tool calls → validate → check permissions → execute
5. If confirmation needed → return approval request (not auto-approve)
6. Aggregate results → generate grounded response

For Phase 1, this implements the tool execution path with a stub LLM call.
The full LLM integration comes in Phase 5.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.connector_base import ConnectorResult
from app.core.errors import (
    ToolNotFoundError,
    ToolArgumentError,
    PermissionDeniedError,
    ApprovalRequiredError,
)
from app.core.connector_base import ConnectorStatus
from app.registry.connector_registry import registry
from app.auth.permissions import require_permission, classify_action

router = APIRouter(tags=["chat"])


# ── Request/Response models ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    user_id: str | None = None         # resolved from auth token in production
    workspace_id: str | None = None    # resolved from auth token in production


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    user_id: str | None = None
    workspace_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    tools_called: list[dict] = []
    partial_results: list[dict] = []
    approval_required: bool = False
    approval_request: dict | None = None


class ToolExecutionResponse(BaseModel):
    tool_name: str
    status: str
    result: dict | None = None
    error: str | None = None


# ── Orchestration ────────────────────────────────────────────────────────────────

@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a user message.

    Phase 1 behaviour:
    - If the message looks like a tool invocation (mentions a known tool name),
      execute it directly and return the result.
    - Otherwise, return a helpful response noting what tools are available.
    - Never auto-execute CONTROLLED or RESTRICTED actions without approval.
    """
    user_id = request.user_id or "demo-user"
    workspace_id = request.workspace_id

    # Try to match the message to a known tool
    tool_name = _extract_tool_name(request.message)
    if tool_name:
        tool = registry.find_tool(tool_name)
        if tool is None:
            return ChatResponse(
                response=f"I don't have a tool called '{tool_name}'. Here are the available tools: ",
                tools_called=[],
            )

        conn, tool_def = tool

        # Confirmation check first — if action needs approval, request it
        # (the approval flow will verify the approver has sufficient role)
        if tool_def.requires_confirmation:
            return ChatResponse(
                response="",
                tools_called=[],
                approval_required=True,
                approval_request={
                    "tool_name": tool_name,
                    "action_description": tool_def.description,
                    "arguments": request.message,
                    "permission": tool_def.permission,
                    "project_id": tool_def.project_id,
                    "connector_project_id": conn.project_id,
                },
            )

        # Permission check for non-confirmation actions
        try:
            require_permission(
                user_role="member",  # stub — real impl resolves from token
                required_permission=tool_def.permission,
                tool_name=tool_name,
            )
        except PermissionDeniedError as e:
            return ChatResponse(
                response=f"Permission denied: {e.message}. You don't have access to that action.",
                tools_called=[],
            )

        # Execute
        result = await conn.execute(tool_name, {}, timeout_seconds=tool_def.timeout_seconds)
        return ChatResponse(
            response=_format_result(tool_name, result),
            tools_called=[{"tool_name": tool_name, "project_id": tool_def.project_id}],
            partial_results=[_serialize_result(result)],
        )

    # No tool match — list available tools as help
    available = []
    for conn in registry.list():
        for tool in conn.capabilities():
            if tool.enabled:
                available.append(f"{tool.name} ({conn.project_name}): {tool.description[:80]}...")

    help_text = (
        f"I can help with the following project tools:\n\n" +
        "\n".join(f"- {t}" for t in available) +
        "\n\nJust ask me to use one of them, e.g. 'check Campus Guardian health'."
    )
    return ChatResponse(response=help_text, tools_called=[])


@router.post("/api/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(request: ToolCallRequest) -> ToolExecutionResponse:
    """
    Direct tool execution endpoint (used by the frontend when a user confirms an action).

    Flow:
    1. Look up tool in registry
    2. Check permission
    3. Check confirmation requirement
    4. Execute
    5. Return result
    """
    tool = registry.find_tool(request.tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.tool_name}")

    conn, tool_def = tool

    # Confirmation requirement — this endpoint is called AFTER approval
    if tool_def.requires_confirmation:
        raise HTTPException(
            status_code=403,
            detail=f"This action ({request.tool_name}) requires confirmation. Use the approval flow.",
        )

    # Permission check for non-confirmation actions
    try:
        require_permission(
            user_role="member",
            required_permission=tool_def.permission,
            tool_name=request.tool_name,
        )
    except PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Permission denied for this action")

    result = await conn.execute(
        request.tool_name,
        request.arguments,
        timeout_seconds=tool_def.timeout_seconds,
    )

    if result.status == ConnectorStatus.UNAVAILABLE:
        raise HTTPException(status_code=502, detail=result.error or "Project unavailable")

    return ToolExecutionResponse(
        tool_name=request.tool_name,
        status=result.status.value,
        result=_serialize_result(result),
        error=result.error,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────────

# Keyword patterns for intent matching (Phase 1 stopgap; replaced by LLM in Phase 5).
# Format: (pattern_substring, tool_name). First match wins.
INTENT_PATTERNS: list[tuple[str, str]] = [
    # Campus Guardian — add/remove source (checked BEFORE generic "source")
    ("remove", "cg_remove_source"),
    ("delete source", "cg_remove_source"),
    ("add source", "cg_add_source"),
    ("register camera", "cg_add_source"),
    # Campus Guardian — health
    ("health", "cg_health"),
    # Campus Guardian — sources (generic)
    ("source", "cg_list_sources"),
    # Campus Guardian — incidents
    ("incident", "cg_list_incidents"),
    ("alert", "cg_list_incidents"),
    # Campus Guardian — review
    ("review", "cg_review_incident"),
    # F.R.I.D.A.Y — hub
    ("friday", "friday_health"),
    ("hub", "friday_health"),
    ("device", "friday_list_devices"),
    ("connected", "friday_list_devices"),
]


def _extract_tool_name(message: str) -> str | None:
    """
    Match a user message to a registered tool name.

    Uses keyword patterns as a Phase 1 stopgap. The LLM-based intent
    router (Phase 5) will replace this with proper NLU.
    """
    message_lower = message.lower()
    for pattern, tool_name in INTENT_PATTERNS:
        if pattern in message_lower:
            # Verify the tool is actually registered
            tool = registry.find_tool(tool_name)
            if tool is not None:
                return tool_name
    return None


def _format_result(tool_name: str, result: ConnectorResult) -> str:
    """Human-readable summary of a connector result."""
    if result.status.value == "unavailable":
        return f"⚠️ {tool_name}: {result.error or 'Project unavailable'}"
    if result.status.value == "degraded":
        return f"⚠️ {tool_name}: {result.error or 'Partial results'}"
    return f"✅ {tool_name}: completed successfully"


def _serialize_result(result: ConnectorResult) -> dict:
    """Serialize a ConnectorResult for JSON transport."""
    return {
        "project_id": result.project_id,
        "status": result.status.value,
        "checked_at": result.checked_at,
        "latency_ms": result.latency_ms,
        "data": result.data,
        "error": result.error,
    }
