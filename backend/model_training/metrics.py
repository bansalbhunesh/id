"""Dependency-free binary-classification evaluation metrics.

Used both by the offline training script (train_pd_model.py) and, via
`backend/model_evaluation.py`, by the live `/model/evaluation` API so the
exact same metric implementations produce the numbers judges see.
"""
from __future__ import annotations

import math


def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    positives = sum(y_true)
    negatives = len(y_true) - positives
    if not positives or not negatives:
        return 0.0
    ranked = sorted(zip(y_score, y_true), key=lambda item: item[0])
    positive_rank_sum = 0.0
    position = 1
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        average_rank = (position + (position + end - index - 1)) / 2
        positive_rank_sum += average_rank * sum(y for _, y in ranked[index:end])
        position += end - index
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def ks_statistic(y_true: list[int], y_score: list[float]) -> float:
    total_goods = len(y_true) - sum(y_true)
    total_bads = sum(y_true)
    if not total_goods or not total_bads:
        return 0.0
    rows = sorted(zip(y_score, y_true), key=lambda item: item[0])
    goods_seen = 0
    bads_seen = 0
    max_gap = 0.0
    index = 0
    while index < len(rows):
        end = index + 1
        while end < len(rows) and rows[end][0] == rows[index][0]:
            end += 1
        bads_seen += sum(y for _, y in rows[index:end])
        goods_seen += (end - index) - sum(y for _, y in rows[index:end])
        max_gap = max(
            max_gap,
            abs(bads_seen / total_bads - goods_seen / total_goods),
        )
        index = end
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


def log_loss(y_true: list[int], y_prob: list[float]) -> float:
    if not y_true:
        return 0.0
    epsilon = 1e-12
    total = 0.0
    for target, probability in zip(y_true, y_prob):
        probability = min(max(probability, epsilon), 1 - epsilon)
        total -= target * math.log(probability) + (1 - target) * math.log(1 - probability)
    return total / len(y_true)


def expected_calibration_error(
    y_true: list[int], y_prob: list[float], buckets: int = 10
) -> float:
    bins = calibration_bins(y_true, y_prob, buckets)
    total = sum(item["n"] for item in bins) or 1
    return sum(
        item["n"] / total
        * abs(item["avg_predicted_pd"] - item["actual_default_rate"])
        for item in bins
    )


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
    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    return {
        "threshold": threshold,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(precision, 4),
        "recall_capture_rate": round(recall, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "specificity": round(specificity, 4),
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
