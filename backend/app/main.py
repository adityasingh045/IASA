"""
ISA FastAPI application entry point.

 Modular monolith — one process, multiple connectors, single API surface.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.llm_adapter import BaseHTTPClient
from app.registry.connector_registry import registry
from app.integrations.connector_campus_guardian import create_cg_connector
from app.integrations.connector_friday import create_friday_connector
from app.api import routes_chat, routes_health, routes_tools


# ── Lifespan ─────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Register connectors
    cg = create_cg_connector()
    registry.register(cg)

    friday = create_friday_connector()
    registry.register(friday)

    # Initial health check (non-blocking — don't fail app startup if a project is down)
    try:
        health = await cg.health()
        print(f"[ISA] Campus Guardian health: {health.status} ({health.latency_ms}ms)")
    except Exception as e:
        print(f"[ISA] Campus Guardian health check failed at startup: {e}")

    try:
        health = await friday.health()
        print(f"[ISA] F.R.I.D.A.Y hub health: {health.status} ({health.latency_ms}ms)")
    except Exception as e:
        print(f"[ISA] F.R.I.D.A.Y hub health check failed at startup: {e}")

    # LLM HTTP client — created once, reused
    app.state.llm_client = BaseHTTPClient(timeout=settings.llm_timeout_seconds)
    yield
    await app.state.llm_client.close()


# ── App ───────────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(routes_health.router)
    app.include_router(routes_tools.router)
    app.include_router(routes_chat.router)

    return app


app = create_app()
