"""
ISA connector base class.

Every project connector must implement this interface.
Connectors are independent — if one fails, the others continue working.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from app.core.errors import ConnectorError, ConnectorUnavailableError


class ConnectorStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class ConnectorResult:
    """Typed result from any connector call."""
    project_id: str
    status: ConnectorStatus
    checked_at: str  # ISO 8601
    latency_ms: int
    data: Any = None
    error: str | None = None
    raw_status_code: int | None = None

    @classmethod
    def healthy(cls, project_id: str, data: Any, latency_ms: int = 0) -> "ConnectorResult":
        return cls(
            project_id=project_id,
            status=ConnectorStatus.HEALTHY,
            checked_at=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
            latency_ms=latency_ms,
            data=data,
        )

    @classmethod
    def degraded(cls, project_id: str, data: Any, error: str, latency_ms: int = 0) -> "ConnectorResult":
        return cls(
            project_id=project_id,
            status=ConnectorStatus.DEGRADED,
            checked_at=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
            latency_ms=latency_ms,
            data=data,
            error=error,
        )

    @classmethod
    def unavailable(cls, project_id: str, error: str, latency_ms: int = 0) -> "ConnectorResult":
        return cls(
            project_id=project_id,
            status=ConnectorStatus.UNAVAILABLE,
            checked_at=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
            latency_ms=latency_ms,
            error=error,
        )


@dataclass
class ToolDefinition:
    """A single tool that a connector exposes to the orchestration layer."""
    name: str            # e.g. "cg_health", "cg_list_incidents"
    project_id: str
    description: str
    input_schema: dict[str, Any]   # JSON Schema
    output_schema: dict[str, Any]  # JSON Schema (optional hint)
    permission: str      # READ | CONTROLLED | RESTRICTED
    requires_confirmation: bool = False
    timeout_seconds: float = 30.0
    enabled: bool = True
    aliases: set[str] = field(default_factory=set)  # alternate names for intent matching


class BaseConnector(abc.ABC):
    """
    Every connector inherits from this.

    Contract:
    - health() → ConnectorResult  (is the project reachable and responding?)
    - capabilities() → list[ToolDefinition]  (what tools does this connector expose?)
    - execute(tool_name, arguments) → ConnectorResult  (run a tool)
    """

    project_id: str = ""
    project_name: str = ""
    version: str = "0.1.0"

    @abc.abstractmethod
    async def health(self) -> ConnectorResult:
        """Check if the upstream project is reachable and operational."""
        ...

    @abc.abstractmethod
    def capabilities(self) -> list[ToolDefinition]:
        """Return the list of tools this connector exposes."""
        ...

    @abc.abstractmethod
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float = 30.0,
    ) -> ConnectorResult:
        """
        Execute a registered tool.

        Must validate `tool_name` against capabilities() before executing.
        Must not expose raw stack traces or secrets in error messages.
        """
        ...

    # ── Optional overrides ─────────────────────────────────────────────────────

    async def execute_batch(
        self,
        calls: list[tuple[str, dict[str, Any]]],
        timeout_seconds: float = 60.0,
    ) -> list[ConnectorResult]:
        """Default sequential implementation. Override for parallel execution."""
        results: list[ConnectorResult] = []
        for tool_name, args in calls:
            results.append(await self.execute(tool_name, args, timeout_seconds=timeout_seconds))
        return results


class BaseHTTPConnector(BaseConnector):
    """
    Convenience base for connectors that talk to an HTTP API.

    Subclasses set `base_url` and `default_headers`; the execute() implementation
    handles the HTTP call, timeout, and error mapping.
    """

    base_url: str = ""
    default_headers: dict[str, str] = field(default_factory=dict)

    def _build_url(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        return f"{base}{path}"

    async def _http_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout_seconds: float = 30.0,
    ) -> ConnectorResult:
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                start = time.perf_counter()
                response = await client.get(
                    self._build_url(path),
                    params=params,
                    headers=self.default_headers,
                )
                latency_ms = int((time.perf_counter() - start) * 1000)
                if response.status_code == 200:
                    return ConnectorResult.healthy(self.project_id, response.json(), latency_ms)
                elif response.status_code == 401:
                    return ConnectorResult.unavailable(
                        self.project_id,
                        "Authentication failed — check API key",
                        latency_ms,
                    )
                elif response.status_code == 404:
                    return ConnectorResult.degraded(
                        self.project_id,
                        None,
                        f"Endpoint not found: {path}",
                        latency_ms,
                    )
                else:
                    return ConnectorResult.degraded(
                        self.project_id,
                        None,
                        f"Upstream returned {response.status_code}",
                        latency_ms,
                    )
        except httpx.TimeoutException:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Request to {path} timed out after {timeout_seconds}s",
            )
        except httpx.RequestError as e:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Cannot reach {self.base_url}: {e}",
            )

    async def _http_post(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout_seconds: float = 30.0,
    ) -> ConnectorResult:
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                start = time.perf_counter()
                response = await client.post(
                    self._build_url(path),
                    json=json_body,
                    headers=self.default_headers,
                )
                latency_ms = int((time.perf_counter() - start) * 1000)
                if response.status_code in (200, 201, 202):
                    return ConnectorResult.healthy(self.project_id, response.json(), latency_ms)
                elif response.status_code == 401:
                    return ConnectorResult.unavailable(
                        self.project_id,
                        "Authentication failed",
                        latency_ms,
                    )
                else:
                    return ConnectorResult.degraded(
                        self.project_id,
                        None,
                        f"Upstream returned {response.status_code}",
                        latency_ms,
                    )
        except httpx.TimeoutException:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Request to {path} timed out",
            )
        except httpx.RequestError as e:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Cannot reach {self.base_url}: {e}",
            )
