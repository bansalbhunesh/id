"""Rebuild the UdyamPulse champion/challenger PD evidence.

The public proxy dataset is cross-sectional, so this pipeline deliberately
uses the honest names development/calibration/holdout. It does not call the
last split out-of-time. A genuine OOT window requires dated IDBI sandbox
outcomes and remains an explicit gap in evaluation.json.

Two models are fitted on the same three universal risk concepts:

* dependency-free calibrated logistic regression (transparent fallback)
* XGBoost challenger with native exact TreeSHAP contributions

The calibration split is used for Platt scaling, model selection and the
PD review threshold. The untouched holdout is opened once for final evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(HERE))

from metrics import (  # noqa: E402
    brier_score,
    calibration_bins,
    confusion_at_threshold,
    expected_calibration_error,
    ks_statistic,
    log_loss,
    pr_auc,
    psi,
    roc_auc,
)
from pd_model import LogisticModel, fit_platt_scaler  # noqa: E402
from uci_feature_bridge import UNIVERSAL_FEATURES, uci_row_to_universal  # noqa: E402
from xgb_pd_model import XGBoostPDModel  # noqa: E402

DATA_DIR = HERE / "data"
ARTIFACT_DIR = HERE / "artifacts"
LOGISTIC_PATH = ARTIFACT_DIR / "artifact.json"
XGB_MODEL_PATH = ARTIFACT_DIR / "xgboost_model.json"
XGB_METADATA_PATH = ARTIFACT_DIR / "xgboost_metadata.json"
CHAMPION_PATH = ARTIFACT_DIR / "champion.json"
EVALUATION_PATH = ARTIFACT_DIR / "evaluation.json"
SPLIT_SEED = 42
SPLIT_RATIOS = {"development": 0.70, "calibration": 0.15, "holdout": 0.15}
BOOTSTRAP_REPLICATES = 200


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    """Write committed JSON with stable bytes across operating systems."""
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_manifest() -> dict:
    with (HERE / "dataset_manifest.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fetch_dataset(manifest: dict) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    target = DATA_DIR / "default_of_credit_card_clients.xls"
    if not target.exists():
        print(f"Downloading {manifest['source_url']} ...")
        urllib.request.urlretrieve(manifest["source_url"], target)
    actual_hash = _sha256(target)
    if actual_hash != manifest["sha256"]:
        raise SystemExit(
            f"Dataset integrity check failed: expected {manifest['sha256']}, got {actual_hash}"
        )
    return target


def load_rows(path: Path, manifest: dict) -> tuple[list[dict], list[int], list[dict]]:
    import pandas as pd

    frame = pd.read_excel(path, header=1)
    label_col = manifest["outcome_label_column"]
    pay_cols = [c for c in frame.columns if c.startswith("PAY_") and not c.startswith("PAY_AMT")]
    bill_cols = [c for c in frame.columns if c.startswith("BILL_AMT")]
    rows: list[dict] = []
    targets: list[int] = []
    slices: list[dict] = []
    for _, record in frame.iterrows():
        item = record.to_dict()
        rows.append(
            uci_row_to_universal(
                item, pay_cols=pay_cols, bill_cols=bill_cols, limit_col="LIMIT_BAL"
            )
        )
        targets.append(int(item[label_col]))
        age = int(item["AGE"])
        age_band = "<30" if age < 30 else "30-44" if age < 45 else "45-59" if age < 60 else "60+"
        slices.append(
            {
                "gender": "female" if int(item["SEX"]) == 2 else "male",
                "age_band": age_band,
            }
        )
    return rows, targets, slices


def stratified_split(targets: list[int], seed: int) -> dict[str, list[int]]:
    rng = random.Random(seed)
    by_class = {0: [], 1: []}
    for index, target in enumerate(targets):
        by_class[target].append(index)
    splits = {name: [] for name in SPLIT_RATIOS}
    for indices in by_class.values():
        rng.shuffle(indices)
        n = len(indices)
        development_end = round(SPLIT_RATIOS["development"] * n)
        calibration_end = round(
            (SPLIT_RATIOS["development"] + SPLIT_RATIOS["calibration"]) * n
        )
        splits["development"].extend(indices[:development_end])
        splits["calibration"].extend(indices[development_end:calibration_end])
        splits["holdout"].extend(indices[calibration_end:])
    for indices in splits.values():
        rng.shuffle(indices)
    return splits


def subset(values: list, indices: list[int]) -> list:
    return [values[index] for index in indices]


def evaluate(targets: list[int], probabilities: list[float], threshold: float) -> dict:
    auc = roc_auc(targets, probabilities)
    base_rate = sum(targets) / len(targets)
    return {
        "n": len(targets),
        "default_rate": round(base_rate, 4),
        "auc": round(auc, 4),
        "gini": round(2 * auc - 1, 4),
        "ks": round(ks_statistic(targets, probabilities), 4),
        "pr_auc": round(pr_auc(targets, probabilities), 4),
        "brier_score": round(brier_score(targets, probabilities), 4),
        "null_brier_score": round(base_rate * (1 - base_rate), 4),
        "brier_skill_pct": round(
            (1 - brier_score(targets, probabilities) / (base_rate * (1 - base_rate))) * 100,
            2,
        ),
        "log_loss": round(log_loss(targets, probabilities), 4),
        "expected_calibration_error": round(
            expected_calibration_error(targets, probabilities), 4
        ),
        "confusion_matrix": confusion_at_threshold(targets, probabilities, threshold),
        "calibration_bins": calibration_bins(targets, probabilities),
    }


def choose_threshold(targets: list[int], probabilities: list[float]) -> tuple[float, dict]:
    candidates = sorted(set(round(value, 3) for value in probabilities))
    eligible = []
    for threshold in candidates:
        matrix = confusion_at_threshold(targets, probabilities, threshold)
        if matrix["recall_capture_rate"] >= 0.60:
            eligible.append((matrix["false_positive_rate"], -threshold, threshold, matrix))
    if not eligible:
        threshold = 0.30
        return threshold, confusion_at_threshold(targets, probabilities, threshold)
    _fpr, _negative_threshold, threshold, matrix = min(eligible)
    return threshold, matrix


def bootstrap_intervals(targets: list[int], probabilities: list[float]) -> dict:
    rng = random.Random(SPLIT_SEED + 100)
    by_class = {
        0: [i for i, target in enumerate(targets) if target == 0],
        1: [i for i, target in enumerate(targets) if target == 1],
    }
    samples = {"auc": [], "ks": [], "pr_auc": [], "brier_score": []}
    for _ in range(BOOTSTRAP_REPLICATES):
        indices = []
        for class_indices in by_class.values():
            indices.extend(rng.choices(class_indices, k=len(class_indices)))
        rng.shuffle(indices)
        sample_targets = subset(targets, indices)
        sample_probabilities = subset(probabilities, indices)
        samples["auc"].append(roc_auc(sample_targets, sample_probabilities))
        samples["ks"].append(ks_statistic(sample_targets, sample_probabilities))
        samples["pr_auc"].append(pr_auc(sample_targets, sample_probabilities))
        samples["brier_score"].append(brier_score(sample_targets, sample_probabilities))

    intervals = {}
    for name, values in samples.items():
        ordered = sorted(values)
        intervals[name] = {
            "lower_95": round(ordered[int(0.025 * len(ordered))], 4),
            "upper_95": round(ordered[int(0.975 * len(ordered)) - 1], 4),
            "replicates": BOOTSTRAP_REPLICATES,
        }
    return intervals


def fairness_slices(
    targets: list[int], probabilities: list[float], attributes: list[dict], threshold: float
) -> dict:
    output = {
        "note": "Protected attributes are excluded from model inputs and used only for post-model outcome monitoring on the public proxy holdout.",
        "dimensions": {},
    }
    for dimension in ("gender", "age_band"):
        groups = sorted({item[dimension] for item in attributes})
        rows = []
        for group in groups:
            indices = [i for i, item in enumerate(attributes) if item[dimension] == group]
            group_targets = subset(targets, indices)
            group_probabilities = subset(probabilities, indices)
            matrix = confusion_at_threshold(group_targets, group_probabilities, threshold)
            rows.append(
                {
                    "group": group,
                    "n": len(indices),
                    "observed_default_rate": round(sum(group_targets) / len(group_targets), 4),
                    "average_predicted_pd": round(sum(group_probabilities) / len(group_probabilities), 4),
                    "auc": round(roc_auc(group_targets, group_probabilities), 4),
                    "brier_score": round(brier_score(group_targets, group_probabilities), 4),
                    "recall_capture_rate": matrix["recall_capture_rate"],
                    "false_positive_rate": matrix["false_positive_rate"],
                }
            )
        output["dimensions"][dimension] = {
            "groups": rows,
            "max_auc_gap": round(max(row["auc"] for row in rows) - min(row["auc"] for row in rows), 4),
            "max_recall_gap": round(
                max(row["recall_capture_rate"] for row in rows)
                - min(row["recall_capture_rate"] for row in rows),
                4,
            ),
            "max_false_positive_rate_gap": round(
                max(row["false_positive_rate"] for row in rows)
                - min(row["false_positive_rate"] for row in rows),
                4,
            ),
        }
    return output


def train_logistic(
    development_rows: list[dict],
    development_targets: list[int],
    calibration_rows: list[dict],
    calibration_targets: list[int],
) -> LogisticModel:
    model = LogisticModel(UNIVERSAL_FEATURES)
    model.fit(development_rows, development_targets)
    model.calibrate(calibration_rows, calibration_targets)
    return model


def train_xgboost(
    development_rows: list[dict],
    development_targets: list[int],
    calibration_rows: list[dict],
    calibration_targets: list[int],
) -> tuple[XGBoostPDModel, dict]:
    import xgboost as xgb

    def matrix(rows: list[dict], labels: list[int] | None = None):
        return xgb.DMatrix(
            [[row[name] for name in UNIVERSAL_FEATURES] for row in rows],
            label=labels,
            feature_names=UNIVERSAL_FEATURES,
        )

    booster = xgb.train(
        {
            "objective": "binary:logistic",
            "eval_metric": ["auc", "logloss"],
            "max_depth": 3,
            "eta": 0.04,
            "min_child_weight": 20,
            "subsample": 0.9,
            "colsample_bytree": 1.0,
            "lambda": 2.0,
            "alpha": 0.2,
            "seed": SPLIT_SEED,
            "nthread": 1,
            "tree_method": "hist",
            "monotone_constraints": "(-1,-1,-1)",
        },
        matrix(development_rows, development_targets),
        num_boost_round=220,
        verbose_eval=False,
    )
    ARTIFACT_DIR.mkdir(exist_ok=True)
    booster.save_model(XGB_MODEL_PATH)
    calibration_margins = [
        float(value)
        for value in booster.predict(matrix(calibration_rows), output_margin=True)
    ]
    slope, intercept = fit_platt_scaler(calibration_margins, calibration_targets)
    metadata = {
        "model_type": "xgboost_pd_proxy_v1",
        "feature_names": UNIVERSAL_FEATURES,
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "tree_count": 220,
        "monotone_constraints": {
            "discipline": -1,
            "leverage": -1,
            "liquidity": -1,
        },
        "tree_shap": "native pred_contribs, exact in calibrated logit space",
    }
    _write_json(XGB_METADATA_PATH, metadata)
    return XGBoostPDModel.load(XGB_MODEL_PATH, XGB_METADATA_PATH), metadata


def probabilities(model, rows: list[dict]) -> list[float]:
    return [model.predict_proba(row) for row in rows]


def select_champion(candidate_metrics: dict) -> tuple[str, str]:
    logistic = candidate_metrics["logistic_pd_v2"]["calibration"]
    xgboost = candidate_metrics["xgboost_pd_proxy_v1"]["calibration"]
    if xgboost["auc"] > logistic["auc"] + 0.005:
        return "xgboost_pd_proxy_v1", "XGBoost exceeded logistic calibration AUC by more than the 0.005 materiality guardrail."
    if logistic["brier_score"] <= xgboost["brier_score"]:
        return "logistic_pd_v2", "AUC difference was immaterial; calibrated logistic won the simplicity/Brier tie-break."
    return "xgboost_pd_proxy_v1", "AUC difference was immaterial; XGBoost won the calibration Brier tie-break."


def main() -> None:
    manifest = load_manifest()
    dataset_path = fetch_dataset(manifest)
    rows, targets, protected_attributes = load_rows(dataset_path, manifest)
    splits = stratified_split(targets, SPLIT_SEED)
    split_rows = {name: subset(rows, indices) for name, indices in splits.items()}
    split_targets = {name: subset(targets, indices) for name, indices in splits.items()}
    split_attributes = {
        name: subset(protected_attributes, indices) for name, indices in splits.items()
    }

    logistic = train_logistic(
        split_rows["development"],
        split_targets["development"],
        split_rows["calibration"],
        split_targets["calibration"],
    )
    xgboost_model, xgboost_metadata = train_xgboost(
        split_rows["development"],
        split_targets["development"],
        split_rows["calibration"],
        split_targets["calibration"],
    )
    models = {
        "logistic_pd_v2": logistic,
        "xgboost_pd_proxy_v1": xgboost_model,
    }

    candidate_metrics = {}
    for provider, model in models.items():
        candidate_metrics[provider] = {}
        for split_name in ("calibration", "holdout"):
            candidate_metrics[provider][split_name] = evaluate(
                split_targets[split_name],
                probabilities(model, split_rows[split_name]),
                0.30,
            )

    champion_provider, selection_reason = select_champion(candidate_metrics)
    champion = models[champion_provider]
    calibration_probabilities = probabilities(champion, split_rows["calibration"])
    policy_threshold, threshold_matrix = choose_threshold(
        split_targets["calibration"], calibration_probabilities
    )

    champion_splits = {}
    champion_probabilities = {}
    for split_name in SPLIT_RATIOS:
        champion_probabilities[split_name] = probabilities(
            champion, split_rows[split_name]
        )
        champion_splits[split_name] = evaluate(
            split_targets[split_name],
            champion_probabilities[split_name],
            policy_threshold,
        )

    trained_at = datetime.now(timezone.utc).isoformat()
    logistic_artifact = logistic.to_dict()
    logistic_artifact.update(
        {
            "model_type": "logistic_pd_v2",
            "trained_at_utc": trained_at,
            "dataset_sha256": manifest["sha256"],
        }
    )
    ARTIFACT_DIR.mkdir(exist_ok=True)
    _write_json(LOGISTIC_PATH, logistic_artifact)
    xgboost_metadata.update(
        {
            "trained_at_utc": trained_at,
            "dataset_sha256": manifest["sha256"],
        }
    )
    _write_json(XGB_METADATA_PATH, xgboost_metadata)

    champion_manifest = {
        "provider": champion_provider,
        "fallback_provider": "logistic_pd_v2",
        "feature_names": UNIVERSAL_FEATURES,
        "policy_review_threshold": round(policy_threshold, 4),
        "trained_at_utc": trained_at,
        "dataset_sha256": manifest["sha256"],
        "selection_split": "calibration",
        "selection_reason": selection_reason,
        "artifacts": {
            "logistic": LOGISTIC_PATH.name,
            "xgboost_model": XGB_MODEL_PATH.name,
            "xgboost_metadata": XGB_METADATA_PATH.name,
        },
    }
    _write_json(CHAMPION_PATH, champion_manifest)

    holdout_targets = split_targets["holdout"]
    holdout_probabilities = champion_probabilities["holdout"]
    evaluation = {
        "model_type": champion_provider,
        "champion_provider": champion_provider,
        "universal_features": UNIVERSAL_FEATURES,
        "split_seed": SPLIT_SEED,
        "split_ratios": SPLIT_RATIOS,
        "validation_design": (
            "Stratified random development/calibration/holdout on a cross-sectional public proxy dataset. "
            "The holdout is untouched during fitting, calibration, threshold selection and champion selection; "
            "it is not an out-of-time sample."
        ),
        "trained_at_utc": trained_at,
        "dataset": {
            "name": manifest["name"],
            "sha256": manifest["sha256"],
            "rows": len(rows),
            "domain": "Taiwan consumer credit-card accounts; public proxy, not Indian MSME/IDBI data",
        },
        "model_selection": {
            "selected_on": "calibration split only",
            "selection_reason": selection_reason,
            "candidates": candidate_metrics,
        },
        "policy_threshold": {
            "pd_review_threshold": round(policy_threshold, 4),
            "selected_on": "calibration split",
            "objective": "Highest threshold retaining at least 60% bad capture; routes to human review, never automatic decline.",
            "calibration_confusion": threshold_matrix,
        },
        "splits": champion_splits,
        "holdout_confidence_intervals": bootstrap_intervals(
            holdout_targets, holdout_probabilities
        ),
        "drift": {
            "psi_development_vs_holdout": round(
                psi(
                    champion_probabilities["development"],
                    holdout_probabilities,
                ),
                4,
            ),
            "thresholds": {
                "stable": "< 0.10",
                "watch": "0.10-0.25",
                "drift": "> 0.25",
            },
            "note": "PSI on champion predicted-PD distributions; random holdout stability, not temporal drift evidence.",
        },
        "fairness": fairness_slices(
            holdout_targets,
            holdout_probabilities,
            split_attributes["holdout"],
            policy_threshold,
        ),
        "artifacts": {
            "champion_manifest_sha256": _sha256(CHAMPION_PATH),
            "logistic_sha256": _sha256(LOGISTIC_PATH),
            "xgboost_model_sha256": _sha256(XGB_MODEL_PATH),
            "xgboost_metadata_sha256": _sha256(XGB_METADATA_PATH),
        },
        "disclosed_gaps": {
            "out_of_time_validation": (
                "Not available in the cross-sectional UCI source. A genuine dated OOT window remains mandatory "
                "once IDBI sandbox repayment outcomes arrive; this report does not relabel a random holdout as OOT."
            ),
            "ntc_ntb_slice_validation": (
                "Not available: every UCI row already has a credit file. NTC/NTB performance requires labelled IDBI outcomes."
            ),
            "sector_geography_vintage": (
                "Unavailable in this proxy dataset. Live synthetic cohort monitors remain illustrative only."
            ),
            "domain_transfer": (
                "The universal feature bridge is an engineering proof, not evidence that consumer-credit relationships transfer to Indian MSMEs."
            ),
        },
    }
    _write_json(EVALUATION_PATH, evaluation)

    holdout = evaluation["splits"]["holdout"]
    print(
        f"Champion={champion_provider} holdout AUC={holdout['auc']} KS={holdout['ks']} "
        f"PR-AUC={holdout['pr_auc']} Brier={holdout['brier_score']} threshold={policy_threshold:.3f}"
    )
    if holdout["auc"] < 0.65:
        raise SystemExit("Holdout AUC is below 0.65; refusing to ship the artifact")


if __name__ == "__main__":
    main()
