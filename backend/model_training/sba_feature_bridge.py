"""Feature engineering for the real SBA small-business default model.

Turns a raw SBA 7(a) loan row into the model's feature vector. Every feature is
a genuine loan/borrower attribute known *at origination* -- no post-outcome
leakage. In particular `ChgOffPrinGr` (charged-off principal, non-zero only
after a default) and the causal-study `Selected` treatment flag are never used.

Each feature carries an economically-defensible monotone direction so an
underwriter can trust that, e.g., "more employees never increases predicted
risk". The signs feed XGBoost `monotone_constraints`.
"""
from __future__ import annotations

import math

# name -> monotone direction w.r.t. P(default): -1 risk-decreasing, +1 risk-increasing, 0 free.
SME_FEATURES: dict[str, int] = {
    "term_months": -1,          # longer amortising term -> lower default (SBA: strongest signal)
    "employees_log": -1,        # larger, more established firm -> lower default
    "jobs_supported_log": -1,   # more jobs created/retained -> healthier operation
    "gross_approved_log": 0,    # loan size: ambiguous, left free
    "guarantee_portion": 0,     # SBA-guaranteed share: ambiguous, left free
    "new_business": +1,         # brand-new business -> higher default
    "real_estate_backed": -1,   # real-estate collateral -> lower default
    "urban": 0,                 # location type: free
    "recession_origination": +1,  # originated during a recession -> higher default
}

FEATURE_NAMES: list[str] = list(SME_FEATURES)
MONOTONE_CONSTRAINTS: tuple[int, ...] = tuple(SME_FEATURES.values())


def _num(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def sba_row_to_features(row: dict) -> dict[str, float]:
    """Map one raw SBA row -> the leakage-free SME feature vector."""
    term = _num(row.get("Term"))
    employees = _num(row.get("NoEmp"))
    jobs = _num(row.get("CreateJob")) + _num(row.get("RetainedJob"))
    gross_approved = _num(row.get("GrAppv"))
    sba_approved = _num(row.get("SBA_Appv"))
    # `Portion` is present in the cleaned file; fall back to SBA_Appv/GrAppv.
    portion = row.get("Portion")
    guarantee_portion = _num(portion) if portion not in (None, "") else (
        sba_approved / gross_approved if gross_approved > 0 else 0.0
    )
    urban_rural = _num(row.get("UrbanRural"))

    return {
        "term_months": term,
        "employees_log": math.log1p(max(0.0, employees)),
        "jobs_supported_log": math.log1p(max(0.0, jobs)),
        "gross_approved_log": math.log1p(max(0.0, gross_approved)),
        "guarantee_portion": max(0.0, min(1.0, guarantee_portion)),
        "new_business": 1.0 if _num(row.get("New")) >= 1 else 0.0,
        "real_estate_backed": 1.0 if _num(row.get("RealEstate")) >= 1 else 0.0,
        "urban": 1.0 if urban_rural == 1 else 0.0,
        "recession_origination": 1.0 if _num(row.get("Recession")) >= 1 else 0.0,
    }


def sba_row_label(row: dict) -> int:
    return 1 if _num(row.get("label")) >= 1 else 0
