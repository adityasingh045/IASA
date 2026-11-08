"""
ISA public health endpoint.

No auth required — used by load balancers, monitors, and the investor demo.
Returns overall ISA status + per-project connector health.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.registry.connector_registry import registry
from app.core.connector_base import ConnectorStatus

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def isa_health():
    """
    ISA-level health check.

    Returns:
    - isa status (ok | degraded | starting)
    - timestamp
    - per-project health from each registered connector
    """
    connector_health = {}
    all_healthy = True
    any_known = False

    for conn in registry.list():
        try:
            result = await conn.health()
            connector_health[conn.project_id] = {
                "status": result.status.value,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "data": result.data,
            }
            if result.status != ConnectorStatus.HEALTHY:
                all_healthy = False
            any_known = True
        except Exception as e:
            connector_health[conn.project_id] = {
                "status": "unavailable",
                "latency_ms": 0,
                "error": str(e),
                "data": None,
            }
            all_healthy = False
            any_known = True

    if not any_known:
        overall = "starting"
    elif all_healthy:
        overall = "ok"
    else:
        overall = "degraded"

    return {
        "service": "isa",
        "status": overall,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "projects": connector_health,
    }
