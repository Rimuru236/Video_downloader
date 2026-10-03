"""API key authentication.

Single shared-secret auth, matching this app's single-user/self-hosted
design: when the `api_key` setting is empty (the default), auth is disabled
and every route stays open — the same behavior as before this module
existed, so upgrading doesn't break existing trusted local/LAN deployments.
Setting a key (via SV_API_KEY or the Settings page) requires every
authenticated request to present it, either as the `X-API-Key` header
(normal HTTP requests) or an `api_key` query parameter (the WebSocket
progress endpoint — browsers cannot attach custom headers to a WebSocket
handshake, so the key has to travel in the URL there instead).
"""
import hmac
import logging
from typing import Optional

from fastapi import Header, HTTPException
from starlette.websockets import WebSocket

from config.config_manager import ConfigManager

logger = logging.getLogger("streamvault.auth")
config = ConfigManager()

_warned_unprotected = False


def _configured_key() -> str:
    return config.get("api_key", "")


def _warn_if_unprotected():
    global _warned_unprotected
    if not _configured_key() and not _warned_unprotected:
        _warned_unprotected = True
        logger.warning(
            "No api_key is configured — every StreamVault API endpoint is "
            "reachable by anyone who can reach this port. Set SV_API_KEY (or "
            "the 'api_key' setting) before exposing this beyond a trusted "
            "local network."
        )


async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """FastAPI dependency — attach to any router that should require auth."""
    expected = _configured_key()
    _warn_if_unprotected()
    if not expected:
        return  # no key configured: auth disabled
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Missing or invalid API key")


def ws_api_key_ok(websocket: WebSocket) -> bool:
    """Same check for the WebSocket route. Returns True if the connection
    should proceed; the caller must reject it (before accept(), so nothing is
    exchanged first) when this returns False."""
    expected = _configured_key()
    _warn_if_unprotected()
    if not expected:
        return True
    provided = websocket.query_params.get("api_key", "")
    return hmac.compare_digest(provided, expected)
