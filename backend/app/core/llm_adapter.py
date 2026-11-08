"""
ISA LLM provider adapter.

The orchestration layer never calls a specific LLM API directly.
It goes through this adapter, which is swappable by changing the
`llm_provider` setting.

Each provider implementation must support:
- completion with structured tool definitions
- structured output (JSON mode / tool calling)
- timeout and retry policy
"""
from __future__ import annotations

import abc
import time
from typing import Any

import asyncio
import time

import httpx

from app.core.config import get_settings
from app.core.errors import LLMError, LLMTimeoutError


class LLMAdapter(abc.ABC):
    """Abstract interface every LLM provider must implement."""

    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""

    @abc.abstractmethod
    def describe_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert internal tool definitions to the provider's tool format."""

    @abc.abstractmethod
    def build_messages(self, history: list[dict[str, str]], system: str) -> list[dict[str, str]]:
        """Build the messages array for the provider's API."""

    @abc.abstractmethod
    def parse_tool_calls(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract proposed tool calls from a provider response."""

    @abc.abstractmethod
    def parse_text_response(self, response: dict[str, Any]) -> str:
        """Extract the text response when no tool was called."""


class BaseHTTPClient:
    """Shared HTTP client with timeout and retry for LLM calls."""

    def __init__(self, timeout: float = 30.0, max_retries: int = 2):
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> dict[str, Any]:
        """POST with retry on transient failures."""
        last_error: Exception | None = None
        for attempt in range(1 + self._max_retries):
            try:
                async with await self.get_client() as client:
                    response = await client.post(url, headers=headers, json=json_body)
                    response.raise_for_status()
                    return response.json()
            except httpx.TimeoutException as e:
                last_error = e
                if attempt == self._max_retries:
                    raise LLMTimeoutError(url=url, timeout=self._timeout) from e
            except httpx.HTTPStatusError as e:
                # Non-retryable on 4xx; retry 5xx
                if e.response.status_code < 500:
                    raise LLMError(
                        message=f"LLM API returned {e.response.status_code}",
                        status_code=e.response.status_code,
                        body=str(e.response.text),
                    ) from e
                last_error = e
            await asyncio.sleep(min(2 ** attempt, 8))
        raise LLMError(message="LLM request failed after retries", cause=last_error)


# ── Provider registry ──────────────────────────────────────────────────────────
_provider_map: dict[str, type[LLMAdapter]] = {}


def register_provider(name: str):
    def decorator(cls: type[LLMAdapter]) -> type[LLMAdapter]:
        _provider_map[name] = cls
        return cls

    return decorator


def get_adapter(provider: str = "") -> LLMAdapter:
    """Factory: return the registered adapter for `provider`."""
    if not provider:
        provider = get_settings().llm_provider
    try:
        return _provider_map[provider]()
    except KeyError:
        raise LLMError(
            message=f"Unknown or unregistered LLM provider: {provider}. "
            f"Registered: {list(_provider_map.keys())}"
        )



