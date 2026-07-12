"""Shared experiment machinery: vectorised metrics, DeLong significance,
PAVA isotonic calibration, adversarial validation, operating-point analysis,
bootstrap intervals, and stability probes.

Numpy-only (plus xgboost for the boosted models) so the experiment suite runs
in the repo's dependency-light environment. Every function is deterministic
under a supplied seed.
"""
from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------- metrics ---

def roc_auc(y: np.ndarray, p: np.ndarray) -> float:
    """Rank-based AUC (ties handled via midranks)."""
    y = np.asarray(y, dtype=np.float64)
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    sorted_p = p[order]
    # midranks
    i = 0
    n = len(p)
    while i < n:
        j = i
        while j + 1 < n and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    n_pos = float(y.sum())
    n_neg = float(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def ks_statistic(y: np.ndarray, p: np.ndarray) -> float:
    order = np.argsort(p, kind="mergesort")
    y_sorted = np.asarray(y)[order]
    cum_pos = np.cumsum(y_sorted) / max(1, y_sorted.sum())
    cum_neg = np.cumsum(1 - y_sorted) / max(1, (1 - y_sorted).sum())
    return float(np.max(np.abs(cum_pos - cum_neg)))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    total = len(p)
    err = 0.0
    for b in range(bins):
        mask = idx == b
        if not mask.any():
            continue
        err += (mask.sum() / total) * abs(np.mean(np.asarray(y)[mask]) - np.mean(np.asarray(p)[mask]))
    return float(err)


def pr_auc(y: np.ndarray, p: np.ndarray) -> float:
    order = np.argsort(-np.asarray(p), kind="mergesort")
    y_sorted = np.asarray(y)[order]
    tp = np.cumsum(y_sorted)
    precision = tp / (np.arange(len(y_sorted)) + 1)
    recall = tp / max(1, y_sorted.sum())
    # step-wise integration over recall
    d_recall = np.diff(np.concatenate([[0.0], recall]))
    return float(np.sum(precision * d_recall))


def operating_points(y: np.ndarray, p: np.ndarray, approval_rates=(0.2, 0.3, 0.4, 0.5)) -> dict:
    """Approve the lowest-PD fraction q; report book quality at each q."""
    y = np.asarray(y)
    order = np.argsort(p, kind="mergesort")  # ascending risk
    n = len(y)
    total_bad = max(1, int(y.sum()))
    base_rate = float(y.mean())
    out = {}
    for q in approval_rates:
        k = max(1, int(round(q * n)))
        approved = y[order[:k]]
        bad_in_book = float(approved.mean())
        out[f"approve_{int(q*100)}pct"] = {
            "bad_rate_in_approved_book": round(bad_in_book, 4),
            "vs_population_bad_rate": round(base_rate, 4),
            "book_cleanliness_multiple": round(base_rate / bad_in_book, 2) if bad_in_book > 0 else None,
            "defaults_kept_out_pct": round(100 * (1 - approved.sum() / total_bad), 2),
        }
    return out


def band_bad_rates(y: np.ndarray, p: np.ndarray, bands: int = 5) -> dict:
    """Quantile risk bands (A=lowest PD). Monotone bad rates = usable scorecard."""
    order = np.argsort(p, kind="mergesort")
    chunks = np.array_split(np.asarray(y)[order], bands)
    rates = [round(float(chunk.mean()), 4) for chunk in chunks]
    labels = [chr(ord("A") + i) for i in range(bands)]
    return {
        "bands": dict(zip(labels, rates)),
        "monotone": bool(all(rates[i] <= rates[i + 1] + 1e-12 for i in range(len(rates) - 1))),
    }


def metric_bundle(y: np.ndarray, p: np.ndarray) -> dict:
    return {
        "n": int(len(y)),
        "default_rate": round(float(np.mean(y)), 4),
        "auc": round(roc_auc(y, p), 4),
        "gini": round(2 * roc_auc(y, p) - 1, 4),
        "ks": round(ks_statistic(y, p), 4),
        "pr_auc": round(pr_auc(y, p), 4),
        "brier": round(brier(y, p), 4),
        "ece": round(ece(y, p), 4),
        "operating_points": operating_points(y, p),
        "risk_bands": band_bad_rates(y, p),
    }

# ----------------------------------------------------------------- DeLong ---

def _midrank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    sorted_x = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sorted_x[j + 1] == sorted_x[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return ranks


def delong_test(y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray) -> dict:
    """DeLong, DeLong & Clarke-Pearson (1988) paired AUC-difference test."""
    from math import erf, sqrt

    y = np.asarray(y)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    m, n = len(pos), len(neg)
    thetas, v01, v10 = [], [], []
    for p in (np.asarray(p_a, dtype=np.float64), np.asarray(p_b, dtype=np.float64)):
        all_rank = _midrank(np.concatenate([p[pos], p[neg]]))
        pos_rank = _midrank(p[pos])
        neg_rank = _midrank(p[neg])
        auc = (all_rank[:m].sum() - m * (m + 1) / 2) / (m * n)
        thetas.append(auc)
        v01.append((all_rank[:m] - pos_rank) / n)          # structural components (positives)
        v10.append(1.0 - (all_rank[m:] - neg_rank) / m)    # structural components (negatives)
    s01 = np.cov(np.vstack(v01))
    s10 = np.cov(np.vstack(v10))
    var = (s01[0, 0] + s01[1, 1] - 2 * s01[0, 1]) / m + (s10[0, 0] + s10[1, 1] - 2 * s10[0, 1]) / n
    delta = thetas[0] - thetas[1]
    if var <= 0:
        return {"auc_a": thetas[0], "auc_b": thetas[1], "delta": delta, "z": None, "p_value": 1.0}
    z = delta / sqrt(var)
    p_value = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    return {
        "auc_a": round(float(thetas[0]), 4),
        "auc_b": round(float(thetas[1]), 4),
        "delta": round(float(delta), 4),
        "z": round(float(z), 3),
        "p_value": float(f"{p_value:.2e}"),
        "significant_5pct": bool(p_value < 0.05),
    }

# ------------------------------------------------------------- calibration --

def fit_platt(scores: np.ndarray, y: np.ndarray, iterations: int = 400, lr: float = 0.1) -> tuple[float, float]:
    s = (np.asarray(scores, dtype=np.float64) - scores.mean()) / (scores.std() or 1.0)
    slope, intercept = 0.0, float(np.log(max(y.mean(), 1e-6) / max(1 - y.mean(), 1e-6)))
    for _ in range(iterations):
        z = intercept + slope * s
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))
        err = p - y
        slope -= lr * float(err @ s / len(y))
        intercept -= lr * float(err.mean())
    return slope / (scores.std() or 1.0), intercept - slope * scores.mean() / (scores.std() or 1.0)


def apply_platt(scores: np.ndarray, slope: float, intercept: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(intercept + slope * np.asarray(scores), -35, 35)))


class Isotonic:
    """Pool-Adjacent-Violators isotonic regression (our own implementation)."""

    def __init__(self) -> None:
        self.x_: np.ndarray | None = None
        self.y_: np.ndarray | None = None

    def fit(self, scores: np.ndarray, y: np.ndarray) -> "Isotonic":
        order = np.argsort(scores, kind="mergesort")
        x = np.asarray(scores, dtype=np.float64)[order]
        target = np.asarray(y, dtype=np.float64)[order]
        # PAVA with block weights
        values = list(target)
        weights = [1.0] * len(values)
        starts = list(range(len(values)))
        i = 0
        merged_values, merged_weights, merged_starts = [], [], []
        for i in range(len(values)):
            merged_values.append(values[i])
            merged_weights.append(weights[i])
            merged_starts.append(starts[i])
            while len(merged_values) > 1 and merged_values[-2] > merged_values[-1]:
                v2, w2 = merged_values.pop(), merged_weights.pop()
                merged_starts.pop()
                v1, w1 = merged_values.pop(), merged_weights.pop()
                s1 = merged_starts.pop()
                merged_values.append((v1 * w1 + v2 * w2) / (w1 + w2))
                merged_weights.append(w1 + w2)
                merged_starts.append(s1)
        # expand blocks to step function knots
        knots_x, knots_y = [], []
        for block, start in enumerate(merged_starts):
            end = merged_starts[block + 1] if block + 1 < len(merged_starts) else len(x)
            knots_x.append(x[start])
            knots_y.append(merged_values[block])
            knots_x.append(x[end - 1])
            knots_y.append(merged_values[block])
        self.x_ = np.asarray(knots_x)
        self.y_ = np.clip(np.asarray(knots_y), 1e-6, 1 - 1e-6)
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        return np.interp(np.asarray(scores), self.x_, self.y_)

# ---------------------------------------------------------------- models ----

XGB_BASE = {
    "objective": "binary:logistic",
    "eval_metric": ["auc"],
    "tree_method": "hist",
    "nthread": 4,
    "seed": 42,
}


def train_xgb(X, y, feature_names, *, params=None, rounds=300, monotone=None):
    import xgboost as xgb

    config = dict(XGB_BASE)
    config.update(params or {})
    if monotone is not None:
        config["monotone_constraints"] = "(" + ",".join(str(c) for c in monotone) + ")"
    matrix = xgb.DMatrix(np.asarray(X), label=np.asarray(y), feature_names=list(feature_names))
    booster = xgb.train(config, matrix, num_boost_round=rounds, verbose_eval=False)
    return booster


def predict_xgb(booster, X, feature_names, *, margin=False):
    import xgboost as xgb

    matrix = xgb.DMatrix(np.asarray(X), feature_names=list(feature_names))
    return booster.predict(matrix, output_margin=margin)


def train_logistic(X, y, *, iterations=300, lr=0.3, l2=1e-3):
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std == 0] = 1.0
    Z = (X - mean) / std
    w = np.zeros(X.shape[1])
    b = float(np.log(max(y.mean(), 1e-6) / max(1 - y.mean(), 1e-6)))
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-np.clip(b + Z @ w, -35, 35)))
        err = p - y
        w -= lr * (Z.T @ err / len(y) + l2 * w)
        b -= lr * float(err.mean())
    return {"w": w / std, "b": b - float((w / std) @ mean)}


def predict_logistic(model, X):
    z = np.asarray(X, dtype=np.float64) @ model["w"] + model["b"]
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))

# ----------------------------------------------------- shift & robustness ---

def adversarial_validation(X_a, X_b, feature_names, *, seed=42, rounds=120) -> dict:
    """Train a classifier to distinguish sample A (0) from sample B (1).
    AUC ~0.5 = same distribution; high AUC = strong covariate shift.
    Returns the shift meter plus per-feature gain (shift drivers) and
    propensity-based importance weights for domain adaptation on A.
    """
    rng = np.random.default_rng(seed)
    X = np.vstack([X_a, X_b]).astype(np.float32)
    d = np.concatenate([np.zeros(len(X_a)), np.ones(len(X_b))])
    idx = rng.permutation(len(X))
    split = int(0.8 * len(X))
    booster = train_xgb(X[idx[:split]], d[idx[:split]], feature_names,
                        params={"max_depth": 4, "eta": 0.1, "seed": seed}, rounds=rounds)
    p_val = predict_xgb(booster, X[idx[split:]], feature_names)
    auc = roc_auc(d[idx[split:]], p_val)
    gains = booster.get_score(importance_type="gain")
    p_a = predict_xgb(booster, X_a, feature_names)
    weights = np.clip(p_a / np.clip(1 - p_a, 1e-3, None), 0.1, 10.0)  # density ratio, clipped
    return {
        "shift_auc": round(float(auc), 4),
        "shift_drivers": dict(sorted(gains.items(), key=lambda kv: -kv[1])[:6]),
        "importance_weights": weights,
    }


def bootstrap_metric(y, p, fn, *, replicates=200, seed=42) -> dict:
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    p = np.asarray(p)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    values = []
    for _ in range(replicates):
        idx = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
        values.append(fn(y[idx], p[idx]))
    values.sort()
    return {"lower_95": round(values[int(0.025 * len(values))], 4),
            "upper_95": round(values[int(0.975 * len(values)) - 1], 4)}


def seed_stability(train_fn, predict_fn, y_eval, *, seeds=(0, 1, 2, 3, 4)) -> dict:
    aucs = []
    for seed in seeds:
        model = train_fn(seed)
        aucs.append(roc_auc(y_eval, predict_fn(model)))
    return {"auc_mean": round(float(np.mean(aucs)), 4),
            "auc_std": round(float(np.std(aucs)), 5),
            "seeds": len(seeds)}


def perturbation_sensitivity(predict_fn, X, *, scale=0.05, seed=42) -> dict:
    """Mean |ΔPD| under ±scale relative noise on continuous inputs."""
    rng = np.random.default_rng(seed)
    base = predict_fn(X)
    noisy = X * (1 + rng.uniform(-scale, scale, X.shape)).astype(X.dtype)
    return {"mean_abs_pd_delta": round(float(np.mean(np.abs(predict_fn(noisy) - base))), 5),
            "p95_abs_pd_delta": round(float(np.percentile(np.abs(predict_fn(noisy) - base), 95)), 5)}
