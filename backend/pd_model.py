"""A tiny, dependency-free logistic-regression PD (probability of default)
model with exact Shapley attribution in logit space.

Mirrors `linear_model.LinearModel`'s design (stdlib-only, genuinely trained,
genuinely explainable) but fits a real binary default-outcome label via
gradient descent instead of an OLS score-proxy. For a linear-in-logit model
logit(x) = intercept + sum(w_i * x_i), the exact Shapley value of feature i
(baseline = training-set mean) is w_i * (x_i - mean_i) in logit space -- this
is the same closed form LinearModel uses, just before the sigmoid link.

Trained by `backend/model_training/train_pd_model.py` on a public
credit-default dataset; the fitted artifact is loaded at runtime by
`ml.py` with no scikit-learn/xgboost/shap dependency required to serve.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def fit_platt_scaler(
    raw_logits: list[float],
    targets: list[int],
    *,
    learning_rate: float = 0.05,
    iterations: int = 800,
    l2: float = 1e-4,
) -> tuple[float, float]:
    """Fit ``calibrated_logit = intercept + slope * raw_logit``.

    The calibration set is kept outside model fitting. Standardising the
    one-dimensional margin before gradient descent makes the optimiser stable;
    the returned parameters are folded back onto the raw margin.
    """
    if not raw_logits or len(raw_logits) != len(targets):
        raise ValueError("Platt calibration requires equally sized non-empty logits and targets")
    if len(set(targets)) < 2:
        raise ValueError("Platt calibration requires both outcome classes")

    mean_score = sum(raw_logits) / len(raw_logits)
    variance = sum((value - mean_score) ** 2 for value in raw_logits) / len(raw_logits)
    std_score = math.sqrt(variance) or 1.0
    standardized = [(value - mean_score) / std_score for value in raw_logits]

    slope = 0.0
    intercept = math.log(sum(targets) / (len(targets) - sum(targets)))
    n = len(targets)
    try:
        import numpy as np

        values_np = np.asarray(standardized, dtype=float)
        targets_np = np.asarray(targets, dtype=float)
        for _ in range(iterations):
            logits = intercept + slope * values_np
            probabilities = np.where(
                logits >= 0,
                1.0 / (1.0 + np.exp(-logits)),
                np.exp(logits) / (1.0 + np.exp(logits)),
            )
            errors = probabilities - targets_np
            grad_slope = float(values_np @ errors / n + l2 * slope)
            grad_intercept = float(errors.mean())
            slope -= learning_rate * grad_slope
            intercept -= learning_rate * grad_intercept
    except ImportError:
        for _ in range(iterations):
            grad_slope = 0.0
            grad_intercept = 0.0
            for value, target in zip(standardized, targets):
                error = _sigmoid(intercept + slope * value) - target
                grad_slope += error * value
                grad_intercept += error
            grad_slope = grad_slope / n + l2 * slope
            grad_intercept /= n
            slope -= learning_rate * grad_slope
            intercept -= learning_rate * grad_intercept

    raw_slope = slope / std_score
    raw_intercept = intercept - slope * mean_score / std_score
    return raw_slope, raw_intercept


class LogisticModel:
    """Standardized-gradient-descent logistic regression with L2 regularization.

    Fits on raw feature values directly (standardization is folded into the
    final weights/intercept so `predict`/`shap_contributions` operate on raw
    inputs, exactly like `linear_model.LinearModel`).
    """

    def __init__(self, feature_names: list[str]) -> None:
        self.feature_names = list(feature_names)
        self.weights: dict[str, float] = {name: 0.0 for name in self.feature_names}
        self.intercept: float = 0.0
        self.feature_means: dict[str, float] = {}
        self.calibration_slope: float = 1.0
        self.calibration_intercept: float = 0.0
        self.baseline_logit: float = 0.0
        self.baseline_probability: float = 0.0

    def fit(
        self,
        rows: list[dict[str, float]],
        targets: list[int],
        *,
        learning_rate: float = 0.5,
        iterations: int = 800,
        l2: float = 1e-3,
        seed: int = 42,
    ) -> None:
        n = len(rows)
        names = self.feature_names

        means = {name: sum(r[name] for r in rows) / n for name in names}
        stds = {}
        for name in names:
            variance = sum((r[name] - means[name]) ** 2 for r in rows) / n
            stds[name] = math.sqrt(variance) or 1.0

        standardized = [
            {name: (r[name] - means[name]) / stds[name] for name in names} for r in rows
        ]

        w = {name: 0.0 for name in names}
        b = 0.0
        try:
            import numpy as np

            matrix = np.asarray(
                [[row[name] for name in names] for row in standardized], dtype=float
            )
            target_array = np.asarray(targets, dtype=float)
            weights = np.zeros(len(names), dtype=float)
            for _ in range(iterations):
                logits = b + matrix @ weights
                probabilities = np.where(
                    logits >= 0,
                    1.0 / (1.0 + np.exp(-logits)),
                    np.exp(logits) / (1.0 + np.exp(logits)),
                )
                errors = probabilities - target_array
                gradient = matrix.T @ errors / n + l2 * weights
                weights -= learning_rate * gradient
                b -= learning_rate * float(errors.mean())
            w = {name: float(weights[index]) for index, name in enumerate(names)}
        except ImportError:
            for _ in range(iterations):
                grad_w = {name: 0.0 for name in names}
                grad_b = 0.0
                for row, y in zip(standardized, targets):
                    z = b + sum(w[name] * row[name] for name in names)
                    p = _sigmoid(z)
                    error = p - y
                    for name in names:
                        grad_w[name] += error * row[name]
                    grad_b += error
                for name in names:
                    grad_w[name] = grad_w[name] / n + l2 * w[name]
                grad_b /= n
                for name in names:
                    w[name] -= learning_rate * grad_w[name]
                b -= learning_rate * grad_b

        # Fold standardization into raw-input weights: z = b + sum(w_i * (x_i-mean_i)/std_i)
        # = (b - sum(w_i*mean_i/std_i)) + sum((w_i/std_i) * x_i)
        raw_weights = {name: w[name] / stds[name] for name in names}
        raw_intercept = b - sum(w[name] * means[name] / stds[name] for name in names)

        self.weights = raw_weights
        self.intercept = raw_intercept
        self.feature_means = means
        self._refresh_baseline()

    def calibrate(self, rows: list[dict[str, float]], targets: list[int]) -> None:
        raw_logits = [self.predict_raw_logit(row) for row in rows]
        self.calibration_slope, self.calibration_intercept = fit_platt_scaler(
            raw_logits, targets
        )
        self._refresh_baseline()

    def _refresh_baseline(self) -> None:
        raw_baseline = self.intercept + sum(
            self.weights[name] * self.feature_means[name] for name in self.feature_names
        )
        self.baseline_logit = (
            self.calibration_intercept + self.calibration_slope * raw_baseline
        )
        self.baseline_probability = _sigmoid(self.baseline_logit)

    def predict_raw_logit(self, features: dict[str, float]) -> float:
        return self.intercept + sum(
            self.weights[name] * features[name] for name in self.feature_names
        )

    def predict_logit(self, features: dict[str, float]) -> float:
        return (
            self.calibration_intercept
            + self.calibration_slope * self.predict_raw_logit(features)
        )

    def predict_proba(self, features: dict[str, float]) -> float:
        return _sigmoid(self.predict_logit(features))

    def shap_contributions_logit(self, features: dict[str, float]) -> dict[str, float]:
        """Exact Shapley values in logit space: w_i * (x_i - mean_i).

        These sum exactly to predict_logit(features) - baseline_logit.
        """
        return {
            name: self.calibration_slope
            * self.weights[name]
            * (features[name] - self.feature_means[name])
            for name in self.feature_names
        }

    def to_dict(self) -> dict:
        return {
            "feature_names": self.feature_names,
            "weights": self.weights,
            "intercept": self.intercept,
            "feature_means": self.feature_means,
            "calibration_slope": self.calibration_slope,
            "calibration_intercept": self.calibration_intercept,
            "baseline_logit": self.baseline_logit,
            "baseline_probability": self.baseline_probability,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LogisticModel":
        model = cls(data["feature_names"])
        model.weights = data["weights"]
        model.intercept = data["intercept"]
        model.feature_means = data["feature_means"]
        model.calibration_slope = data.get("calibration_slope", 1.0)
        model.calibration_intercept = data.get("calibration_intercept", 0.0)
        model._refresh_baseline()
        return model

    @classmethod
    def load(cls, path: str | Path) -> "LogisticModel":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))
