"""Operational metadata and HTTP hardening for the single-service runtime."""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass

from starlette.responses import JSONResponse

APP_VERSION = "0.7.0"
SERVICE_NAME = "udyampulse"
DEFAULT_MAX_BODY_BYTES = 8 * 1024 * 1024
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _bounded_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


MAX_BODY_BYTES = _bounded_int(
    "UDYAMPULSE_MAX_BODY_BYTES",
    DEFAULT_MAX_BODY_BYTES,
    minimum=64 * 1024,
    maximum=64 * 1024 * 1024,
)


class BodySizeLimitMiddleware:
    """Pure-ASGI enforcement of the request-body ceiling.

    The HTTP-layer ``Content-Length`` check is only a fast-path: a chunked
    request declares no length and slips past it. This middleware buffers the
    incoming body while counting bytes and short-circuits with ``413`` the
    moment the cap is exceeded -- so the limit holds whether or not a length is
    declared. Bodies within the cap are replayed intact to the handler.
    """

    def __init__(self, app, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            message_type = message.get("type")
            if message_type == "http.disconnect":
                return
            if message_type != "http.request":
                # Unexpected message; hand control back without buffering.
                async def _passthrough(_message=message):
                    return _message

                await self.app(scope, _passthrough, send)
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body exceeds the {self.max_bytes}-byte service limit."
                    },
                )
                await response(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        buffered = b"".join(chunks)
        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)


def request_id(incoming: str | None) -> str:
    if incoming and _REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def release_metadata() -> dict:
    commit = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or "local"
    return {
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "commit": commit[:12],
        "mode": os.getenv("UDYAMPULSE_MODE", "public_demo").strip().lower(),
    }


@dataclass(frozen=True)
class SecurityHeaderContext:
    request_id: str
    duration_ms: float
    is_https: bool
    is_json: bool
    path: str


def security_headers(context: SecurityHeaderContext) -> dict[str, str]:
    documentation = context.path in {"/docs", "/redoc"}
    script_sources = "'self' 'unsafe-inline' https://cdn.jsdelivr.net" if documentation else "'self'"
    style_sources = (
        "'self' 'unsafe-inline' https://cdn.jsdelivr.net"
        if documentation
        else "'self'"
    )
    headers = {
        "X-Request-ID": context.request_id,
        "Server-Timing": f"app;dur={context.duration_ms:.2f}",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "X-Permitted-Cross-Domain-Policies": "none",
        "Content-Security-Policy": (
            "default-src 'self'; "
            f"script-src {script_sources}; "
            f"style-src {style_sources}; "
            "font-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        ),
        "Cache-Control": "no-store" if context.is_json else "no-cache",
    }
    if context.is_https:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers
