"""A tiny, dependency-free linear regression model with exact Shapley attribution.

For an additive linear model f(x) = intercept + sum(w_i * x_i), the exact
Shapley value of feature i (relative to a baseline = training-set mean) is
w_i * (x_i - mean_i) -- this is precisely what SHAP's LinearExplainer
computes. We implement OLS fit via the normal equations, solved with plain
Gauss-Jordan elimination, so the whole model needs no numpy/scikit-learn/shap.
This keeps the environment install-free while still being a genuinely
trained, genuinely explainable model. Swap-in target for Stage 2: a
gradient-boosted model (XGBoost/LightGBM) with the `shap` package, trained
on real AA/GST/UPI/EPFO data -- this module's public interface
(`fit`, `predict`, `shap_contributions`) is designed to stay the same.
"""
from __future__ import annotations

FEATURE_NAMES = [
    "avg_monthly_inflow",
    "inflow_volatility",
    "cheque_bounce_rate",
    "gst_filing_streak_months",
    "gst_turnover_growth_pct",
    "upi_txn_count_monthly",
    "unique_counterparties",
    "outstanding_debt_to_inflow",
]


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gauss-Jordan elimination with partial pivoting. matrix is square (n x n)."""
    n = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(augmented[r][col]))
        if abs(augmented[pivot_row][col]) < 1e-12:
            continue
        augmented[col], augmented[pivot_row] = augmented[pivot_row], augmented[col]

        pivot_val = augmented[col][col]
        augmented[col] = [v / pivot_val for v in augmented[col]]

        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            if factor == 0:
                continue
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[col])]

    return [augmented[i][n] for i in range(n)]


class LinearModel:
    """OLS-fit linear model over FEATURE_NAMES, with exact Shapley attribution."""

    def __init__(self) -> None:
        self.weights: dict[str, float] = {}
        self.intercept: float = 0.0
        self.feature_means: dict[str, float] = {}
        self.baseline_prediction: float = 0.0

    def fit(self, rows: list[dict[str, float]], targets: list[float]) -> None:
        n_features = len(FEATURE_NAMES)
        n_rows = len(rows)

        self.feature_means = {
            name: sum(r[name] for r in rows) / n_rows for name in FEATURE_NAMES
        }

        design = [[1.0] + [r[name] for name in FEATURE_NAMES] for r in rows]

        n_cols = n_features + 1
        xtx = [[0.0] * n_cols for _ in range(n_cols)]
        xty = [0.0] * n_cols
        for row, target in zip(design, targets):
            for i in range(n_cols):
                xty[i] += row[i] * target
                for j in range(n_cols):
                    xtx[i][j] += row[i] * row[j]

        coefficients = _solve_linear_system(xtx, xty)
        self.intercept = coefficients[0]
        self.weights = dict(zip(FEATURE_NAMES, coefficients[1:]))
        self.baseline_prediction = self.intercept + sum(
            self.weights[name] * self.feature_means[name] for name in FEATURE_NAMES
        )

    def predict(self, features: dict[str, float]) -> float:
        return self.intercept + sum(
            self.weights[name] * features[name] for name in FEATURE_NAMES
        )

    def shap_contributions(self, features: dict[str, float]) -> dict[str, float]:
        """Exact Shapley values for a linear model: w_i * (x_i - mean_i).

        These sum exactly to predict(features) - baseline_prediction.
        """
        return {
            name: self.weights[name] * (features[name] - self.feature_means[name])
            for name in FEATURE_NAMES
        }
