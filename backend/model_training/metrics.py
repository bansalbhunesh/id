"""Dependency-free binary-classification evaluation metrics.

Used both by the offline training script (train_pd_model.py) and, via
`backend/model_evaluation.py`, by the live `/model/evaluation` API so the
exact same metric implementations produce the numbers judges see.
"""
from __future__ import annotations

import math


def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    positives = [s for s, y in zip(y_score, y_true) if y == 1]
    negatives = [s for s, y in zip(y_score, y_true) if y == 0]
    if not positives or not negatives:
        return 0.0
    wins = 0.0
    for pos in positives:
        for neg in negatives:
            if pos > neg:
                wins += 1
            elif pos == neg:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def ks_statistic(y_true: list[int], y_score: list[float]) -> float:
    goods = sorted(s for s, y in zip(y_score, y_true) if y == 0)
    bads = sorted(s for s, y in zip(y_score, y_true) if y == 1)
    if not goods or not bads:
        return 0.0
    thresholds = sorted(set(goods + bads))
    max_gap = 0.0
    for t in thresholds:
        good_cdf = sum(s <= t for s in goods) / len(goods)
        bad_cdf = sum(s <= t for s in bads) / len(bads)
        max_gap = max(max_gap, abs(bad_cdf - good_cdf))
    return max_gap


def pr_auc(y_true: list[int], y_score: list[float]) -> float:
    n_pos = sum(y_true)
    if n_pos == 0:
        return 0.0
    order = sorted(range(len(y_score)), key=lambda i: -y_score[i])
    tp = 0
    fp = 0
    prev_recall = 0.0
    area = 0.0
    for i in order:
        if y_true[i] == 1:
            tp += 1
        else:
            fp += 1
        precision = tp / (tp + fp)
        recall = tp / n_pos
        area += precision * (recall - prev_recall)
        prev_recall = recall
    return area


def brier_score(y_true: list[int], y_prob: list[float]) -> float:
    n = len(y_true)
    if n == 0:
        return 0.0
    return sum((p - y) ** 2 for p, y in zip(y_prob, y_true)) / n


def confusion_at_threshold(y_true: list[int], y_prob: list[float], threshold: float) -> dict:
    tp = fp = tn = fn = 0
    for y, p in zip(y_true, y_prob):
        predicted_bad = p >= threshold
        if predicted_bad and y == 1:
            tp += 1
        elif predicted_bad and y == 0:
            fp += 1
        elif not predicted_bad and y == 0:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "threshold": threshold,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(precision, 4),
        "recall_capture_rate": round(recall, 4),
    }


def calibration_bins(y_true: list[int], y_prob: list[float], buckets: int = 10) -> list[dict]:
    rows = sorted(zip(y_prob, y_true), key=lambda r: r[0])
    n = len(rows)
    if n == 0:
        return []
    bin_size = max(1, n // buckets)
    bins = []
    for i in range(0, n, bin_size):
        chunk = rows[i : i + bin_size]
        if not chunk:
            continue
        avg_predicted = sum(p for p, _ in chunk) / len(chunk)
        avg_actual = sum(y for _, y in chunk) / len(chunk)
        bins.append(
            {
                "n": len(chunk),
                "avg_predicted_pd": round(avg_predicted, 4),
                "actual_default_rate": round(avg_actual, 4),
            }
        )
    return bins


def psi(expected: list[float], actual: list[float], buckets: int = 10) -> float:
    if not expected or not actual:
        return 0.0

    def bucket_counts(values: list[float]) -> list[int]:
        counts = [0] * buckets
        for v in values:
            idx = min(buckets - 1, max(0, int(v * buckets)))
            counts[idx] += 1
        return counts

    exp_counts = bucket_counts(expected)
    act_counts = bucket_counts(actual)
    total_exp = sum(exp_counts) or 1
    total_act = sum(act_counts) or 1
    epsilon = 1e-4
    value = 0.0
    for e, a in zip(exp_counts, act_counts):
        exp_pct = max(e / total_exp, epsilon)
        act_pct = max(a / total_act, epsilon)
        value += (act_pct - exp_pct) * math.log(act_pct / exp_pct)
    return value
