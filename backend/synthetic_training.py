"""Generates a synthetic MSME training set for the linear PD-proxy model.

Stdlib-only (uses `random`, seeded for reproducibility). The ground-truth
generative formula intentionally mirrors real underwriting intuition
(liquidity stability, repayment discipline, growth, leverage, digital
footprint breadth) so the fitted model recovers sensible, explainable
weights. Stage 2 replaces this with real AA/GST/UPI/EPFO-derived labels.
"""
import random

from linear_model import FEATURE_NAMES

_RNG = random.Random(42)


def _sample_row() -> dict[str, float]:
    return {
        "avg_monthly_inflow": _RNG.uniform(50_000, 1_200_000),
        "inflow_volatility": _RNG.uniform(0.02, 0.8),
        "cheque_bounce_rate": _RNG.uniform(0.0, 0.3),
        "gst_filing_streak_months": _RNG.uniform(0, 48),
        "gst_turnover_growth_pct": _RNG.uniform(-30, 40),
        "upi_txn_count_monthly": _RNG.uniform(5, 400),
        "unique_counterparties": _RNG.uniform(2, 80),
        "outstanding_debt_to_inflow": _RNG.uniform(0.0, 0.9),
    }


def _ground_truth_score(row: dict[str, float]) -> float:
    score = 50.0
    score += -35 * row["inflow_volatility"]
    score += -30 * row["cheque_bounce_rate"]
    score += 0.5 * min(row["gst_filing_streak_months"], 36)
    score += 0.4 * max(min(row["gst_turnover_growth_pct"], 40), -30)
    score += 0.03 * min(row["upi_txn_count_monthly"], 300)
    score += 0.15 * min(row["unique_counterparties"], 60)
    score += -25 * row["outstanding_debt_to_inflow"]
    score += _RNG.gauss(0, 4)  # measurement noise
    return max(0.0, min(100.0, score))


def generate_training_set(n_rows: int = 400) -> tuple[list[dict[str, float]], list[float]]:
    rows = [_sample_row() for _ in range(n_rows)]
    targets = [_ground_truth_score(r) for r in rows]
    return rows, targets


assert set(_sample_row().keys()) == set(FEATURE_NAMES)
