"""Champion/challenger PD inference and exact model attribution.

The committed champion manifest is produced by
``model_training/train_pd_model.py``. The preferred provider is calibrated
XGBoost with native TreeSHAP in logit space. A calibrated dependency-free
logistic artifact remains the deterministic fallback if XGBoost cannot load;
the old synthetic score regression is only a last-resort missing-artifact
fallback and is never presented as default-risk evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

from feature_bridge import UNIVERSAL_FEATURES, msme_pillars_to_universal
from linear_model import FEATURE_NAMES, LinearModel
from pd_model import LogisticModel
from scoring import MSMEProfile
from synthetic_training import generate_training_set

ARTIFACT_DIR = Path(__file__).parent / "model_training" / "artifacts"
LOGISTIC_PATH = ARTIFACT_DIR / "artifact.json"
XGB_MODEL_PATH = ARTIFACT_DIR / "xgboost_model.json"
XGB_METADATA_PATH = ARTIFACT_DIR / "xgboost_metadata.json"
CHAMPION_PATH = ARTIFACT_DIR / "champion.json"
EVALUATION_PATH = ARTIFACT_DIR / "evaluation.json"


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_champion():
    if not LOGISTIC_PATH.exists():
        return None, {
            "active_provider": "linear_synthetic_fallback",
            "champion_provider": None,
            "training_data": "public synthetic score proxy; no PD artifact found",
            "explainability": "exact linear Shapley contributions on a synthetic score target",
            "fallback": f"Run {Path('backend/model_training/train_pd_model.py')}",
            "policy_review_threshold": None,
        }

    champion = _read_json(CHAMPION_PATH) if CHAMPION_PATH.exists() else {
        "provider": "logistic_pd_v2",
        "policy_review_threshold": 0.30,
    }
    fallback_reason = None
    model = None
    active_provider = champion["provider"]
    if champion["provider"] == "xgboost_pd_proxy_v1":
        try:
            from xgb_pd_model import XGBoostPDModel

            model = XGBoostPDModel.load(XGB_MODEL_PATH, XGB_METADATA_PATH)
        except (ImportError, OSError, ValueError) as exc:
            fallback_reason = (
                f"Champion XGBoost unavailable ({exc.__class__.__name__}); "
                "serving calibrated logistic fallback."
            )
            active_provider = "logistic_pd_v2_fallback"

    if model is None:
        model = LogisticModel.load(LOGISTIC_PATH)
        if champion["provider"] != "xgboost_pd_proxy_v1":
            active_provider = "logistic_pd_v2"

    evaluation = _read_json(EVALUATION_PATH) if EVALUATION_PATH.exists() else {}
    dataset = evaluation.get("dataset", {})
    status = {
        "active_provider": active_provider,
        "champion_provider": champion.get("provider"),
        "fallback_provider": champion.get("fallback_provider", "logistic_pd_v2"),
        "training_data": (
            f"{dataset.get('name', 'public credit-default proxy')} "
            f"({dataset.get('rows', '?')} rows; not IDBI/MSME data)"
        ),
        "trained_at_utc": champion.get("trained_at_utc"),
        "features": UNIVERSAL_FEATURES,
        "policy_review_threshold": champion.get("policy_review_threshold", 0.30),
        "validation_design": evaluation.get("validation_design"),
        "explainability": (
            "native exact TreeSHAP in calibrated logit space"
            if active_provider == "xgboost_pd_proxy_v1"
            else "exact calibrated linear Shapley contributions in logit space"
        ),
        "fallback": fallback_reason,
    }
    return model, status


_pd_model, _runtime_status = _load_champion()

# Missing-artifact fallback only. It keeps the app available but is explicitly
# labelled synthetic and is not used when the committed PD artifacts exist.
_linear_model = LinearModel()
_rows, _targets = generate_training_set()
_linear_model.fit(_rows, _targets)


def model_status() -> dict:
    return dict(_runtime_status)


def pd_policy_threshold() -> float | None:
    value = _runtime_status.get("policy_review_threshold")
    return float(value) if value is not None else None


def model_evaluation() -> dict | None:
    if not EVALUATION_PATH.exists():
        return None
    return _read_json(EVALUATION_PATH)


def _pd_explain(pillars: dict[str, int]) -> dict:
    assert _pd_model is not None
    universal = msme_pillars_to_universal(pillars)
    pd_probability = _pd_model.predict_proba(universal)
    logit_contributions = _pd_model.shap_contributions_logit(universal)
    baseline_probability = _pd_model.baseline_probability
    baseline_logit = _pd_model.baseline_logit

    # Delta-method display values aid underwriter intuition. The exact audit
    # invariant remains the logit-space reconstruction directly below.
    probability_slope = baseline_probability * (1 - baseline_probability)
    approx_probability_points = {
        name: round(value * probability_slope * 100, 2)
        for name, value in logit_contributions.items()
    }
    ranked = sorted(logit_contributions.items(), key=lambda item: abs(item[1]), reverse=True)
    top_reasons = [
        f"{'+' if approx_probability_points[name] >= 0 else ''}{approx_probability_points[name]:.1f} "
        f"approx. PD pts from {name}"
        for name, _value in ranked
    ]

    predicted_logit = _pd_model.predict_logit(universal)
    return {
        "predicted_score": round((1 - pd_probability) * 100, 1),
        "baseline_score": round((1 - baseline_probability) * 100, 1),
        "pd_estimate": round(pd_probability, 4),
        "pd_baseline": round(baseline_probability, 4),
        "pd_review_threshold": pd_policy_threshold(),
        "shap_contributions_logit": {
            name: round(value, 4) for name, value in logit_contributions.items()
        },
        "shap_contributions_approx_probability_points": approx_probability_points,
        "probability_points_note": (
            "First-order display approximation at the baseline; exact additivity is in logit space."
        ),
        "top_reasons": top_reasons,
        "provider": _runtime_status["active_provider"],
        "champion_provider": _runtime_status.get("champion_provider"),
        "shap_sum_check_logit": round(
            sum(logit_contributions.values()) - (predicted_logit - baseline_logit),
            6,
        ),
    }


def _linear_explain(profile: MSMEProfile) -> dict:
    features = {name: getattr(profile, name) for name in FEATURE_NAMES}
    predicted = _linear_model.predict(features)
    contributions = _linear_model.shap_contributions(features)
    baseline = _linear_model.baseline_prediction
    return {
        "predicted_score": round(max(0.0, min(100.0, predicted)), 1),
        "baseline_score": round(max(0.0, min(100.0, baseline)), 1),
        "top_reasons": [
            f"{'+' if value >= 0 else ''}{value:.1f} score pts from {name.replace('_', ' ')}"
            for name, value in sorted(
                contributions.items(), key=lambda item: abs(item[1]), reverse=True
            )[:4]
        ],
        "provider": "linear_synthetic_fallback",
        "shap_contributions": {
            name: round(value, 2) for name, value in contributions.items()
        },
        "shap_sum_check": round(
            sum(contributions.values()) - (predicted - baseline), 6
        ),
    }


def explain(profile: MSMEProfile, pillars: dict[str, int]) -> dict:
    if _pd_model is not None:
        return _pd_explain(pillars)
    return _linear_explain(profile)
