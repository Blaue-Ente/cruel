"""Request IDs, security headers, and rate limiting."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import (
    APP_VERSION,
    RATE_LIMIT_ADMIN,
    RATE_LIMIT_ANONYMOUS,
    RATE_LIMIT_AUTHENTICATED,
    RATE_LIMIT_WINDOW_SEC,
)
from app.security.rate_limit import RateLimiter

log = logging.getLogger("argoscout")

_anon = RateLimiter(RATE_LIMIT_ANONYMOUS, RATE_LIMIT_WINDOW_SEC)
_auth = RateLimiter(RATE_LIMIT_AUTHENTICATED, RATE_LIMIT_WINDOW_SEC)
_admin = RateLimiter(RATE_LIMIT_ADMIN, RATE_LIMIT_WINDOW_SEC)

SKIP_PREFIXES = ("/static/",)
SKIP_EXACT = {"/", "/health", "/favicon.ico"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()

        path = request.url.path
        if not _should_skip(path) and request.method not in ("OPTIONS", "HEAD"):
            limited = _rate_limit(request)
            if limited is not None:
                limited.headers["X-Request-Id"] = request_id
                return limited

        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled_error request_id=%s path=%s", request_id, path)
            raise

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-ArgosScout-Version"] = APP_VERSION
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if path.startswith("/api") or path.startswith("/admin") or path == "/health":
            response.headers["Cache-Control"] = "no-store"
        log.info(
            "request_id=%s method=%s path=%s status=%s ms=%s",
            request_id,
            request.method,
            path,
            response.status_code,
            elapsed_ms,
        )
        return response


def _should_skip(path: str) -> bool:
    if path in SKIP_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in SKIP_PREFIXES)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request) -> JSONResponse | None:
    path = request.url.path
    api_key = request.headers.get("X-API-Key") or ""
    admin = request.headers.get("X-Admin-Secret") or ""

    if path.startswith("/admin"):
        limiter, key, scope = _admin, f"admin:{_client_ip(request)}:{admin[-6:]}", "admin"
    elif api_key:
        limiter, key, scope = _auth, f"key:{api_key[:18]}", "authenticated"
    elif path.startswith("/api") or path.startswith("/ws"):
        limiter, key, scope = _anon, f"ip:{_client_ip(request)}", "anonymous"
    else:
        return None

    allowed, remaining, retry = limiter.allow(key)
    if allowed:
        request.state.rate_remaining = remaining
        return None

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "scope": scope,
            "retry_after_seconds": retry,
        },
        headers={"Retry-After": str(retry)},
    )


def install_security_middleware(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
