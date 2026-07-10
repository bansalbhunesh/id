"""ML explainability layer.

Default runtime model: a logistic-regression PD (probability of default)
model trained on a real binary default-outcome label from a public dataset
(backend/model_training/train_pd_model.py), loaded from the committed
`model_training/artifacts/artifact.json`. No scikit-learn/xgboost/shap is
required to serve -- `pd_model.LogisticModel` is dependency-free stdlib
Python, exactly like the linear model it replaces as the default provider.

Every score also gets an optional GBM upgrade path: when IDBI sandbox labels
and optional production ML packages are available,
`UDYAMPULSE_MODEL_PROVIDER=xgboost|lightgbm` plus
`UDYAMPULSE_TRAINING_DATA=/path/to/labelled.jsonl` switches the same public
`explain` contract to a gradient-boosted model with SHAP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from feature_bridge import UNIVERSAL_FEATURES, msme_pillars_to_universal
from linear_model import FEATURE_NAMES, LinearModel
from pd_model import LogisticModel
from scoring import MSMEProfile
from synthetic_training import generate_training_set

MIN_PRODUCTION_ROWS = 1000
ARTIFACT_PATH = Path(__file__).parent / "model_training" / "artifacts" / "artifact.json"
EVALUATION_PATH = Path(__file__).parent / "model_training" / "artifacts" / "evaluation.json"


def _load_pd_model() -> tuple[LogisticModel | None, dict]:
    if not ARTIFACT_PATH.exists():
        return None, {
            "active_provider": "linear_synthetic_fallback",
            "requested_provider": os.getenv("UDYAMPULSE_MODEL_PROVIDER", "linear").lower(),
            "training_data": "public synthetic cohort (fallback: no trained PD artifact found)",
            "explainability": "exact linear Shapley contributions on a synthetic score proxy",
            "fallback": f"Expected artifact at {ARTIFACT_PATH}; run backend/model_training/train_pd_model.py",
        }
    model = LogisticModel.load(ARTIFACT_PATH)
    with ARTIFACT_PATH.open("r", encoding="utf-8") as handle:
        artifact_meta = json.load(handle)
    status = {
        "active_provider": "logistic_pd_v1",
        "requested_provider": os.getenv("UDYAMPULSE_MODEL_PROVIDER", "linear").lower(),
        "training_data": f"UCI public credit-default dataset (proxy; see model_training/dataset_manifest.json), sha256={artifact_meta.get('dataset_sha256', '?')[:12]}...",
        "trained_at_utc": artifact_meta.get("trained_at_utc"),
        "features": UNIVERSAL_FEATURES,
        "explainability": "exact logit-space Shapley contributions + first-order probability-scale approximation",
        "fallback": None,
    }
    return model, status


_pd_model, _runtime_status = _load_pd_model()

# Kept only as the deterministic score-explanation fallback if no PD artifact
# is committed; never the default when artifact.json exists (see above).
_linear_model = LinearModel()
_rows, _targets = generate_training_set()
_linear_model.fit(_rows, _targets)

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


def model_evaluation() -> dict | None:
    """Held-out OOT evaluation metrics for the active PD artifact, or None if
    no artifact has been trained yet. Same numbers /model/evaluation serves."""
    if not EVALUATION_PATH.exists():
        return None
    with EVALUATION_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _pd_explain(pillars: dict[str, int]) -> dict:
    assert _pd_model is not None
    universal = msme_pillars_to_universal(pillars)
    pd_probability = _pd_model.predict_proba(universal)
    logit_contributions = _pd_model.shap_contributions_logit(universal)
    baseline_probability = _pd_model.baseline_probability

    # First-order (delta-method) linearization of the sigmoid at the baseline
    # to express logit-space contributions in approximate probability points.
    # Exact only at the baseline point; noted explicitly in the response.
    slope = baseline_probability * (1 - baseline_probability)
    approx_probability_points = {
        name: round(value * slope * 100, 2) for name, value in logit_contributions.items()
    }

    ranked = sorted(logit_contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top_reasons = [
        f"{'+' if approx_probability_points[name] <= 0 else ''}{-approx_probability_points[name]:.1f} pts "
        f"of default risk from {name}"
        for name, _ in ranked
    ]

    predicted_score = round((1 - pd_probability) * 100, 1)
    baseline_score = round((1 - baseline_probability) * 100, 1)

    return {
        "predicted_score": predicted_score,
        "baseline_score": baseline_score,
        "pd_estimate": round(pd_probability, 4),
        "pd_baseline": round(baseline_probability, 4),
        "shap_contributions_logit": {k: round(v, 4) for k, v in logit_contributions.items()},
        "shap_contributions_approx_probability_points": approx_probability_points,
        "top_reasons": top_reasons,
        "provider": _runtime_status["active_provider"],
        "shap_sum_check_logit": round(
            sum(logit_contributions.values()) - (_pd_model.predict_logit(universal) - _pd_model.baseline_logit), 6
        ),
    }


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


def explain(p: MSMEProfile, pillars: dict[str, int]) -> dict:
    if _gbm_bundle is not None:
        return _gbm_explain(_to_features(p))
    if _pd_model is not None:
        return _pd_explain(pillars)
    return _linear_explain(_to_features(p))


_try_build_gbm()
