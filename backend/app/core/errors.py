"""
ISA error types.

All connector and LLM errors inherit from here so the orchestration layer
can map them to user-facing messages without leaking internals.
"""
from __future__ import annotations


class ISAError(Exception):
    """Base for all ISA-level errors."""
    message: str = "ISA error"
    cause: Exception | None = None

    def __str__(self) -> str:
        return self.message


class LLMError(ISAError):
    """LLM provider call failed."""
    def __init__(self, message: str = "LLM call failed", status_code: int | None = None, body: str = "", cause: Exception | None = None):
        super().__init__(message=message, cause=cause)
        self.status_code = status_code
        self.body = body


class LLMTimeoutError(LLMError):
    """LLM provider did not respond within the configured timeout."""
    def __init__(self, url: str = "", timeout: float = 30.0, cause: Exception | None = None):
        super().__init__(
            message=f"LLM provider timed out after {timeout}s (url: {url})",
            cause=cause,
        )


class ConnectorError(ISAError):
    """A project connector call failed in an expected way (bad args, auth, etc.)."""
    ...


class ConnectorUnavailableError(ConnectorError):
    """The upstream project is unreachable or not responding."""
    ...


class PermissionDeniedError(ISAError):
    """The user is not authorized for the requested action."""
    def __init__(self, message: str = "Permission denied", tool_name: str = "", permission: str = ""):
        super().__init__(message=message)
        self.tool_name = tool_name
        self.permission = permission


class ToolNotFoundError(ConnectorError):
    """The requested tool name is not registered on any connector."""
    def __init__(self, tool_name: str = ""):
        super().__init__(message=f"Tool not found: {tool_name}")
        self.tool_name = tool_name


class ToolArgumentError(ConnectorError):
    """Tool arguments failed schema validation."""
    def __init__(self, tool_name: str = "", errors: dict | None = None):
        super().__init__(message=f"Invalid arguments for tool: {tool_name}")
        self.tool_name = tool_name
        self.errors = errors or {}


class ApprovalRequiredError(ISAError):
    """The action requires user confirmation before execution."""
    def __init__(self, tool_name: str = "", action_description: str = ""):
        super().__init__(message=f"Approval required for: {tool_name}")
        self.tool_name = tool_name
        self.action_description = action_description
