"""
ISA core settings.
All secrets are loaded from environment / .env — never hardcoded.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "IASA"
    version: str = "0.1.0"
    environment: str = "development"  # development | staging | production

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql://isa_user:isa_pass@localhost:5432/isa_db"

    # ── Redis (cache / short-lived state / task coordination) ─────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Authentication ─────────────────────────────────────────────────────────
    # OIDC-compatible: we accept JWTs from an external IdP.
    # For local development, a simple shared secret signs session tokens.
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_token_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 7

    # ── LLM Provider (adapter-backed; configurable per environment) ────────────
    llm_provider: str = "openai"  # openai | anthropic | local-ollama | ...
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 4096

    # ── Campus Guardian connector ──────────────────────────────────────────────
    cg_api_base_url: str = "http://localhost:8000"
    cg_api_key: str = ""  # X-API-Key for Campus Guardian REST + WS

    # ── F.R.I.D.A.Y hub connector ──────────────────────────────────────────────
    friday_hub_ws_url: str = "ws://localhost:8765"
    friday_hub_session_key: str = ""  # SESSION_KEY shared with hub
    friday_hub_http2_url: str = "http://localhost:8766"

    # ── Memory / privacy ───────────────────────────────────────────────────────
    # Do not send these data categories to the LLM provider without explicit review.
    block_pii_to_llm: bool = True

    # ── Observability ──────────────────────────────────────────────────────────
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
