"""Wave-2 experiments: reject inference (E10) and discrete-time survival (E16).

E10 — the survivorship-bias experiment competitors describe but never measure:
simulate a legacy approval policy, train approved-only vs fuzzy-parcelling
(Feelders 2000; Hand & Henley 1997), then evaluate BOTH on the full labelled
population (possible here because the simulation hides labels the ground truth
still knows). Reports the bias a bank would actually suffer and how much the
correction recovers, especially on the historically-rejected segment (the
new-to-credit analog).

E16 — discrete-time hazard model on annual person-periods. Produces
horizon-specific PDs; the 12-month hazard aligns exactly with the dated
`bad_12m` outcome contract the product already exposes for the IDBI sandbox
(`GET /sandbox/outcome-contract`), which a lifetime binary label cannot do.

Usage: python backend/model_training/experiments/wave2.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from dataset import FEATURE_NAMES, MONOTONE, temporal_protocol  # noqa: E402
from exp_lib import (  # noqa: E402
    apply_platt,
    delong_test,
    fit_platt,
    metric_bundle,
    predict_logistic,
    predict_xgb,
    roc_auc,
    train_logistic,
    train_xgb,
)

REGISTRY_PATH = HERE / "registry.json"
SEED = 42


def _params() -> tuple[dict, int]:
    """Use the E4-selected capacity if the registry has it, else v1-style."""
    if REGISTRY_PATH.exists():
        for entry in reversed(json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))):
            if entry.get("id") == "E4":
                sel = dict(entry["results"]["selected"])
                rounds = sel.pop("rounds")
                return sel, rounds
    return ({"max_depth": 3, "eta": 0.05, "min_child_weight": 10, "subsample": 0.9,
             "lambda": 2.0, "alpha": 0.1, "seed": SEED}, 220)


def record(entry: dict) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8")) if REGISTRY_PATH.exists() else []
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        entry.setdefault("git", subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                               capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        entry.setdefault("git", "unknown")
    registry.append(entry)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=1) + "\n", encoding="utf-8")
    print(f"[{entry['id']}] {entry['name']}: recorded")


def experiment_e10(data: dict, params: dict, rounds: int) -> None:
    train, cal = data["train"], data["calibration"]

    # 1. Legacy policy: a deliberately conservative logistic scorecard fit on a
    #    small early sample -- the "old credit officer".
    rng = np.random.default_rng(SEED)
    legacy_idx = rng.choice(len(train["y"]), 20_000, replace=False)
    legacy = train_logistic(train["X"][legacy_idx], train["y"][legacy_idx])
    legacy_pd = predict_logistic(legacy, train["X"])
    approve_cut = np.quantile(legacy_pd, 0.60)  # legacy bank approves 60%
    approved = legacy_pd <= approve_cut
    rejected = ~approved

    # 2. Approved-only model (the survivorship-biased bank model).
    b_appr = train_xgb(train["X"][approved], train["y"][approved], FEATURE_NAMES,
                       params=params, rounds=rounds, monotone=MONOTONE)
    s1, i1 = fit_platt(predict_xgb(b_appr, cal["X"], FEATURE_NAMES, margin=True), cal["y"])

    def pd_appr(X):
        return apply_platt(predict_xgb(b_appr, X, FEATURE_NAMES, margin=True), s1, i1)

    # 3. Fuzzy parcelling: rejects enter twice with weights (1-PD) good / PD bad.
    import xgboost as xgb

    current = b_appr
    for _iteration in range(2):
        reject_pd = pd_appr(train["X"][rejected]) if current is b_appr else apply_platt(
            predict_xgb(current, train["X"][rejected], FEATURE_NAMES, margin=True), s1, i1)
        X_aug = np.vstack([train["X"][approved],
                           train["X"][rejected], train["X"][rejected]])
        y_aug = np.concatenate([train["y"][approved],
                                np.zeros(rejected.sum()), np.ones(rejected.sum())])
        w_aug = np.concatenate([np.ones(int(approved.sum())),
                                1.0 - reject_pd, reject_pd])
        matrix = xgb.DMatrix(X_aug, label=y_aug, weight=w_aug, feature_names=FEATURE_NAMES)
        config = {"objective": "binary:logistic", "eval_metric": ["auc"],
                  "tree_method": "hist", "nthread": 4, **params,
                  "monotone_constraints": "(" + ",".join(str(c) for c in MONOTONE) + ")"}
        current = xgb.train(config, matrix, num_boost_round=rounds, verbose_eval=False)
    s2, i2 = fit_platt(predict_xgb(current, cal["X"], FEATURE_NAMES, margin=True), cal["y"])

    def pd_fuzzy(X):
        return apply_platt(predict_xgb(current, X, FEATURE_NAMES, margin=True), s2, i2)

    # 4. Truth: evaluate both on the FULL population (holdout + OOT), and on
    #    the historically-rejected segment specifically.
    results = {}
    for split_name in ("holdout", "oot"):
        split = data[split_name]
        p_a, p_f = pd_appr(split["X"]), pd_fuzzy(split["X"])
        legacy_split = predict_logistic(legacy, split["X"]) > approve_cut  # would-be rejects
        results[split_name] = {
            "approved_only_auc_full_population": round(roc_auc(split["y"], p_a), 4),
            "fuzzy_parcelling_auc_full_population": round(roc_auc(split["y"], p_f), 4),
            "delong_fuzzy_vs_approved_only": delong_test(split["y"], p_f, p_a),
            "rejected_segment": {
                "n": int(legacy_split.sum()),
                "default_rate": round(float(split["y"][legacy_split].mean()), 4),
                "approved_only_auc": round(roc_auc(split["y"][legacy_split], p_a[legacy_split]), 4),
                "fuzzy_parcelling_auc": round(roc_auc(split["y"][legacy_split], p_f[legacy_split]), 4),
            },
        }
    record({"id": "E10", "family": "E10", "name": "reject inference: approved-only vs fuzzy parcelling",
            "seed": SEED,
            "config": {"legacy_policy": "logistic on 20k early sample, approves 60%",
                       "iterations": 2, "params": params, "rounds": rounds},
            "data": {"protocol": "FY2010-16 train, FY2017-19 OOT"},
            "results": results})


def experiment_e16(data: dict, params: dict, rounds: int) -> None:
    train, cal, oot = data["train"], data["calibration"], data["oot"]
    horizon_years = 7

    def person_periods(split):
        X, event, months = split["X"], split["event"], split["months_to_event"]
        years = np.minimum(np.ceil(months / 12.0).astype(int), horizon_years)
        rows, labels = [], []
        for year in range(1, horizon_years + 1):
            alive = years >= year
            if not alive.any():
                continue
            X_year = np.column_stack([X[alive], np.full(alive.sum(), year, dtype=np.float32)])
            y_year = ((years[alive] == year) & (event[alive] == 1)).astype(np.float32)
            rows.append(X_year)
            labels.append(y_year)
        return np.vstack(rows), np.concatenate(labels)

    names = FEATURE_NAMES + ["period_year"]
    mono = MONOTONE + (0,)
    X_pp, y_pp = person_periods(train)
    hazard = train_xgb(X_pp, y_pp, names, params={**params, "max_depth": min(params.get("max_depth", 3), 5)},
                       rounds=rounds, monotone=mono)
    X_cal_pp, y_cal_pp = person_periods(cal)
    hs, hi = fit_platt(predict_xgb(hazard, X_cal_pp, names, margin=True), y_cal_pp)

    def horizon_pd(split, upto_years: int):
        X = split["X"]
        survival = np.ones(len(X))
        for year in range(1, upto_years + 1):
            X_year = np.column_stack([X, np.full(len(X), year, dtype=np.float32)])
            h = apply_platt(predict_xgb(hazard, X_year, names, margin=True), hs, hi)
            survival *= (1.0 - h)
        return 1.0 - survival

    pd_12m = horizon_pd(oot, 1)
    pd_36m = horizon_pd(oot, 3)
    # 12m ground truth on OOT: charged off within 12 months of approval.
    y_12m = ((oot["event"] == 1) & (oot["months_to_event"] <= 12)).astype(int)
    y_36m = ((oot["event"] == 1) & (oot["months_to_event"] <= 36)).astype(int)
    record({"id": "E16", "family": "E16", "name": "discrete-time hazard (annual person-periods)",
            "seed": SEED,
            "config": {"horizon_years": horizon_years, "person_period_rows": int(len(y_pp)),
                       "params": params, "rounds": rounds},
            "data": {"protocol": "FY2010-16 train, FY2017-19 OOT"},
            "results": {
                "oot_12m": {"n": int(len(y_12m)), "event_rate": round(float(y_12m.mean()), 4),
                            **{k: metric_bundle(y_12m, pd_12m)[k] for k in ("auc", "ks", "brier", "ece")},
                            "mean_predicted_pd": round(float(pd_12m.mean()), 4)},
                "oot_36m": {"n": int(len(y_36m)), "event_rate": round(float(y_36m.mean()), 4),
                            **{k: metric_bundle(y_36m, pd_36m)[k] for k in ("auc", "ks", "brier", "ece")},
                            "mean_predicted_pd": round(float(pd_36m.mean()), 4)},
                "why_it_matters": (
                    "Horizon-specific PDs align with the product's dated bad_12m outcome "
                    "contract; a lifetime binary label cannot produce a 12-month PD."),
            }})


def main() -> None:
    t0 = time.time()
    params, rounds = _params()
    data = temporal_protocol(SEED)
    experiment_e10(data, params, rounds)
    experiment_e16(data, params, rounds)
    print(f"wave2 done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
