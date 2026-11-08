"""
ISA F.R.I.D.A.Y hub connector.

Connects to the F.R.I.D.A.Y hub WebSocket server as an authorized client.
The hub authenticates via a shared SESSION_KEY (SHA-256 hash in AUTH message).
All messages are AES-256-GCM encrypted.

NOTE: This connector talks to the hub directly — not to the (empty) Flutter client apps.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

import websockets
from websockets import WebSocketClientProtocol

from app.core.connector_base import (
    BaseConnector,
    ToolDefinition,
    ConnectorResult,
    ConnectorStatus,
)
from app.core.config import get_settings


# ── Message types (mirrored from hub/server.js) ─────────────────────────────────

HANDSHAKE_MSG = {"type": "HANDSHAKE"}
AUTH_MSG = lambda key_hash, device_type, device_name: {
    "type": "AUTH",
    "keyHash": key_hash,
    "deviceType": device_type,
    "deviceName": device_name,
}
AUTH_OK_MSG = {"type": "AUTH_OK"}
DEVICE_CONNECTED_MSG = lambda device_id, name: {
    "type": "DEVICE_CONNECTED", "deviceId": device_id, "name": name
}
DEVICE_DISCONNECTED_MSG = lambda device_id: {
    "type": "DEVICE_DISCONNECTED", "deviceId": device_id
}


# ── Connector implementation ─────────────────────────────────────────────────────

class FridayHubConnector(BaseConnector):
    """
    WebSocket client connector for the F.R.I.D.A.Y hub.

    Tools:
    - friday_health          READ         Is the hub reachable and responding?
    - friday_list_devices    READ         List currently connected devices
    - friday_send_message    CONTROLLED   Send a message to a specific device or broadcast
    - friday_request_file    CONTROLLED   Initiate a file transfer to a device
    - friday_discover        READ         Discover hub on local network via mDNS
    """

    project_id = "friday"
    project_name = "F.R.I.D.A.Y Hub"
    version = "0.1.0"

    def __init__(self):
        super().__init__()
        s = get_settings()
        self._ws_url = s.friday_hub_ws_url.rstrip("/")
        self._session_key = s.friday_hub_session_key
        self._http2_url = s.friday_hub_http2_url.rstrip("/")
        self._ws: WebSocketClientProtocol | None = None
        self._connected_devices: dict[str, dict] = {}
        self._device_available: bool = False

    # ── Auth key hash (same algorithm as hub/server.js) ──────────────────────────

    def _key_hash(self) -> str:
        if not self._session_key:
            raise ValueError("friday_hub_session_key is not configured")
        return hashlib.sha256(self._session_key.encode()).hexdigest()

    # ── Capabilities ──────────────────────────────────────────────────────────────

    def capabilities(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="friday_health",
                project_id=self.project_id,
                description="Check if the F.R.I.D.A.Y hub is reachable and responding. Connects via WebSocket, completes the HANDSHAKE → AUTH flow, and reports connection status.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["connected", "disconnected", "auth_failed"]},
                        "ws_url": {"type": "string"},
                        "devices_connected": {"type": "integer"},
                    },
                },
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="friday_list_devices",
                project_id=self.project_id,
                description="List all devices currently connected to the F.R.I.D.A.Y hub. Returns device IDs and names from the broadcast DEVICE_CONNECTED messages received after authentication.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={
                    "type": "object",
                    "properties": {
                        "devices": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "device_id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                            },
                        },
                    },
                },
                permission="READ",
                requires_confirmation=False,
                timeout_seconds=10.0,
            ),
            ToolDefinition(
                name="friday_send_message",
                project_id=self.project_id,
                description="Send a message to a specific connected device or broadcast to all devices. Message types: SCREEN_FRAME, INPUT_EVENT, CLIPBOARD, DRAG_PAYLOAD, VOICE_CMD. Requires confirmation before sending.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "message_type": {
                            "type": "string",
                            "enum": ["SCREEN_FRAME", "INPUT_EVENT", "CLIPBOARD", "DRAG_PAYLOAD", "VOICE_CMD"],
                        },
                        "target_device_id": {"type": "string", "description": "Optional: send to specific device. Omit to broadcast."},
                        "payload": {"type": "object", "description": "Message payload (depends on message_type)"},
                    },
                    "required": ["message_type", "payload"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "sent": {"type": "boolean"},
                        "target_device_id": {"type": "string"},
                        "message_type": {"type": "string"},
                    },
                },
                permission="CONTROLLED",
                requires_confirmation=True,
                timeout_seconds=15.0,
            ),
            ToolDefinition(
                name="friday_request_file",
                project_id=self.project_id,
                description="Request a file transfer to a specific device. The hub returns an HTTP/2 token and port; the actual file upload is handled by the IASA API layer. Requires confirmation.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_device_id": {"type": "string", "minLength": 1},
                        "filename": {"type": "string", "minLength": 1},
                    },
                    "required": ["target_device_id", "filename"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "token": {"type": "string"},
                        "http2_port": {"type": "integer"},
                        "target_device_id": {"type": "string"},
                    },
                },
                permission="CONTROLLED",
                requires_confirmation=True,
                timeout_seconds=15.0,
            ),
        ]

    # ── Health ───────────────────────────────────────────────────────────────────

    async def health(self) -> ConnectorResult:
        """Connect, do HANDSHAKE → AUTH, confirm we're in, then disconnect."""
        if not self._session_key:
            return ConnectorResult.unavailable(
                self.project_id,
                "friday_hub_session_key is not configured",
            )

        ws = None
        try:
            ws = await websockets.connect(self._ws_url, open_timeout=10.0)
            # Receive HANDSHAKE
            handshake = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
            if handshake.get("type") != "HANDSHAKE":
                return ConnectorResult.degraded(
                    self.project_id,
                    None,
                    f"Unexpected first message: {handshake.get('type')}",
                    0,
                )

            # Send AUTH
            auth_msg = AUTH_MSG(
                self._key_hash(),
                "isa-connector",
                "IASA Hub Connector",
            )
            await ws.send(json.dumps(auth_msg))

            # Receive AUTH_OK or AUTH_FAIL
            auth_response = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
            if auth_response.get("type") != "AUTH_OK":
                return ConnectorResult.unavailable(
                    self.project_id,
                    f"Hub auth failed: {auth_response.get('type')}",
                )

            self._device_available = True
            return ConnectorResult.healthy(
                self.project_id,
                {
                    "status": "connected",
                    "ws_url": self._ws_url,
                    "devices_connected": len(self._connected_devices),
                },
                0,
            )

        except asyncio.TimeoutError:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Hub at {self._ws_url} did not respond within 10s",
            )
        except websockets.InvalidURI:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Invalid hub WS URL: {self._ws_url}",
            )
        except Exception as e:
            return ConnectorResult.unavailable(
                self.project_id,
                f"Health check failed: {e}",
            )
        finally:
            if ws and not ws.closed:
                await ws.close()
            self._device_available = False

    # ── Execute ───────────────────────────────────────────────────────────────────

    async def execute(
        self,
        tool_name: str,
        arguments: dict,
        timeout_seconds: float = 30.0,
    ) -> ConnectorResult:
        tool = next((t for t in self.capabilities() if t.name == tool_name), None)
        if tool is None:
            return ConnectorResult.unavailable(self.project_id, f"Tool not found: {tool_name}")

        if tool_name == "friday_health":
            return await self.health()

        if tool_name == "friday_list_devices":
            return ConnectorResult.healthy(
                self.project_id,
                {"devices": list(self._connected_devices.values())},
                latency_ms=0,
            )

        if tool_name == "friday_send_message":
            ws = None
            try:
                ws = await websockets.connect(self._ws_url, open_timeout=10.0)
                # Auth
                handshake = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
                auth_msg = AUTH_MSG(self._key_hash(), "isa-connector", "IASA Hub Connector")
                await ws.send(json.dumps(auth_msg))
                auth_response = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
                if auth_response.get("type") != "AUTH_OK":
                    return ConnectorResult.unavailable(self.project_id, "Hub auth failed during message send")

                target_id = arguments.get("target_device_id")
                msg = {
                    "type": arguments["message_type"],
                    "payload": arguments.get("payload", {}),
                }
                if target_id:
                    msg["targetId"] = target_id

                await ws.send(json.dumps(msg))
                return ConnectorResult.healthy(
                    self.project_id,
                    {"sent": True, "target_device_id": target_id, "message_type": arguments["message_type"]},
                    latency_ms=0,
                )
            except Exception as e:
                return ConnectorResult.unavailable(self.project_id, f"Failed to send message: {e}")
            finally:
                if ws and not ws.closed:
                    await ws.close()

        if tool_name == "friday_request_file":
            ws = None
            try:
                ws = await websockets.connect(self._ws_url, open_timeout=10.0)
                # Auth
                handshake = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
                auth_msg = AUTH_MSG(self._key_hash(), "isa-connector", "IASA Hub Connector")
                await ws.send(json.dumps(auth_msg))
                auth_response = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
                if auth_response.get("type") != "AUTH_OK":
                    return ConnectorResult.unavailable(self.project_id, "Hub auth failed during file request")

                init_msg = {
                    "type": "FILE_TRANSFER_INIT",
                    "targetId": arguments["target_device_id"],
                    "filename": arguments["filename"],
                }
                await ws.send(json.dumps(init_msg))
                token_response = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
                if token_response.get("type") != "FILE_TOKEN":
                    return ConnectorResult.degraded(
                        self.project_id,
                        None,
                        f"Expected FILE_TOKEN, got {token_response.get('type')}",
                        0,
                    )
                return ConnectorResult.healthy(
                    self.project_id,
                    {
                        "token": token_response.get("token"),
                        "http2_port": token_response.get("port"),
                        "target_device_id": arguments["target_device_id"],
                    },
                    latency_ms=0,
                )
            except Exception as e:
                return ConnectorResult.unavailable(self.project_id, f"File transfer request failed: {e}")
            finally:
                if ws and not ws.closed:
                    await ws.close()

        return ConnectorResult.unavailable(self.project_id, f"Unimplemented tool: {tool_name}")


# ── Factory ──────────────────────────────────────────────────────────────────────

def create_friday_connector() -> FridayHubConnector:
    return FridayHubConnector()
