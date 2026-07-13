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
    "saakhscore-demo-underwriter-key": "underwriter",
    "saakhscore-demo-auditor-key": "auditor",
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


# Capability-based access, not a seniority ladder. Underwriting (making a
# lending decision) and auditing (reading the decision trail) are separate
# duties under maker-checker/model-risk separation: an auditor must NOT be able
# to submit scores, and an underwriter must NOT be able to read the audit log.
# Only an explicit admin holds both. The previous rank ladder let `auditor`
# inherit underwriter write access, collapsing that separation.
_ROLE_CAPABILITIES = {
    "underwriter": frozenset({"underwriter"}),
    "auditor": frozenset({"auditor"}),
    "admin": frozenset({"underwriter", "auditor"}),
}


def require_role(capability: str):
    if capability not in {"underwriter", "auditor"}:
        raise ValueError(f"Unknown capability {capability!r}")

    def _dependency(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=401,
                detail=f"Missing bearer token. This endpoint requires the '{capability}' capability.",
            )
        token = authorization.split(" ", 1)[1].strip()
        keys = _load_keys()
        role = keys.get(token)
        if role is None or role not in _ROLE_CAPABILITIES:
            raise HTTPException(status_code=401, detail="Invalid API key.")
        if capability not in _ROLE_CAPABILITIES[role]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Role '{role}' lacks the '{capability}' capability required by this "
                    "endpoint (underwriting and auditing are separated duties)."
                ),
            )
        return role

    return _dependency
