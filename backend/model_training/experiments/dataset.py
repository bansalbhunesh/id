"""Leakage-audited dataset builder for the SBA 7(a) FOIA loan-level files.

Every feature is a loan/borrower attribute known at origination. The leakage
register lives in foia_manifest.json and is enforced here by construction: the
raw post-outcome columns are read only to build the label / survival target,
never into the feature matrix.

Label policy (see manifest): PIF -> 0, CHGOFF -> 1; CANCLD/COMMIT (never
disbursed) and EXEMPT (active/undisclosed) rows are excluded from labelled
sets. Resolved-only sampling right-censors slow outcomes in late vintages;
the survival columns (event, months_to_event) let E16 model that explicitly.

The parsed matrix is cached as a gitignored .npz keyed by the source file's
manifest hash, so the 600 MB CSVs are parsed once.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
CACHE_DIR = DATA_DIR / "cache"
MANIFEST = json.loads((HERE / "foia_manifest.json").read_text(encoding="utf-8"))

# Feature schema. Monotone direction w.r.t. P(default): -1 decreasing,
# +1 increasing, 0 free. Directions are stated economic assumptions -- the
# monotone-vs-free experiment (E3) tests whether imposing them costs signal.
FEATURES: dict[str, int] = {
    "term_months": -1,
    "gross_approval_log": 0,
    "guarantee_portion": 0,
    "jobs_supported_log": -1,
    "is_new_business": +1,
    "is_change_of_ownership": 0,
    "is_individual": +1,          # unincorporated borrower
    "is_partnership": 0,
    "revolver": +1,               # revolving credit lines charge off more
    "collateral": -1,
    "fixed_rate": 0,
    "has_franchise": 0,
    "sector_accom_food": +1,      # NAICS 72
    "sector_retail": +1,          # 44-45
    "sector_construction": +1,    # 23
    "sector_professional": 0,     # 54
    "sector_health": -1,          # 62
    "sector_manufacturing": 0,    # 31-33
    "sector_wholesale": 0,        # 42
    "sector_transport": +1,       # 48-49
    "sector_other_services": 0,   # 81
}
FEATURE_NAMES = list(FEATURES)
MONOTONE = tuple(FEATURES.values())

# Sensitivity-only column (lender's contemporaneous risk view, not a borrower
# attribute): carried separately, never inside the default feature matrix.
RATE_COLUMN = "initial_interest_rate"

_SECTOR_FLAGS = {
    "72": "sector_accom_food",
    "44": "sector_retail", "45": "sector_retail",
    "23": "sector_construction",
    "54": "sector_professional",
    "62": "sector_health",
    "31": "sector_manufacturing", "32": "sector_manufacturing", "33": "sector_manufacturing",
    "42": "sector_wholesale",
    "48": "sector_transport", "49": "sector_transport",
    "81": "sector_other_services",
}

WEST = {"WA", "OR", "CA", "NV", "AZ", "ID", "UT", "MT", "WY", "CO", "NM", "AK", "HI"}
SOUTH = {"TX", "OK", "AR", "LA", "MS", "AL", "TN", "KY", "GA", "FL", "SC", "NC", "VA", "WV", "MD", "DE", "DC"}
MIDWEST = {"ND", "SD", "NE", "KS", "MN", "IA", "MO", "WI", "IL", "MI", "IN", "OH"}


def _num(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _parse_date(value: str):
    value = (value or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _region(state: str) -> int:
    state = (state or "").strip().upper()
    if state in WEST:
        return 0
    if state in SOUTH:
        return 1
    if state in MIDWEST:
        return 2
    return 3  # Northeast + territories + unknown


def _row_features(row: dict) -> list[float] | None:
    term = _num(row.get("TerminMonths"))
    gross = _num(row.get("GrossApproval"))
    if gross <= 0:
        return None
    guarantee = _num(row.get("SBAGuaranteedApproval")) / gross
    age = (row.get("BusinessAge") or "").lower()
    business_type = (row.get("BusinessType") or "").upper()
    naics = (row.get("NAICSCode") or "").strip()[:2]

    values = {
        "term_months": term,
        "gross_approval_log": float(np.log1p(gross)),
        "guarantee_portion": min(max(guarantee, 0.0), 1.0),
        "jobs_supported_log": float(np.log1p(max(0.0, _num(row.get("JobsSupported"))))),
        "is_new_business": 1.0 if ("new business" in age or "startup" in age) else 0.0,
        "is_change_of_ownership": 1.0 if "change of ownership" in age else 0.0,
        "is_individual": 1.0 if business_type == "INDIVIDUAL" else 0.0,
        "is_partnership": 1.0 if business_type == "PARTNERSHIP" else 0.0,
        "revolver": 1.0 if (row.get("RevolverStatus") or "").strip().upper() in ("Y", "1") else 0.0,
        "collateral": 1.0 if (row.get("CollateralInd") or "").strip().upper() == "Y" else 0.0,
        "fixed_rate": 1.0 if (row.get("FixedorVariableInterestRate") or "").strip().upper() == "F" else 0.0,
        "has_franchise": 1.0 if (row.get("FranchiseCode") or "").strip() not in ("", "0") else 0.0,
    }
    for flag in set(_SECTOR_FLAGS.values()):
        values[flag] = 0.0
    if naics in _SECTOR_FLAGS:
        values[_SECTOR_FLAGS[naics]] = 1.0
    return [values[name] for name in FEATURE_NAMES]


def load_file(filename: str, *, resolved_only: bool = True) -> dict[str, np.ndarray]:
    """Parse one FOIA CSV into arrays (cached).

    Returns dict with: X (n,d), y, fy, region, rate, event, months_to_event.
    For resolved_only=False, y is -1 for unresolved rows (census use only).
    """
    entry = next(item for item in MANIFEST["files"] if item["filename"] == filename)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{filename}.{entry['sha256'][:12]}.{'res' if resolved_only else 'all'}.npz"
    if cache.exists():
        loaded = np.load(cache)
        return {key: loaded[key] for key in loaded.files}

    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. Run backend/model_training/experiments/fetch_foia_data.py"
        )

    rows_X, rows_y, rows_fy, rows_region, rows_rate = [], [], [], [], []
    rows_event, rows_months = [], []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            status = (row.get("LoanStatus") or "").strip().upper()
            if status in ("CANCLD", "COMMIT"):
                continue
            resolved = status in ("PIF", "CHGOFF")
            if resolved_only and not resolved:
                continue
            features = _row_features(row)
            if features is None:
                continue
            approval = _parse_date(row.get("ApprovalDate"))
            chargeoff = _parse_date(row.get("ChargeoffDate"))
            asof = _parse_date(row.get("AsOfDate")) or datetime(2025, 9, 30)
            if approval is None:
                continue
            if status == "CHGOFF" and chargeoff is not None:
                event, months = 1.0, max(1.0, (chargeoff - approval).days / 30.44)
            elif status == "CHGOFF":
                event, months = 1.0, max(1.0, _num(row.get("TerminMonths"), 60.0) / 2)
            else:  # PIF or unresolved: censored at asof (PIF earlier, but PIF date optional)
                pif = _parse_date(row.get("PaidinFullDate"))
                end = pif or asof
                event, months = 0.0, max(1.0, (end - approval).days / 30.44)

            rows_X.append(features)
            rows_y.append(1 if status == "CHGOFF" else (0 if status == "PIF" else -1))
            rows_fy.append(int(_num(row.get("ApprovalFY"), approval.year)))
            rows_region.append(_region(row.get("ProjectState") or row.get("BorrState")))
            rows_rate.append(_num(row.get("InitialInterestRate")))
            rows_event.append(event)
            rows_months.append(months)

    arrays = {
        "X": np.asarray(rows_X, dtype=np.float32),
        "y": np.asarray(rows_y, dtype=np.int8),
        "fy": np.asarray(rows_fy, dtype=np.int16),
        "region": np.asarray(rows_region, dtype=np.int8),
        "rate": np.asarray(rows_rate, dtype=np.float32),
        "event": np.asarray(rows_event, dtype=np.float32),
        "months_to_event": np.asarray(rows_months, dtype=np.float32),
    }
    np.savez_compressed(cache, **arrays)
    return arrays


def temporal_protocol(seed: int = 42) -> dict[str, dict[str, np.ndarray]]:
    """The primary evaluation protocol.

    TRAIN      = FY2010-2016 resolved loans minus calibration share
    CALIBRATION= random 20% of FY2010-2016 (stratified by label)
    HOLDOUT    = random 15% of FY2010-2016 carved out before any fitting
    OOT        = FY2017-2019 resolved loans (never seen, later in time)
    STRESS     = FY2005-2007 vintages from the 2000s file (recession exposure)
    """
    modern = load_file("foia-7a-fy2000-fy2009.csv")  # loaded for stress below
    recession_mask = (modern["fy"] >= 2005) & (modern["fy"] <= 2007)
    stress = {key: value[recession_mask] for key, value in modern.items()}

    data = load_file("foia-7a-fy2010-fy2019.csv")
    early = (data["fy"] >= 2010) & (data["fy"] <= 2016)
    late = (data["fy"] >= 2017) & (data["fy"] <= 2019)
    pool = {key: value[early] for key, value in data.items()}
    oot = {key: value[late] for key, value in data.items()}

    rng = np.random.default_rng(seed)
    n = pool["y"].shape[0]
    order = rng.permutation(n)
    # Stratified assignment: shuffle within each class, then split by ratio.
    splits = {"train": [], "calibration": [], "holdout": []}
    for label in (0, 1):
        idx = order[pool["y"][order] == label]
        n_cal = int(0.20 * idx.size)
        n_hold = int(0.15 * idx.size)
        splits["calibration"].append(idx[:n_cal])
        splits["holdout"].append(idx[n_cal:n_cal + n_hold])
        splits["train"].append(idx[n_cal + n_hold:])
    out = {}
    for name, parts in splits.items():
        chosen = np.concatenate(parts)
        rng.shuffle(chosen)
        out[name] = {key: value[chosen] for key, value in pool.items()}
    out["oot"] = oot
    out["stress"] = stress
    return out
