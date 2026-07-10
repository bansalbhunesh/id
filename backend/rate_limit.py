"""Dependency-free in-memory sliding-window rate limiter.

In-memory state is fine for the same reason audit_log.py's in-memory log is
fine: this ships as one process (see main.py's mount comment). A multi-
instance production deployment would move this to a shared store (Redis/
Bedrock-adjacent infra) -- noted as a sandbox-phase upgrade, not pretended
away.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_WINDOW_SECONDS = 60
_hits: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_requests: int, window_seconds: int = _WINDOW_SECONDS):
    def _dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.monotonic()
        recent = [t for t in _hits[key] if now - t < window_seconds]
        if len(recent) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {max_requests} requests per {window_seconds}s.",
            )
        recent.append(now)
        _hits[key] = recent

    return _dependency
