"""Dependency-free in-memory sliding-window rate limiter.

In-memory state is fine for the same reason audit_log.py's in-memory log is
fine: this ships as one process (see main.py's mount comment). A multi-
instance production deployment would move this to a shared store (Redis/
Bedrock-adjacent infra) -- noted as a sandbox-phase upgrade, not pretended
away.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from math import ceil

from fastapi import HTTPException, Request, Response

_WINDOW_SECONDS = 60
_hits: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()
_last_cleanup = 0.0


def _prune_stale(now: float, window_seconds: int) -> None:
    global _last_cleanup
    if now - _last_cleanup < window_seconds and len(_hits) < 1000:
        return
    stale = [
        key
        for key, timestamps in _hits.items()
        if not timestamps or now - timestamps[-1] >= window_seconds
    ]
    for key in stale:
        _hits.pop(key, None)
    _last_cleanup = now


def rate_limit(max_requests: int, window_seconds: int = _WINDOW_SECONDS):
    def _dependency(request: Request, response: Response) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.monotonic()
        with _lock:
            _prune_stale(now, window_seconds)
            recent = [t for t in _hits[key] if now - t < window_seconds]
            reset_seconds = max(1, ceil(window_seconds - (now - recent[0]))) if recent else window_seconds
            if len(recent) >= max_requests:
                headers = {
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                }
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {max_requests} requests per {window_seconds}s.",
                    headers=headers,
                )
            recent.append(now)
            _hits[key] = recent
            remaining = max_requests - len(recent)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)

    return _dependency
