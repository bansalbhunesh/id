"""Validation and monitoring metrics for Stage 2 model governance."""
from __future__ import annotations

from collections import Counter
from math import log
from typing import Annotated

from pydantic import BaseModel, Field


ReasonCode = Annotated[str, Field(min_length=1, max_length=256)]
PeriodLabel = Annotated[str, Field(min_length=1, max_length=64)]


class ValidationRecord(BaseModel):
    score: float = Field(ge=0, le=100)
    defaulted: bool
    period: PeriodLabel
    reasons: list[ReasonCode] = Field(default_factory=list, max_length=20)


class ValidationRequest(BaseModel):
    development: list[ValidationRecord] = Field(max_length=20000)
    out_of_time: list[ValidationRecord] = Field(max_length=20000)


def _auc_for_good_label(records: list[ValidationRecord]) -> float:
    if not records:
        return 0.0
    positives = [record for record in records if not record.defaulted]
    negatives = [record for record in records if record.defaulted]
    if not positives or not negatives:
        return 0.0

    ordered = sorted((record.score, not record.defaulted) for record in records)
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2
        rank_sum += average_rank * sum(is_good for _score, is_good in ordered[index:end])
        index = end
    good_count = len(positives)
    bad_count = len(negatives)
    mann_whitney_u = rank_sum - good_count * (good_count + 1) / 2
    return round(mann_whitney_u / (good_count * bad_count), 4)


def _ks_statistic(records: list[ValidationRecord]) -> float:
    good_total = sum(not record.defaulted for record in records)
    bad_total = sum(record.defaulted for record in records)
    if not good_total or not bad_total:
        return 0.0

    ordered = sorted((record.score, record.defaulted) for record in records)
    good_seen = 0
    bad_seen = 0
    max_gap = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        for _score, defaulted in ordered[index:end]:
            if defaulted:
                bad_seen += 1
            else:
                good_seen += 1
        max_gap = max(max_gap, abs(good_seen / good_total - bad_seen / bad_total))
        index = end
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


def _validation_warnings(development: list[ValidationRecord], out_of_time: list[ValidationRecord]) -> list[str]:
    warnings: list[str] = []
    if not development:
        warnings.append("Development sample is empty; PSI and stability are not meaningful.")
    if not out_of_time:
        warnings.append("Out-of-time sample is empty; rank-order metrics are not meaningful.")
    if out_of_time:
        outcomes = {record.defaulted for record in out_of_time}
        if len(outcomes) < 2:
            warnings.append("Out-of-time sample needs both defaulted and non-defaulted records for AUC/KS.")
    if len(development) < 30 or len(out_of_time) < 30:
        warnings.append("Sample size is below production monitoring scale; treat metrics as directional only.")
    return warnings


def build_validation_report(development: list[ValidationRecord], out_of_time: list[ValidationRecord]) -> dict:
    auc = _auc_for_good_label(out_of_time)
    ks = _ks_statistic(out_of_time)
    drift = psi([record.score for record in development], [record.score for record in out_of_time])
    stability = reason_code_stability(development, out_of_time)
    warnings = _validation_warnings(development, out_of_time)
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
        "status": "insufficient_sample" if warnings else "ready",
        "warnings": warnings,
        "thresholds": {
            "auc": ">= 0.70 before pilot rollout",
            "ks": ">= 0.30 for rank-order separation",
            "psi": "< 0.10 stable, 0.10-0.25 watch, > 0.25 drift",
            "reason_code_stability": ">= 0.70 expected after recalibration",
        },
    }
