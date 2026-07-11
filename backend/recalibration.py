"""IDBI sandbox distribution and recalibration readiness reports."""
from __future__ import annotations

from statistics import median
from typing import Annotated

from pydantic import BaseModel, Field

from feed_ingestion import IDBISandboxPayload, readiness, to_profile
from linear_model import FEATURE_NAMES
from ml import model_status
from scoring import score_profile
from validation import ValidationRecord, build_validation_report


MIN_GBM_DEVELOPMENT_ROWS = 1000
MIN_GBM_OUT_OF_TIME_ROWS = 200
PeriodLabel = Annotated[str, Field(min_length=1, max_length=64)]


class SandboxOutcome(BaseModel):
    payload: IDBISandboxPayload
    defaulted: bool | None = None
    period: PeriodLabel = "pilot"


class SandboxRecalibrationRequest(BaseModel):
    development: list[SandboxOutcome] = Field(default_factory=list, max_length=5000)
    out_of_time: list[SandboxOutcome] = Field(default_factory=list, max_length=5000)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _profiles(records: list[SandboxOutcome]):
    return [to_profile(record.payload) for record in records]


def _feature_distribution(records: list[SandboxOutcome]) -> dict:
    profiles = _profiles(records)
    distribution = {}
    for feature in FEATURE_NAMES:
        values = [float(getattr(profile, feature)) for profile in profiles]
        distribution[feature] = {
            "min": round(min(values), 4) if values else 0.0,
            "p50": round(median(values), 4) if values else 0.0,
            "p90": round(_percentile(values, 0.9), 4) if values else 0.0,
            "max": round(max(values), 4) if values else 0.0,
        }
    return distribution


def _source_coverage(records: list[SandboxOutcome]) -> dict:
    if not records:
        return {"average_coverage_pct": 0.0, "source_presence_pct": {}}
    readiness_rows = [readiness(record.payload) for record in records]
    sources = sorted(
        {
            source
            for row in readiness_rows
            for source in row["sources_connected"] + row["missing_sources"]
        }
    )
    return {
        "average_coverage_pct": round(
            sum(row["coverage_pct"] for row in readiness_rows) / len(readiness_rows), 1
        ),
        "source_presence_pct": {
            source: round(
                sum(source in row["sources_connected"] for row in readiness_rows)
                / len(readiness_rows)
                * 100,
                1,
            )
            for source in sources
        },
    }


def _validation_records(records: list[SandboxOutcome]) -> list[ValidationRecord]:
    rows: list[ValidationRecord] = []
    for record in records:
        if record.defaulted is None:
            continue
        score = score_profile(to_profile(record.payload), record_audit=False)
        rows.append(
            ValidationRecord(
                score=score["score"],
                defaulted=record.defaulted,
                period=record.period,
                reasons=score["reasons"],
            )
        )
    return rows


def _warnings(request: SandboxRecalibrationRequest, dev_labels: int, oot_labels: int) -> list[str]:
    warnings: list[str] = []
    if not request.development and not request.out_of_time:
        warnings.append("No sandbox records supplied; upload AA/GST/UPI/EPFO payloads to profile distributions.")
    if dev_labels == 0 or oot_labels == 0:
        warnings.append("Repayment outcome labels are required for recalibration validation and GBM training.")
    if dev_labels < MIN_GBM_DEVELOPMENT_ROWS or oot_labels < MIN_GBM_OUT_OF_TIME_ROWS:
        warnings.append(
            "Production GBM/SHAP mode requires at least "
            f"{MIN_GBM_DEVELOPMENT_ROWS} labelled development and "
            f"{MIN_GBM_OUT_OF_TIME_ROWS} labelled out-of-time records."
        )
    return warnings


def build_recalibration_report(request: SandboxRecalibrationRequest) -> dict:
    development_validation = _validation_records(request.development)
    out_of_time_validation = _validation_records(request.out_of_time)
    validation = None
    if development_validation and out_of_time_validation:
        validation = build_validation_report(development_validation, out_of_time_validation)

    warnings = _warnings(request, len(development_validation), len(out_of_time_validation))
    ready_for_gbm = (
        len(development_validation) >= MIN_GBM_DEVELOPMENT_ROWS
        and len(out_of_time_validation) >= MIN_GBM_OUT_OF_TIME_ROWS
    )

    return {
        "mode": "idbi_sandbox_recalibration_report",
        "records": {
            "development": len(request.development),
            "out_of_time": len(request.out_of_time),
            "labelled_development": len(development_validation),
            "labelled_out_of_time": len(out_of_time_validation),
        },
        "source_coverage": {
            "development": _source_coverage(request.development),
            "out_of_time": _source_coverage(request.out_of_time),
        },
        "feature_distributions": {
            "development": _feature_distribution(request.development),
            "out_of_time": _feature_distribution(request.out_of_time),
        },
        "validation": validation,
        "model_upgrade": {
            "target": "XGBoost/LightGBM with SHAP",
            "ready": ready_for_gbm,
            "minimum_records": {
                "development": MIN_GBM_DEVELOPMENT_ROWS,
                "out_of_time": MIN_GBM_OUT_OF_TIME_ROWS,
            },
            "runtime": model_status(),
        },
        "status": "ready_for_gbm" if ready_for_gbm and not warnings else "needs_more_sandbox_data",
        "warnings": warnings,
    }
