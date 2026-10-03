"""Per-process in-memory rate limiting middleware (SEC-4).

This is a first line of defense, not a substitute for a proper edge limiter
(nginx `limit_req`, a CDN, etc.) in front of a real deployment — see the
single-process caveat in README's "Known limitations" section (ARCH-1). State
lives in a plain dict, so it resets on restart and does not coordinate across
multiple processes/workers.
"""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.config_manager import ConfigManager

_WINDOW_SECONDS = 60
_EXEMPT_PATHS = {"/health", "/ready", "/", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)
        self._config = ConfigManager()

    def _client_key(self, request: Request) -> str:
        # Prefer the API key (stable per client) when auth is configured;
        # otherwise fall back to the connecting IP.
        api_key = request.headers.get("x-api-key") or request.query_params.get("api_key")
        if api_key:
            return f"key:{api_key}"
        return f"ip:{request.client.host}" if request.client else "ip:unknown"

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        try:
            limit = int(self._config.get("api_rate_limit_per_min", "0") or 0)
        except ValueError:
            limit = 0
        if limit <= 0:
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > _WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - hits[0])))
            return JSONResponse(
                {"detail": "Rate limit exceeded — try again shortly"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)
