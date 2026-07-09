"""ML explainability layer.

The public build trains a dependency-free linear PD-proxy model once at
import time and exposes exact SHAP-equivalent feature contributions.
When IDBI sandbox labels and optional production ML packages are available,
`UDYAMPULSE_MODEL_PROVIDER=xgboost|lightgbm` plus
`UDYAMPULSE_TRAINING_DATA=/path/to/labelled.jsonl` can switch the same
public `explain` contract to a gradient-boosted model with SHAP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from linear_model import FEATURE_NAMES, LinearModel
from scoring import MSMEProfile
from synthetic_training import generate_training_set

MIN_PRODUCTION_ROWS = 1000

_linear_model = LinearModel()
_rows, _targets = generate_training_set()
_linear_model.fit(_rows, _targets)
_runtime_status: dict = {
    "active_provider": "linear",
    "requested_provider": os.getenv("UDYAMPULSE_MODEL_PROVIDER", "linear").lower(),
    "training_data": "public synthetic cohort",
    "records": len(_rows),
    "explainability": "exact linear Shapley contributions",
    "fallback": None,
}
_gbm_bundle: dict | None = None


def _to_features(p: MSMEProfile) -> dict[str, float]:
    return {name: getattr(p, name) for name in FEATURE_NAMES}


def _load_labelled_rows(path: str) -> tuple[list[dict[str, float]], list[float]]:
    rows: list[dict[str, float]] = []
    targets: list[float] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            target = item.get("target_score", item.get("score"))
            if target is None:
                raise ValueError(f"Missing target score on line {line_number}")
            source = item.get("features", item)
            rows.append({name: float(source[name]) for name in FEATURE_NAMES})
            targets.append(float(target))
    return rows, targets


def _try_build_gbm() -> None:
    global _gbm_bundle, _runtime_status

    provider = _runtime_status["requested_provider"]
    if provider not in {"xgboost", "lightgbm"}:
        return

    data_path = os.getenv("UDYAMPULSE_TRAINING_DATA")
    if not data_path:
        _runtime_status["fallback"] = "UDYAMPULSE_TRAINING_DATA is not configured."
        return

    try:
        rows, targets = _load_labelled_rows(data_path)
        min_rows = int(os.getenv("UDYAMPULSE_MIN_GBM_ROWS", str(MIN_PRODUCTION_ROWS)))
        if len(rows) < min_rows:
            _runtime_status["fallback"] = f"Only {len(rows)} labelled rows found; {min_rows} required for GBM mode."
            return

        if provider == "xgboost":
            from xgboost import XGBRegressor as Regressor  # type: ignore
        else:
            from lightgbm import LGBMRegressor as Regressor  # type: ignore
        import shap  # type: ignore

        matrix = [[row[name] for name in FEATURE_NAMES] for row in rows]
        model = Regressor(n_estimators=300, max_depth=3, learning_rate=0.05, random_state=42)
        model.fit(matrix, targets)
        explainer = shap.Explainer(model, matrix[: min(500, len(matrix))])
        baseline = float(getattr(explainer, "expected_value", sum(targets) / len(targets)))
        if isinstance(baseline, list):
            baseline = float(baseline[0])
        _gbm_bundle = {
            "model": model,
            "explainer": explainer,
            "baseline": baseline,
        }
        _runtime_status = {
            "active_provider": provider,
            "requested_provider": provider,
            "training_data": str(Path(data_path)),
            "records": len(rows),
            "explainability": "Tree SHAP via shap package",
            "fallback": None,
        }
    except Exception as exc:  # optional production dependencies must not break demo mode
        _runtime_status["fallback"] = f"{provider} mode unavailable: {exc.__class__.__name__}"
        _gbm_bundle = None


def model_status() -> dict:
    return dict(_runtime_status)


def _linear_explain(features: dict[str, float]) -> dict:
    predicted = _linear_model.predict(features)
    contributions = _linear_model.shap_contributions(features)
    baseline = _linear_model.baseline_prediction
    return _format_explanation(predicted, baseline, contributions)


def _gbm_explain(features: dict[str, float]) -> dict:
    assert _gbm_bundle is not None
    matrix = [[features[name] for name in FEATURE_NAMES]]
    predicted = float(_gbm_bundle["model"].predict(matrix)[0])
    shap_values = _gbm_bundle["explainer"](matrix).values[0]
    contributions = {name: float(value) for name, value in zip(FEATURE_NAMES, shap_values)}
    return _format_explanation(predicted, _gbm_bundle["baseline"], contributions)


def _format_explanation(predicted: float, baseline: float, contributions: dict[str, float]) -> dict:
    raw_predicted = predicted
    raw_baseline = baseline
    predicted = max(0.0, min(100.0, raw_predicted))
    baseline = max(0.0, min(100.0, raw_baseline))
    contribution_sum = sum(contributions.values())
    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top_reasons = [
        f"{'+' if value >= 0 else ''}{value:.1f} pts from {name.replace('_', ' ')}"
        for name, value in ranked[:4]
    ]

    return {
        "predicted_score": round(predicted, 1),
        "baseline_score": round(baseline, 1),
        "shap_contributions": {k: round(v, 2) for k, v in contributions.items()},
        "top_reasons": top_reasons,
        "provider": _runtime_status["active_provider"],
        "shap_sum_check": round(contribution_sum - (raw_predicted - raw_baseline), 4),
    }


def explain(p: MSMEProfile) -> dict:
    features = _to_features(p)
    if _gbm_bundle is not None:
        return _gbm_explain(features)
    return _linear_explain(features)


_try_build_gbm()
