"""Train sba_sme_pd_v2 -- the experiment-selected successor benchmark.

Everything here is the product of the registry-tracked experiment programme
(backend/model_training/experiments/):
- data: real SBA 7(a) FOIA loan-level records, temporal protocol
  (FY2010-16 train/cal/holdout, FY2017-19 true OOT, FY2005-07 stress)
- recipe: selective monotonicity (E3/E3b: term freed because real term-risk is
  non-monotone at the short end; every economically-defensible constraint
  kept), capacity from the calibration-split sweep (E4), identity calibration
  (E5: large-sample hist-XGBoost with logistic loss was already the tied-best
  calibrated option in-distribution, and identity preserves exact TreeSHAP
  additivity through the runtime wrapper)
- complexity gate (anti-Shroff): the 5-seed bag (E6) replaces the single model
  only if DeLong p < 0.05 AND delta AUC >= 0.003 on OOT -- pre-registered
  before results were known
- the served artifact IS the protocol-trained model, so committed metrics are
  exactly the metrics of the artifact being served (no refit drift)

Run:  python backend/model_training/train_sme_pd_model_v2.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "experiments"))
sys.path.insert(0, str(HERE.parent))

from experiments.dataset import FEATURE_NAMES, FEATURES, temporal_protocol  # noqa: E402
from experiments.exp_lib import (  # noqa: E402
    bootstrap_metric,
    delong_test,
    metric_bundle,
    predict_logistic,
    predict_xgb,
    roc_auc,
    train_logistic,
    train_xgb,
)

ARTIFACT_DIR = HERE / "artifacts"
V2_MODEL_PATH = ARTIFACT_DIR / "sba_v2_model.json"
V2_METADATA_PATH = ARTIFACT_DIR / "sba_v2_metadata.json"
V2_EVALUATION_PATH = ARTIFACT_DIR / "sme_evaluation_v2.json"
REGISTRY_PATH = HERE / "experiments" / "registry.json"
SEED = 42
MATERIALITY_AUC = 0.003

MONO_SELECTIVE = {name: (0 if name == "term_months" else c) for name, c in FEATURES.items()}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _registry() -> list:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8")) if REGISTRY_PATH.exists() else []


def _latest(registry: list, exp_id: str) -> dict | None:
    for entry in reversed(registry):
        if entry.get("id") == exp_id:
            return entry
    return None


def main() -> None:
    registry = _registry()
    e4 = _latest(registry, "E4")
    params = {"max_depth": 7, "eta": 0.05, "min_child_weight": 20, "subsample": 0.9,
              "colsample_bytree": 0.9, "lambda": 2.0, "alpha": 0.1, "seed": SEED}
    rounds = 400
    if e4:
        selected = dict(e4["results"]["selected"])
        rounds = selected.pop("rounds")
        params = selected

    data = temporal_protocol(SEED)
    train, cal, hold, oot, stress = (data[n] for n in ("train", "calibration", "holdout", "oot", "stress"))

    mono = tuple(MONO_SELECTIVE[name] for name in FEATURE_NAMES)
    booster = train_xgb(train["X"], train["y"], FEATURE_NAMES,
                        params=params, rounds=rounds, monotone=mono)

    def predict(split):
        return predict_xgb(booster, split["X"], FEATURE_NAMES)

    p = {name: predict(data[name]) for name in ("holdout", "oot", "stress")}

    # Baselines for the comparison table (same protocol, same features).
    logistic = train_logistic(train["X"], train["y"])
    p_logistic_oot = predict_logistic(logistic, oot["X"])
    v1_style = train_xgb(train["X"], train["y"], FEATURE_NAMES,
                         params={"max_depth": 3, "eta": 0.05, "min_child_weight": 10,
                                 "subsample": 0.9, "lambda": 2.0, "alpha": 0.1, "seed": SEED},
                         rounds=220, monotone=tuple(FEATURES.values()))
    p_v1_style_oot = predict_xgb(v1_style, oot["X"], FEATURE_NAMES)

    # Pre-registered complexity gate for the 5-seed bag (E6).
    e6 = _latest(registry, "E6")
    bag_gate = {"applied": False, "reason": "E6 not available"}
    if e6 and "delong_vs_single_oot" in e6["results"]:
        dl = e6["results"]["delong_vs_single_oot"]
        material = abs(dl.get("delta") or 0) >= MATERIALITY_AUC
        significant = bool(dl.get("significant_5pct"))
        bag_gate = {"applied": False, "delong": dl, "materiality_threshold": MATERIALITY_AUC,
                    "reason": ("bag not significantly and materially better; shipping the single model"
                               if not (significant and material and (dl.get("delta") or 0) > 0)
                               else "bag passed the gate but is not shipped in this build; recorded as open challenger")}

    ARTIFACT_DIR.mkdir(exist_ok=True)
    booster.save_model(V2_MODEL_PATH)
    gains = booster.get_score(importance_type="gain")
    metadata = {
        "model_type": "sba_sme_pd_v2",
        "feature_names": FEATURE_NAMES,
        # Identity calibration: preserves exact TreeSHAP additivity in logit
        # space through the standard runtime wrapper; E5 showed the raw model
        # was already tied-best calibrated in-distribution.
        "calibration_slope": 1.0,
        "calibration_intercept": 0.0,
        "tree_count": rounds,
        "monotone_constraints": MONO_SELECTIVE,
        "gain_importance": {k: round(v, 4) for k, v in gains.items()},
        "tree_shap": "native pred_contribs, exact in logit space (identity calibration)",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    V2_METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")

    from xgb_pd_model import XGBoostPDModel

    served = XGBoostPDModel.load(V2_MODEL_PATH, V2_METADATA_PATH)
    sample = {name: float(oot["X"][0][i]) for i, name in enumerate(FEATURE_NAMES)}
    contribs = served.shap_contributions_logit(sample)
    reconstruction = abs(sum(contribs.values()) + served.shap_baseline_logit(sample)
                         - served.predict_logit(sample))

    # Stability probe (corrects E14's first pass, which perturbed binary flags
    # off-manifold): +/-5% relative noise on continuous inputs only.
    continuous = [i for i, name in enumerate(FEATURE_NAMES)
                  if name in ("term_months", "gross_approval_log", "guarantee_portion",
                              "jobs_supported_log")]
    rng = np.random.default_rng(SEED)
    X_probe = hold["X"][:20000].copy()
    noise = np.ones_like(X_probe)
    noise[:, continuous] = (1 + rng.uniform(-0.05, 0.05, (len(X_probe), len(continuous)))).astype(np.float32)
    base_pd = predict_xgb(booster, X_probe, FEATURE_NAMES)
    perturbed_pd = predict_xgb(booster, X_probe * noise, FEATURE_NAMES)
    perturbation = {
        "mean_abs_pd_delta": round(float(np.mean(np.abs(perturbed_pd - base_pd))), 5),
        "p95_abs_pd_delta": round(float(np.percentile(np.abs(perturbed_pd - base_pd), 95)), 5),
        "note": "+/-5% relative noise on continuous inputs only; binary flags excluded (off-manifold)",
    }

    evaluation = {
        "model_type": "sba_sme_pd_v2",
        "champion_provider": "sba_sme_pd_v2",
        "evidence_type": "real_loan_level_temporal_benchmark",
        "features": FEATURE_NAMES,
        "monotone_constraints": MONO_SELECTIVE,
        "selective_monotonicity_rationale": (
            "E3/E3b: blanket constraints cost 5.2pp OOT AUC because real SBA term-risk is "
            "non-monotone at the short end; freeing term while keeping every defensible "
            "constraint beat the unconstrained model out-of-time (DeLong z=-8.6) and under stress."),
        "params": {**params, "rounds": rounds},
        "seed": SEED,
        "dataset": {
            "name": "SBA 7(a) FOIA loan-level records (official U.S. SBA, public domain)",
            "protocol": "FY2010-16 train/calibration/holdout; FY2017-19 true out-of-time; FY2005-07 recession stress",
            "train_rows": int(train["y"].shape[0]),
            "holdout_rows": int(hold["y"].shape[0]),
            "oot_rows": int(oot["y"].shape[0]),
            "stress_rows": int(stress["y"].shape[0]),
            "base_rates": {"train": round(float(train["y"].mean()), 4),
                           "oot": round(float(oot["y"].mean()), 4),
                           "stress": round(float(stress["y"].mean()), 4)},
            "manifest": "backend/model_training/experiments/foia_manifest.json",
        },
        "splits": {
            "holdout": metric_bundle(hold["y"], p["holdout"]),
            "oot": metric_bundle(oot["y"], p["oot"]),
            "stress": metric_bundle(stress["y"], p["stress"]),
        },
        "confidence_intervals": {
            "holdout_auc": bootstrap_metric(hold["y"], p["holdout"], roc_auc),
            "oot_auc": bootstrap_metric(oot["y"], p["oot"], roc_auc),
        },
        "baseline_comparison_oot": {
            "logistic_same_features": {"auc": round(roc_auc(oot["y"], p_logistic_oot), 4),
                                       "delong_vs_v2": delong_test(oot["y"], p["oot"], p_logistic_oot)},
            "v1_recipe_blanket_monotone": {"auc": round(roc_auc(oot["y"], p_v1_style_oot), 4),
                                           "delong_vs_v2": delong_test(oot["y"], p["oot"], p_v1_style_oot)},
        },
        "bag_complexity_gate": bag_gate,
        "calibration_note": (
            "Identity calibration shipped: E5 found the raw large-sample model tied-best on ECE "
            "in-distribution (0.0019 holdout) and that OOT calibration error (~0.03) is base-rate "
            "drift no static calibrator fixes; operational recalibration remains the product answer."),
        "explainability": {
            "method": "native exact TreeSHAP in logit space",
            "served_reconstruction_error_logit": float(f"{reconstruction:.3e}"),
            "gain_importance": metadata["gain_importance"],
        },
        "stability": {
            "seed_std_auc": "4e-05 across 5 seeds (registry E14)",
            "perturbation_continuous": perturbation,
        },
        "experiment_registry": "backend/model_training/experiments/registry.json",
        "cross_references": {
            "reject_inference": "E10", "survival_12m_pd": "E16", "adversarial_shift": "E7",
            "domain_adaptation": "E8", "geographic_ood": "E13", "stability": "E14",
            "regional_fairness": "E15", "ablation": "E2", "calibration": "E5",
        },
        "trained_at_utc": metadata["trained_at_utc"],
        "artifacts": {
            "sba_v2_model_sha256": _sha256(V2_MODEL_PATH),
            "sba_v2_metadata_sha256": _sha256(V2_METADATA_PATH),
        },
        "honesty_boundary": {
            "real_outcomes": "Yes -- 418k resolved real SBA loans with real charge-offs; natural base rates (7-9%), not a balanced research sample.",
            "temporal": "OOT is genuinely later-in-time (FY2017-19) than every fitted row (FY2010-16).",
            "censoring": "Resolved-only labelling right-censors slow outcomes in late vintages; the discrete-time hazard experiment (E16) models this explicitly.",
            "domain": "US small business is a proxy for Indian MSME; this is methodology evidence, not an IDBI calibration.",
            "v1_baseline": "The v1 case-sample benchmark (sme_evaluation.json) remains committed for like-for-like comparison.",
        },
    }
    V2_EVALUATION_PATH.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8", newline="\n")

    h, o, s = (evaluation["splits"][n] for n in ("holdout", "oot", "stress"))
    print(f"sba_sme_pd_v2: holdout AUC={h['auc']} KS={h['ks']} | OOT AUC={o['auc']} KS={o['ks']} "
          f"Brier={o['brier']} | stress AUC={s['auc']}")
    print(f"  OOT 30% approval: {o['operating_points']['approve_30pct']}")
    print(f"  served TreeSHAP reconstruction error: {reconstruction:.2e}")
    if o["auc"] < 0.90:
        raise SystemExit("OOT AUC below 0.90; refusing to ship v2")


if __name__ == "__main__":
    main()
