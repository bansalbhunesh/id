"""Runtime wrapper for the trained XGBoost PD challenger/champion.

XGBoost's native ``pred_contribs`` output is exact TreeSHAP in margin
(log-odds) space, including the model bias term. The calibration slope is
therefore applied directly to every contribution and the intercept to the
bias, preserving the exact reconstruction invariant after Platt scaling.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


class XGBoostPDModel:
    def __init__(
        self,
        model_path: str | Path,
        *,
        feature_names: list[str],
        calibration_slope: float,
        calibration_intercept: float,
    ) -> None:
        import xgboost as xgb

        self.feature_names = list(feature_names)
        self.calibration_slope = float(calibration_slope)
        self.calibration_intercept = float(calibration_intercept)
        self.booster = xgb.Booster()
        self.booster.load_model(str(model_path))
        self.baseline_logit = self._calibrated_contributions(
            {name: 0.0 for name in self.feature_names}
        )[1]
        self.baseline_probability = _sigmoid(self.baseline_logit)

    @classmethod
    def load(cls, model_path: str | Path, metadata_path: str | Path) -> "XGBoostPDModel":
        with Path(metadata_path).open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
        return cls(
            model_path,
            feature_names=metadata["feature_names"],
            calibration_slope=metadata["calibration_slope"],
            calibration_intercept=metadata["calibration_intercept"],
        )

    def _matrix(self, features: dict[str, float]):
        import xgboost as xgb

        return xgb.DMatrix(
            [[float(features[name]) for name in self.feature_names]],
            feature_names=self.feature_names,
        )

    def predict_raw_logit(self, features: dict[str, float]) -> float:
        return float(self.booster.predict(self._matrix(features), output_margin=True)[0])

    def predict_logit(self, features: dict[str, float]) -> float:
        return (
            self.calibration_intercept
            + self.calibration_slope * self.predict_raw_logit(features)
        )

    def predict_proba(self, features: dict[str, float]) -> float:
        return _sigmoid(self.predict_logit(features))

    def _calibrated_contributions(
        self, features: dict[str, float]
    ) -> tuple[dict[str, float], float]:
        values = self.booster.predict(self._matrix(features), pred_contribs=True)[0]
        contributions = {
            name: self.calibration_slope * float(value)
            for name, value in zip(self.feature_names, values[:-1])
        }
        bias = self.calibration_intercept + self.calibration_slope * float(values[-1])
        return contributions, bias

    def shap_contributions_logit(self, features: dict[str, float]) -> dict[str, float]:
        contributions, _bias = self._calibrated_contributions(features)
        return contributions

    def shap_baseline_logit(self, features: dict[str, float]) -> float:
        _contributions, bias = self._calibrated_contributions(features)
        return bias
