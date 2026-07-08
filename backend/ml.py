"""ML explainability layer: trains a linear PD-proxy model once at import
time and exposes SHAP-equivalent, per-feature reason codes for a profile.

See linear_model.py for why this needs no numpy/scikit-learn/shap install.
"""
from linear_model import FEATURE_NAMES, LinearModel
from scoring import MSMEProfile
from synthetic_training import generate_training_set

_model = LinearModel()
_rows, _targets = generate_training_set()
_model.fit(_rows, _targets)


def _to_features(p: MSMEProfile) -> dict[str, float]:
    return {name: getattr(p, name) for name in FEATURE_NAMES}


def explain(p: MSMEProfile) -> dict:
    features = _to_features(p)
    predicted = _model.predict(features)
    contributions = _model.shap_contributions(features)

    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top_reasons = [
        f"{'+' if value >= 0 else ''}{value:.1f} pts from {name.replace('_', ' ')}"
        for name, value in ranked[:4]
    ]

    return {
        "predicted_score": round(max(0.0, min(100.0, predicted)), 1),
        "baseline_score": round(_model.baseline_prediction, 1),
        "shap_contributions": {k: round(v, 2) for k, v in contributions.items()},
        "top_reasons": top_reasons,
    }
