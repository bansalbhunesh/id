"""Environment settings with a preferred and a legacy prefix.

The service was renamed UdyamPulse -> SaakhScore on 2026-07-13. Existing
deployments (Render blueprint, dashboards, operator runbooks) still export
``UDYAMPULSE_*`` variables, so every setting is read through this helper:
``SAAKHSCORE_<suffix>`` wins when both are set, ``UDYAMPULSE_<suffix>`` is
honored as a fallback, and the code never needs to know which one supplied
the value. New deployments should use the ``SAAKHSCORE_`` prefix only.
"""
from __future__ import annotations

import os

PREFERRED_PREFIX = "SAAKHSCORE_"
LEGACY_PREFIX = "UDYAMPULSE_"


def env_setting(suffix: str, default: str | None = None) -> str | None:
    """Return the setting for ``suffix``, preferring the SAAKHSCORE_ prefix.

    Mirrors ``os.getenv`` chaining semantics: a variable that is set to an
    empty string still counts as set, exactly as the pre-migration call
    sites behaved.
    """
    value = os.environ.get(PREFERRED_PREFIX + suffix)
    if value is not None:
        return value
    value = os.environ.get(LEGACY_PREFIX + suffix)
    if value is not None:
        return value
    return default
