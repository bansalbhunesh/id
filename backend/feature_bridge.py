"""Runtime half of the universal-risk-feature bridge (stdlib only, no
training-time dependencies). See model_training/feature_bridge.py for the
UCI-side mapping and the full rationale for what is included/excluded.

`msme_pillars_to_universal` takes the 0-20 pillar scores scoring.py already
computes and rescales the 3 pillars the PD model was trained on to 0-1, so
the live app feeds the model the exact same feature definitions it saw
during training.
"""
from __future__ import annotations

UNIVERSAL_FEATURES = ["discipline", "leverage", "liquidity"]


def msme_pillars_to_universal(pillars_0_20: dict[str, float]) -> dict[str, float]:
    return {
        "discipline": pillars_0_20["discipline"] / 20.0,
        "leverage": pillars_0_20["leverage"] / 20.0,
        "liquidity": pillars_0_20["liquidity"] / 20.0,
    }
