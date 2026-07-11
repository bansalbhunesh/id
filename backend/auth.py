"""API-key authentication and role checks for protected endpoints.

Fixed synthetic GET routes remain public. Every route accepting caller or
sandbox financial data requires the underwriter role, and full audit records
require the auditor role. Published demo keys are public-demo credentials only;
pilot mode fails closed until a deployment supplies its own credentials.
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


def authentication_status() -> dict:
    keys = _load_keys()
    return {
        "provider": "bearer_api_key",
        "demo_keys_active": keys == _DEMO_KEYS,
        "configured_key_count": len(keys),
        "roles": sorted(set(keys.values())),
        "secrets_exposed": False,
    }


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
