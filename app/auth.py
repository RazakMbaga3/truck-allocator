"""
app/auth.py — API key authentication for the Smart Return Truck Allocator.

Usage:
    from app.auth import require_api_key

    @router.get("/protected")
    async def protected_endpoint(api_key: str = Depends(require_api_key)):
        ...

Skip list (no auth required):
    /api/health, /docs, /redoc, /openapi.json, /static/*, /

Authentication:
    Header: X-API-Key: <key>
    The key must match settings.app_api_key.

    When settings.app_api_key is the dev default ("dev-api-key-change-me"),
    auth is DISABLED and a warning is logged — dev mode only.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_DEV_KEY = "dev-api-key-change-me"

# FastAPI security scheme — documents the X-API-Key header in Swagger UI
_api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key for authenticated endpoints. Omit in dev mode.",
)

# Paths that NEVER require authentication, even in production
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
    "/proposals",
    "/confirmed",
})

_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/api/schedules/feed",  # SSE stream — browsers can't send custom headers
)


# ── Dependency ────────────────────────────────────────────────────────────────

async def require_api_key(
    request: Request,
    provided_key: Optional[str] = Depends(_api_key_scheme),
) -> str:
    """
    FastAPI dependency that validates the X-API-Key header.

    Returns the key string on success.
    Raises HTTP 401 on failure (in production).

    In dev mode (app_api_key == dev default), auth is skipped entirely and a
    WARNING is logged on each call so the dev knows it's unauthenticated.
    """
    settings = get_settings()
    configured_key = settings.app_api_key

    # ── Dev mode: auth disabled ───────────────────────────────────
    if configured_key == _DEV_KEY:
        logger.warning(
            "auth_skipped path=%s method=%s — set APP_API_KEY in .env for production",
            request.url.path,
            request.method,
        )
        return configured_key

    # ── Public paths: no key required ────────────────────────────
    path = request.url.path
    if path in _PUBLIC_PATHS:
        return ""
    if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return ""

    # ── Validate key ──────────────────────────────────────────────
    if not provided_key:
        logger.warning(
            "auth_missing path=%s method=%s ip=%s",
            path,
            request.method,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if provided_key != configured_key:
        logger.warning(
            "auth_invalid path=%s method=%s ip=%s key_prefix=%s",
            path,
            request.method,
            request.client.host if request.client else "unknown",
            provided_key[:6] + "..." if len(provided_key) > 6 else "***",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return provided_key


# ── Middleware variant (optional — attach to app for global enforcement) ──────

class APIKeyMiddleware:
    """
    ASGI middleware that enforces API key on ALL routes except the skip list.

    Usage in main.py (add BEFORE routers if you want global enforcement):
        from app.auth import APIKeyMiddleware
        app.add_middleware(APIKeyMiddleware)

    The Depends(require_api_key) approach (above) is preferred for per-router
    granularity; this middleware is provided for full-app lockdown if needed.
    """

    def __init__(self, app):
        self.app = app
        self._settings = get_settings()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        # Always let through public paths and dev mode
        if self._is_public(path) or self._settings.app_api_key == _DEV_KEY:
            await self.app(scope, receive, send)
            return

        # Extract key from headers
        headers = dict(scope.get("headers", []))
        key_bytes = headers.get(b"x-api-key", b"")
        provided_key = key_bytes.decode("utf-8", errors="replace")

        if provided_key != self._settings.app_api_key:
            from starlette.responses import JSONResponse
            response = JSONResponse(
                {"detail": "Invalid or missing API key."},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _is_public(self, path: str) -> bool:
        if path in _PUBLIC_PATHS:
            return True
        return any(path.startswith(p) for p in _PUBLIC_PREFIXES)
