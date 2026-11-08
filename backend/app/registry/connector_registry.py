"""
ISA connector registry.

Tracks which connectors are loaded and provides a single lookup point
for the orchestration layer.
"""
from __future__ import annotations

from typing import Any

from app.core.connector_base import BaseConnector, ConnectorResult, ToolDefinition


class ConnectorRegistry:
    """Singleton registry of all loaded project connectors."""

    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        if connector.project_id in self._connectors:
            raise ValueError(f"Connector already registered: {connector.project_id}")
        self._connectors[connector.project_id] = connector

    def get(self, project_id: str) -> BaseConnector | None:
        return self._connectors.get(project_id)

    def list(self) -> list[BaseConnector]:
        return list(self._connectors.values())

    def all_capabilities(self) -> list[ToolDefinition]:
        """Flatten all tool definitions from all registered connectors."""
        caps: list[ToolDefinition] = []
        for conn in self._connectors.values():
            for tool in conn.capabilities():
                if tool.enabled:
                    caps.append(tool)
        return caps

    def find_tool(self, tool_name: str) -> tuple[BaseConnector, ToolDefinition] | None:
        """Find a tool by its fully-qualified name across all connectors."""
        for conn in self._connectors.values():
            for tool in conn.capabilities():
                if tool.name == tool_name and tool.enabled:
                    return conn, tool
        return None

    async def health_all(self) -> dict[str, ConnectorResult]:
        """Run health checks on all connectors sequentially."""
        results: dict[str, ConnectorResult] = {}
        for conn in self._connectors.values():
            try:
                results[conn.project_id] = await conn.health()
            except Exception as e:
                results[conn.project_id] = ConnectorResult.unavailable(
                    conn.project_id,
                    f"Health check raised: {e}",
                )
        return results


# ── Module-level singleton ──────────────────────────────────────────────────────
# Created at app startup; injected into request handlers via dependency.
registry = ConnectorRegistry()
