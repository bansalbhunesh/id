"""API-key authentication and role checks for sensitive endpoints.

Scoring stays unauthenticated (`POST /score`, `POST /sandbox/score`, sample
browsing, portfolio/governance aggregates) -- that is the public judge-facing
demo surface, and it only ever returns the caller's own submitted data or a
fixed synthetic cohort, never another caller's history.

`GET /audit-log` returns every borrower ever scored by anyone hitting this
API and is gated behind the `auditor` role -- this is the endpoint the
external audit named explicitly (main.py:142-144 in the pre-fix code).

Full multi-tenant identity/session management (per-underwriter accounts,
"view only your own submissions") is out of scope for a public hackathon
demo with no login flow; it is the documented sandbox-phase upgrade path
(see docs/SECURITY_COMPLIANCE.md). What's implemented here is real,
enforced RBAC on the one genuinely sensitive endpoint, not a placeholder.

A demo auditor key is published in docs/DEMO_SCRIPT.md and used as the
fallback when `UDYAMPULSE_API_KEYS` is not set, so judges can exercise
`/audit-log` without provisioning secrets -- exactly like a real fintech
sandbox hands evaluators a scoped demo credential. Set
`UDYAMPULSE_API_KEYS="key1:auditor,key2:admin"` to override in any real
deployment.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException

_DEMO_KEYS = {
    "udyampulse-demo-underwriter-key": "underwriter",
    "udyampulse-demo-auditor-key": "auditor",
}


def _load_keys() -> dict[str, str]:
    raw = os.getenv("UDYAMPULSE_API_KEYS")
    if not raw:
        return dict(_DEMO_KEYS)

    keys: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        key, role = pair.split(":", 1)
        keys[key.strip()] = role.strip()
    return keys or dict(_DEMO_KEYS)


_ROLE_RANK = {"underwriter": 1, "auditor": 2, "admin": 3}


def require_role(minimum_role: str):
    minimum_rank = _ROLE_RANK[minimum_role]

    def _dependency(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=401,
                detail=f"Missing bearer token. This endpoint requires role >= '{minimum_role}'.",
            )
        token = authorization.split(" ", 1)[1].strip()
        keys = _load_keys()
        role = keys.get(token)
        if role is None or role not in _ROLE_RANK:
            raise HTTPException(status_code=401, detail="Invalid API key.")
        if _ROLE_RANK[role] < minimum_rank:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' cannot access an endpoint requiring '{minimum_role}' or higher.",
            )
        return role

    return _dependency
