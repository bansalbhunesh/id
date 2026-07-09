"""Validation and monitoring metrics for Stage 2 model governance."""
from __future__ import annotations

from collections import Counter
from math import log

from pydantic import BaseModel, Field


class ValidationRecord(BaseModel):
    score: float = Field(ge=0, le=100)
    defaulted: bool
    period: str
    reasons: list[str] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    development: list[ValidationRecord]
    out_of_time: list[ValidationRecord]


def _auc_for_good_label(records: list[ValidationRecord]) -> float:
    if not records:
        return 0.0
    positives = [record for record in records if not record.defaulted]
    negatives = [record for record in records if record.defaulted]
    if not positives or not negatives:
        return 0.0

    wins = 0.0
    for good in positives:
        for bad in negatives:
            if good.score > bad.score:
                wins += 1
            elif good.score == bad.score:
                wins += 0.5
    return round(wins / (len(positives) * len(negatives)), 4)


def _ks_statistic(records: list[ValidationRecord]) -> float:
    goods = sorted([record.score for record in records if not record.defaulted])
    bads = sorted([record.score for record in records if record.defaulted])
    if not goods or not bads:
        return 0.0

    thresholds = sorted(set(goods + bads))
    max_gap = 0.0
    for threshold in thresholds:
        good_cdf = sum(score <= threshold for score in goods) / len(goods)
        bad_cdf = sum(score <= threshold for score in bads) / len(bads)
        max_gap = max(max_gap, abs(good_cdf - bad_cdf))
    return round(max_gap, 4)


def _bucket_counts(values: list[float], buckets: int) -> list[int]:
    counts = [0 for _ in range(buckets)]
    for value in values:
        idx = min(buckets - 1, max(0, int(value / (100 / buckets))))
        counts[idx] += 1
    return counts


def psi(expected_scores: list[float], actual_scores: list[float], buckets: int = 10) -> float:
    if not expected_scores or not actual_scores:
        return 0.0
    expected = _bucket_counts(expected_scores, buckets)
    actual = _bucket_counts(actual_scores, buckets)
    total_expected = sum(expected)
    total_actual = sum(actual)
    epsilon = 0.0001
    value = 0.0
    for exp_count, act_count in zip(expected, actual):
        exp_pct = max(exp_count / total_expected, epsilon)
        act_pct = max(act_count / total_actual, epsilon)
        value += (act_pct - exp_pct) * log(act_pct / exp_pct)
    return round(value, 4)


def reason_code_stability(reference: list[ValidationRecord], current: list[ValidationRecord]) -> float:
    ref_counts = Counter(reason for record in reference for reason in record.reasons)
    cur_counts = Counter(reason for record in current for reason in record.reasons)
    if not ref_counts and not cur_counts:
        return 1.0
    all_reasons = set(ref_counts) | set(cur_counts)
    overlap = sum(min(ref_counts[reason], cur_counts[reason]) for reason in all_reasons)
    union = sum(max(ref_counts[reason], cur_counts[reason]) for reason in all_reasons)
    return round(overlap / union, 4) if union else 1.0


def build_validation_report(development: list[ValidationRecord], out_of_time: list[ValidationRecord]) -> dict:
    auc = _auc_for_good_label(out_of_time)
    ks = _ks_statistic(out_of_time)
    drift = psi([record.score for record in development], [record.score for record in out_of_time])
    stability = reason_code_stability(development, out_of_time)
    return {
        "records": {
            "development": len(development),
            "out_of_time": len(out_of_time),
        },
        "metrics": {
            "auc": auc,
            "gini": round(2 * auc - 1, 4) if auc else 0.0,
            "ks": ks,
            "psi": drift,
            "reason_code_stability": stability,
        },
        "thresholds": {
            "auc": ">= 0.70 before pilot rollout",
            "ks": ">= 0.30 for rank-order separation",
            "psi": "< 0.10 stable, 0.10-0.25 watch, > 0.25 drift",
            "reason_code_stability": ">= 0.70 expected after recalibration",
        },
    }
