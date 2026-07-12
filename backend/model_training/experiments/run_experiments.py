"""Registry-driven experiment runner for the sba_sme_pd_v2 research programme.

Every run appends a reproducible record (config, seed, data hashes, git rev,
metrics, or the failure reason) to registry.json. Families map to the E-numbers
documented in docs/research/RESEARCH_NOTES.md.

Usage:
    python backend/model_training/experiments/run_experiments.py            # first wave
    python backend/model_training/experiments/run_experiments.py --families E1,E3,E5
    python backend/model_training/experiments/run_experiments.py --quick    # subsampled
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from dataset import FEATURE_NAMES, FEATURES, MANIFEST, MONOTONE, temporal_protocol  # noqa: E402
from exp_lib import (  # noqa: E402
    Isotonic,
    adversarial_validation,
    apply_platt,
    bootstrap_metric,
    delong_test,
    fit_platt,
    metric_bundle,
    perturbation_sensitivity,
    predict_logistic,
    predict_xgb,
    roc_auc,
    seed_stability,
    train_logistic,
    train_xgb,
)

REGISTRY_PATH = HERE / "registry.json"
SEED = 42
SWEEP_SUBSAMPLE = 120_000

# E3/E3b finding: term-risk is non-monotone at the short end in real SBA data.
# Selective monotonicity (term freed, every economically-defensible constraint
# kept) beat both blanket constraints (+5.2pp OOT AUC) and the unconstrained
# model (DeLong z=-8.6 OOT) -- so the champion candidate uses it.
MONO_SELECTIVE = tuple(0 if name == "term_months" else c for name, c in FEATURES.items())

V1_STYLE_PARAMS = {"max_depth": 3, "eta": 0.05, "min_child_weight": 10, "subsample": 0.9,
                   "lambda": 2.0, "alpha": 0.1, "seed": SEED}


def git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def record(registry: list, entry: dict) -> None:
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    entry.setdefault("git", git_rev())
    registry.append(entry)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=1) + "\n", encoding="utf-8")
    status = entry.get("failure") or (
        f"holdout={entry['results'].get('holdout', {}).get('auc')} "
        f"oot={entry['results'].get('oot', {}).get('auc')}"
        if "results" in entry else "ok")
    print(f"[{entry['id']}] {entry['name']}: {status}")


def eval_on(splits: dict, predict) -> dict:
    return {name: metric_bundle(splits[name]["y"], predict(splits[name]["X"]))
            for name in ("holdout", "oot", "stress")}


def subsample(split: dict, n: int, seed: int = SEED) -> dict:
    if split["y"].shape[0] <= n:
        return split
    rng = np.random.default_rng(seed)
    idx = rng.choice(split["y"].shape[0], n, replace=False)
    return {key: value[idx] for key, value in split.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--families", default="E1,E2,E3,E4,E5,E6,E7,E8,E9,E13,E14,E15")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    families = {f.strip() for f in args.families.split(",")}

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8")) if REGISTRY_PATH.exists() else []
    t0 = time.time()
    data = temporal_protocol(SEED)
    if args.quick:
        data = {name: subsample(split, 60_000) for name, split in data.items()}
    train, cal, hold = data["train"], data["calibration"], data["holdout"]
    print(f"protocol: train={train['y'].shape[0]:,} cal={cal['y'].shape[0]:,} "
          f"holdout={hold['y'].shape[0]:,} oot={data['oot']['y'].shape[0]:,} "
          f"stress={data['stress']['y'].shape[0]:,}  (load {time.time()-t0:.0f}s)")
    common_data = {"train_file": MANIFEST["files"][1]["sha256"][:12],
                   "stress_file": MANIFEST["files"][0]["sha256"][:12],
                   "protocol": "FY2010-16 train/cal/holdout, FY2017-19 OOT, FY2005-07 stress",
                   "quick": args.quick}

    # ---------------------------------------------------------------- E1 ----
    predictions = {}  # name -> dict(split -> PD array) for DeLong reuse
    if "E1" in families:
        logistic = train_logistic(train["X"], train["y"])
        raw_cal = np.log(np.clip(predict_logistic(logistic, cal["X"]), 1e-9, 1) /
                         np.clip(1 - predict_logistic(logistic, cal["X"]), 1e-9, 1))
        slope, intercept = fit_platt(raw_cal, cal["y"])
        def predict_e1a(X):
            p = predict_logistic(logistic, X)
            return apply_platt(np.log(np.clip(p, 1e-9, 1) / np.clip(1 - p, 1e-9, 1)), slope, intercept)
        predictions["logistic"] = {n: predict_e1a(data[n]["X"]) for n in ("holdout", "oot", "stress")}
        record(registry, {"id": "E1a", "family": "E1", "name": "logistic baseline (Platt)",
                          "seed": SEED, "config": {"features": FEATURE_NAMES}, "data": common_data,
                          "results": eval_on(data, predict_e1a)})

        booster = train_xgb(train["X"], train["y"], FEATURE_NAMES,
                            params=V1_STYLE_PARAMS, rounds=220, monotone=MONOTONE)
        m_cal = predict_xgb(booster, cal["X"], FEATURE_NAMES, margin=True)
        s2, i2 = fit_platt(m_cal, cal["y"])
        def predict_e1b(X):
            return apply_platt(predict_xgb(booster, X, FEATURE_NAMES, margin=True), s2, i2)
        predictions["v1_style_monotone"] = {n: predict_e1b(data[n]["X"]) for n in ("holdout", "oot", "stress")}
        record(registry, {"id": "E1b", "family": "E1", "name": "v1-recipe monotone XGB (Platt)",
                          "seed": SEED, "config": {"params": V1_STYLE_PARAMS, "rounds": 220,
                                                   "monotone": dict(FEATURES)}, "data": common_data,
                          "results": eval_on(data, predict_e1b)})

    # ---------------------------------------------------------------- E4 ----
    best_params, best_auc = dict(V1_STYLE_PARAMS), -1.0
    if "E4" in families:
        sweep_train = subsample(train, SWEEP_SUBSAMPLE)
        grid = []
        for depth in (3, 5, 7):
            for eta, rounds in ((0.05, 400), (0.10, 250)):
                params = {"max_depth": depth, "eta": eta, "min_child_weight": 20,
                          "subsample": 0.9, "colsample_bytree": 0.9, "lambda": 2.0,
                          "alpha": 0.1, "seed": SEED}
                booster = train_xgb(sweep_train["X"], sweep_train["y"], FEATURE_NAMES,
                                    params=params, rounds=rounds, monotone=MONOTONE)
                auc_cal = roc_auc(cal["y"], predict_xgb(booster, cal["X"], FEATURE_NAMES))
                grid.append({"depth": depth, "eta": eta, "rounds": rounds,
                             "calibration_auc": round(float(auc_cal), 4)})
                if auc_cal > best_auc:
                    best_auc, best_params, best_rounds = auc_cal, params, rounds
        record(registry, {"id": "E4", "family": "E4", "name": "capacity sweep (calibration-split selection)",
                          "seed": SEED, "config": {"subsample": SWEEP_SUBSAMPLE},
                          "data": common_data,
                          "results": {"grid": grid, "selected": {**best_params, "rounds": best_rounds},
                                      "note": "selected on calibration split only; holdout/OOT untouched"}})
    else:
        best_rounds = 220

    # tuned monotone champion candidate, used by E3/E5/E6/E8/E9/E13/E14/E15
    tuned = train_xgb(train["X"], train["y"], FEATURE_NAMES,
                      params=best_params, rounds=best_rounds, monotone=MONO_SELECTIVE)
    tuned_margin_cal = predict_xgb(tuned, cal["X"], FEATURE_NAMES, margin=True)
    ts, ti = fit_platt(tuned_margin_cal, cal["y"])
    def predict_tuned(X):
        return apply_platt(predict_xgb(tuned, X, FEATURE_NAMES, margin=True), ts, ti)
    predictions["tuned_monotone"] = {n: predict_tuned(data[n]["X"]) for n in ("holdout", "oot", "stress")}
    if "E4" in families:
        record(registry, {"id": "E4b", "family": "E4", "name": "tuned monotone XGB (full train, Platt)",
                          "seed": SEED, "config": {"params": best_params, "rounds": best_rounds},
                          "data": common_data, "results": eval_on(data, predict_tuned)})

    # ---------------------------------------------------------------- E3 ----
    if "E3" in families:
        free = train_xgb(train["X"], train["y"], FEATURE_NAMES,
                         params=best_params, rounds=best_rounds, monotone=None)
        fs, fi = fit_platt(predict_xgb(free, cal["X"], FEATURE_NAMES, margin=True), cal["y"])
        def predict_free(X):
            return apply_platt(predict_xgb(free, X, FEATURE_NAMES, margin=True), fs, fi)
        predictions["tuned_free"] = {n: predict_free(data[n]["X"]) for n in ("holdout", "oot", "stress")}
        results = eval_on(data, predict_free)
        results["delong_vs_monotone"] = {
            n: delong_test(data[n]["y"], predictions["tuned_free"][n], predictions["tuned_monotone"][n])
            for n in ("holdout", "oot")}
        record(registry, {"id": "E3", "family": "E3", "name": "unconstrained vs monotone (DeLong-gated)",
                          "seed": SEED, "config": {"params": best_params}, "data": common_data,
                          "results": results})

    # ---------------------------------------------------------------- E2 ----
    if "E2" in families:
        groups = {
            "structure_only": [n for n in FEATURE_NAMES if not n.startswith(("sector_", "is_", "has_"))],
            "no_sector": [n for n in FEATURE_NAMES if not n.startswith("sector_")],
            "full": FEATURE_NAMES,
        }
        ladder = {}
        for gname, names in groups.items():
            cols = [FEATURE_NAMES.index(n) for n in names]
            mono = tuple(FEATURES[n] for n in names)
            b = train_xgb(train["X"][:, cols], train["y"], names,
                          params=best_params, rounds=best_rounds, monotone=mono)
            gs, gi = fit_platt(predict_xgb(b, cal["X"][:, cols], names, margin=True), cal["y"])
            p_hold = apply_platt(predict_xgb(b, hold["X"][:, cols], names, margin=True), gs, gi)
            p_oot = apply_platt(predict_xgb(b, data["oot"]["X"][:, cols], names, margin=True), gs, gi)
            ladder[gname] = {"n_features": len(names),
                             "holdout_auc": round(roc_auc(hold["y"], p_hold), 4),
                             "oot_auc": round(roc_auc(data["oot"]["y"], p_oot), 4)}
            if gname != "full":
                ladder[gname]["delong_vs_full_oot"] = delong_test(
                    data["oot"]["y"], predictions["tuned_monotone"]["oot"], p_oot)
        # sensitivity: + lender-priced interest rate (flagged, never in default set)
        Xr_train = np.column_stack([train["X"], train["rate"]])
        Xr_cal = np.column_stack([cal["X"], cal["rate"]])
        names_r = FEATURE_NAMES + ["initial_interest_rate"]
        br = train_xgb(Xr_train, train["y"], names_r, params=best_params,
                       rounds=best_rounds, monotone=MONOTONE + (1,))
        rs, ri = fit_platt(predict_xgb(br, Xr_cal, names_r, margin=True), cal["y"])
        p_oot_r = apply_platt(predict_xgb(br, np.column_stack([data["oot"]["X"], data["oot"]["rate"]]),
                                          names_r, margin=True), rs, ri)
        ladder["plus_interest_rate_sensitivity"] = {
            "oot_auc": round(roc_auc(data["oot"]["y"], p_oot_r), 4),
            "note": "lender-priced signal; reported for sensitivity only, excluded from candidate models"}
        record(registry, {"id": "E2", "family": "E2", "name": "feature ablation ladder",
                          "seed": SEED, "config": {}, "data": common_data, "results": {"ladder": ladder}})

    # ---------------------------------------------------------------- E5 ----
    if "E5" in families:
        margins = {n: predict_xgb(tuned, data[n]["X"], FEATURE_NAMES, margin=True)
                   for n in ("holdout", "oot")}
        raw = {n: 1.0 / (1.0 + np.exp(-margins[n])) for n in margins}
        iso = Isotonic().fit(tuned_margin_cal, cal["y"])
        comp = {}
        for method, probs in {
            "uncalibrated": raw,
            "platt": {n: apply_platt(margins[n], ts, ti) for n in margins},
            "isotonic": {n: iso.predict(margins[n]) for n in margins},
        }.items():
            comp[method] = {n: {"brier": round(float(np.mean((probs[n] - data[n]['y'])**2)), 4),
                                "ece": metric_bundle(data[n]["y"], probs[n])["ece"],
                                "auc": round(roc_auc(data[n]["y"], probs[n]), 4)}
                            for n in ("holdout", "oot")}
        record(registry, {"id": "E5", "family": "E5", "name": "calibration: none vs Platt vs isotonic",
                          "seed": SEED, "config": {}, "data": common_data, "results": comp})

    # ---------------------------------------------------------------- E6 ----
    if "E6" in families:
        seed_margins_cal, seed_margins = [], {n: [] for n in ("holdout", "oot", "stress")}
        for seed in range(5):
            b = train_xgb(train["X"], train["y"], FEATURE_NAMES,
                          params={**best_params, "seed": seed}, rounds=best_rounds, monotone=MONO_SELECTIVE)
            seed_margins_cal.append(predict_xgb(b, cal["X"], FEATURE_NAMES, margin=True))
            for n in seed_margins:
                seed_margins[n].append(predict_xgb(b, data[n]["X"], FEATURE_NAMES, margin=True))
        bag_cal = np.mean(seed_margins_cal, axis=0)
        bs, bi = fit_platt(bag_cal, cal["y"])
        bag_pd = {n: apply_platt(np.mean(seed_margins[n], axis=0), bs, bi) for n in seed_margins}
        results = {n: metric_bundle(data[n]["y"], bag_pd[n]) for n in ("holdout", "oot", "stress")}
        results["delong_vs_single_oot"] = delong_test(
            data["oot"]["y"], bag_pd["oot"], predictions["tuned_monotone"]["oot"])
        results["anti_shroff_gate"] = (
            "accept ensemble only if significantly better than the single tuned model")
        record(registry, {"id": "E6", "family": "E6", "name": "5-seed bagged monotone XGB",
                          "seed": SEED, "config": {"bag": 5}, "data": common_data, "results": results})
        predictions["bagged"] = bag_pd

    # ---------------------------------------------------------------- E7 ----
    if "E7" in families:
        adv_oot = adversarial_validation(train["X"], data["oot"]["X"], FEATURE_NAMES, seed=SEED)
        adv_stress = adversarial_validation(train["X"], data["stress"]["X"], FEATURE_NAMES, seed=SEED)
        record(registry, {"id": "E7", "family": "E7", "name": "adversarial validation (shift meters)",
                          "seed": SEED, "config": {}, "data": common_data,
                          "results": {"train_vs_oot": {k: v for k, v in adv_oot.items() if k != "importance_weights"},
                                      "train_vs_stress": {k: v for k, v in adv_stress.items() if k != "importance_weights"}}})
        oot_weights = adv_oot["importance_weights"]
    else:
        oot_weights = None

    # ---------------------------------------------------------------- E8 ----
    if "E8" in families and oot_weights is not None:
        import xgboost as xgb
        matrix = xgb.DMatrix(train["X"], label=train["y"], weight=oot_weights,
                             feature_names=FEATURE_NAMES)
        config = {"objective": "binary:logistic", "eval_metric": ["auc"],
                  "tree_method": "hist", "nthread": 4, **best_params}
        config["monotone_constraints"] = "(" + ",".join(str(c) for c in MONO_SELECTIVE) + ")"
        bw = xgb.train(config, matrix, num_boost_round=best_rounds, verbose_eval=False)
        ws, wi = fit_platt(predict_xgb(bw, cal["X"], FEATURE_NAMES, margin=True), cal["y"])
        def predict_weighted(X):
            return apply_platt(predict_xgb(bw, X, FEATURE_NAMES, margin=True), ws, wi)
        results = eval_on(data, predict_weighted)
        results["delong_vs_tuned_oot"] = delong_test(
            data["oot"]["y"], predict_weighted(data["oot"]["X"]), predictions["tuned_monotone"]["oot"])
        record(registry, {"id": "E8", "family": "E8", "name": "importance-weighted domain adaptation",
                          "seed": SEED, "config": {"weights": "clipped density ratio from E7"},
                          "data": common_data, "results": results})

    # ---------------------------------------------------------------- E9 ----
    if "E9" in families:
        p_oot = predictions["tuned_monotone"]["oot"]
        record(registry, {"id": "E9", "family": "E9", "name": "bootstrap uncertainty (tuned champion)",
                          "seed": SEED, "config": {"replicates": 200}, "data": common_data,
                          "results": {"oot_auc_ci": bootstrap_metric(data["oot"]["y"], p_oot, roc_auc),
                                      "holdout_auc_ci": bootstrap_metric(hold["y"], predictions["tuned_monotone"]["holdout"], roc_auc)}})

    # --------------------------------------------------------------- E13 ----
    if "E13" in families:
        west_train_mask = train["region"] != 0
        west_eval_mask = data["oot"]["region"] == 0
        b = train_xgb(train["X"][west_train_mask], train["y"][west_train_mask], FEATURE_NAMES,
                      params=best_params, rounds=best_rounds, monotone=MONO_SELECTIVE)
        gs2, gi2 = fit_platt(predict_xgb(b, cal["X"], FEATURE_NAMES, margin=True), cal["y"])
        p_west = apply_platt(predict_xgb(b, data["oot"]["X"][west_eval_mask], FEATURE_NAMES, margin=True), gs2, gi2)
        record(registry, {"id": "E13", "family": "E13", "name": "geographic OOD (train ex-West, test West OOT)",
                          "seed": SEED, "config": {}, "data": common_data,
                          "results": {"west_oot": metric_bundle(data["oot"]["y"][west_eval_mask], p_west),
                                      "full_oot_reference_auc": round(roc_auc(data["oot"]["y"], predictions["tuned_monotone"]["oot"]), 4)}})

    # --------------------------------------------------------------- E14 ----
    if "E14" in families:
        sub = subsample(train, SWEEP_SUBSAMPLE, seed=7)
        stability = seed_stability(
            lambda seed: train_xgb(sub["X"], sub["y"], FEATURE_NAMES,
                                   params={**best_params, "seed": seed}, rounds=min(best_rounds, 250),
                                   monotone=MONO_SELECTIVE),
            lambda model: predict_xgb(model, hold["X"], FEATURE_NAMES),
            hold["y"])
        sensitivity = perturbation_sensitivity(predict_tuned, hold["X"][:20000])
        record(registry, {"id": "E14", "family": "E14", "name": "stability: seeds + input perturbation",
                          "seed": SEED, "config": {"train_subsample": SWEEP_SUBSAMPLE},
                          "data": common_data,
                          "results": {"seed_stability": stability, "perturbation": sensitivity}})

    # --------------------------------------------------------------- E15 ----
    if "E15" in families:
        p_oot = predictions["tuned_monotone"]["oot"]
        y_oot = data["oot"]["y"]
        regions = {0: "west", 1: "south", 2: "midwest", 3: "northeast_other"}
        approve_threshold = np.quantile(p_oot, 0.30)
        rows = {}
        for code, name in regions.items():
            mask = data["oot"]["region"] == code
            if mask.sum() < 500:
                continue
            approved = p_oot[mask] <= approve_threshold
            goods = y_oot[mask] == 0
            rows[name] = {"n": int(mask.sum()),
                          "auc": round(roc_auc(y_oot[mask], p_oot[mask]), 4),
                          "approval_rate": round(float(approved.mean()), 4),
                          "good_approval_rate": round(float(approved[goods].mean()), 4),
                          "bad_rate_in_book": round(float(y_oot[mask][approved].mean()), 4)}
        aucs = [r["auc"] for r in rows.values()]
        gars = [r["good_approval_rate"] for r in rows.values()]
        record(registry, {"id": "E15", "family": "E15", "name": "regional fairness monitoring (OOT, 30% approval)",
                          "seed": SEED, "config": {"note": "region is monitoring-only, never a model input"},
                          "data": common_data,
                          "results": {"regions": rows,
                                      "max_auc_gap": round(max(aucs) - min(aucs), 4),
                                      "max_good_approval_gap": round(max(gars) - min(gars), 4)}})

    print(f"total {time.time()-t0:.0f}s; registry entries: {len(registry)}")


if __name__ == "__main__":
    main()
