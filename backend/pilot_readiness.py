"""Dated IDBI pilot-outcome contract and temporal training readiness gates.

This module does not persist submitted records or train on the public server.
It validates whether an approved sandbox extract is mature and broad enough
for a separate offline champion/challenger training job.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field, model_validator

from feed_ingestion import IDBISandboxPayload, readiness


@dataclass(frozen=True)
class PilotThresholds:
    mature_total: int = 1500
    development: int = 1000
    calibration: int = 200
    out_of_time: int = 200
    ntc_ntb: int = 100
    min_segment: int = 50
    min_decision_months: int = 6
    source_coverage_pct: float = 80.0


DEFAULT_THRESHOLDS = PilotThresholds()
MATURITY_DAYS = 365


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class PilotOutcomeRecord(BaseModel):
    application_id: str = Field(min_length=8, max_length=128)
    decision_at: datetime
    observation_end_at: datetime
    bad_12m: bool
    payload: IDBISandboxPayload

    @model_validator(mode="after")
    def observation_follows_decision(self):
        decision = _as_utc(self.decision_at)
        consent_granted = _as_utc(self.payload.consent.granted_at)
        consent_expires = _as_utc(self.payload.consent.expires_at)
        if not consent_granted <= decision <= consent_expires:
            raise ValueError("payload consent must be active at decision_at")
        if _as_utc(self.observation_end_at) <= decision:
            raise ValueError("observation_end_at must be after decision_at")
        if _as_utc(self.observation_end_at) > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("observation_end_at cannot be in the future")
        return self

    def is_mature(self, *, as_of: datetime) -> bool:
        decision = _as_utc(self.decision_at)
        observation = _as_utc(self.observation_end_at)
        return observation <= as_of and observation >= decision + timedelta(days=MATURITY_DAYS)


class PilotReadinessRequest(BaseModel):
    records: list[PilotOutcomeRecord] = Field(default_factory=list, max_length=10000)
    as_of: datetime | None = None


def outcome_contract() -> dict:
    return {
        "contract_version": "pilot-outcome-v1",
        "record_schema": PilotOutcomeRecord.model_json_schema(),
        "label": {
            "field": "bad_12m",
            "definition": (
                "Bank-approved adverse credit outcome observed within 12 months; "
                "the precise DPD/write-off/restructure definition requires IDBI sign-off."
            ),
            "maturity_rule": (
                f"observation_end_at must be at least {MATURITY_DAYS} days after decision_at "
                "before a record enters training or OOT evidence."
            ),
        },
        "split_policy": {
            "method": "chronological 70/15/15",
            "development": "earliest mature decisions; model fitting only",
            "calibration": "later mature decisions; calibration, selection and threshold only",
            "out_of_time": "latest mature decisions; opened once for final evidence",
            "random_shuffle": False,
        },
        "privacy": {
            "persistence": "none on this endpoint",
            "identifiers_returned": False,
            "approved_environment_required": True,
        },
        "thresholds": asdict(DEFAULT_THRESHOLDS),
    }


def _temporal_split(records: list[PilotOutcomeRecord]) -> dict[str, list[PilotOutcomeRecord]]:
    ordered = sorted(records, key=lambda row: _as_utc(row.decision_at))
    count = len(ordered)
    if count < 3:
        return {"development": ordered, "calibration": [], "out_of_time": []}
    development_end = max(1, int(count * 0.70))
    calibration_end = max(development_end + 1, int(count * 0.85))
    calibration_end = min(calibration_end, count - 1)
    return {
        "development": ordered[:development_end],
        "calibration": ordered[development_end:calibration_end],
        "out_of_time": ordered[calibration_end:],
    }


def _split_summary(records: list[PilotOutcomeRecord]) -> dict:
    if not records:
        return {
            "n": 0,
            "decision_start": None,
            "decision_end": None,
            "bad_rate": None,
            "has_both_outcomes": False,
        }
    decisions = [_as_utc(row.decision_at) for row in records]
    bad_count = sum(row.bad_12m for row in records)
    return {
        "n": len(records),
        "decision_start": min(decisions).date().isoformat(),
        "decision_end": max(decisions).date().isoformat(),
        "bad_rate": round(bad_count / len(records), 4),
        "has_both_outcomes": 0 < bad_count < len(records),
    }


def _vintage_band(months: int) -> str:
    if months < 24:
        return "<24m"
    if months < 60:
        return "24-59m"
    return "60m+"


def _segment_counts(records: list[PilotOutcomeRecord]) -> dict[str, dict[str, int]]:
    dimensions: dict[str, Counter] = {
        "sector": Counter(),
        "geography": Counter(),
        "vintage": Counter(),
        "gender": Counter(),
        "bureau_history": Counter(),
    }
    for row in records:
        profile = row.payload.profile
        dimensions["sector"][profile.sector or "Unavailable"] += 1
        dimensions["geography"][profile.district or "Unavailable"] += 1
        dimensions["vintage"][_vintage_band(profile.vintage_months)] += 1
        dimensions["gender"][profile.gender or "Unavailable"] += 1
        dimensions["bureau_history"][
            "bureau_history" if row.payload.bureau.has_bureau_history else "NTC_NTB"
        ] += 1
    return {name: dict(sorted(counts.items())) for name, counts in dimensions.items()}


def _source_coverage(records: list[PilotOutcomeRecord]) -> dict:
    if not records:
        return {"average_pct": 0.0, "by_source_pct": {}}
    rows = [readiness(record.payload) for record in records]
    sources = sorted(
        {
            source
            for row in rows
            for source in row["sources_connected"] + row["missing_sources"]
        }
    )
    return {
        "average_pct": round(sum(row["coverage_pct"] for row in rows) / len(rows), 1),
        "by_source_pct": {
            source: round(
                sum(source in row["sources_connected"] for row in rows) / len(rows) * 100,
                1,
            )
            for source in sources
        },
    }


def _gate(code: str, passed: bool, detail: str) -> dict:
    return {"code": code, "status": "pass" if passed else "block", "detail": detail}


def build_pilot_readiness_report(
    request: PilotReadinessRequest,
    *,
    thresholds: PilotThresholds = DEFAULT_THRESHOLDS,
) -> dict:
    as_of = _as_utc(request.as_of or datetime.now(timezone.utc))
    ids = [record.application_id for record in request.records]
    duplicates = sum(count - 1 for count in Counter(ids).values() if count > 1)
    mature = [record for record in request.records if record.is_mature(as_of=as_of)]
    splits = _temporal_split(mature)
    summaries = {name: _split_summary(rows) for name, rows in splits.items()}
    segments = _segment_counts(mature)
    source_coverage = _source_coverage(mature)
    decision_months = len(
        {(_as_utc(row.decision_at).year, _as_utc(row.decision_at).month) for row in mature}
    )
    ntc_count = segments.get("bureau_history", {}).get("NTC_NTB", 0)
    fairness_dimensions = ["sector", "geography", "vintage", "gender", "bureau_history"]
    supported_groups = {
        dimension: sorted(
            group
            for group, count in segments.get(dimension, {}).items()
            if count >= thresholds.min_segment
        )
        for dimension in fairness_dimensions
    }

    gates = [
        _gate("unique_applications", duplicates == 0, f"duplicate rows: {duplicates}"),
        _gate(
            "mature_total",
            len(mature) >= thresholds.mature_total,
            f"{len(mature)} mature / {thresholds.mature_total} required",
        ),
        _gate(
            "development_volume",
            summaries["development"]["n"] >= thresholds.development,
            f"{summaries['development']['n']} / {thresholds.development} required",
        ),
        _gate(
            "calibration_volume",
            summaries["calibration"]["n"] >= thresholds.calibration,
            f"{summaries['calibration']['n']} / {thresholds.calibration} required",
        ),
        _gate(
            "out_of_time_volume",
            summaries["out_of_time"]["n"] >= thresholds.out_of_time,
            f"{summaries['out_of_time']['n']} / {thresholds.out_of_time} required",
        ),
        _gate(
            "outcome_classes",
            all(summary["has_both_outcomes"] for summary in summaries.values()),
            "development, calibration and OOT must each contain good and bad outcomes",
        ),
        _gate(
            "temporal_breadth",
            decision_months >= thresholds.min_decision_months,
            f"{decision_months} decision months / {thresholds.min_decision_months} required",
        ),
        _gate(
            "source_coverage",
            source_coverage["average_pct"] >= thresholds.source_coverage_pct,
            f"{source_coverage['average_pct']}% / {thresholds.source_coverage_pct}% required",
        ),
        _gate(
            "ntc_ntb_outcomes",
            ntc_count >= thresholds.ntc_ntb,
            f"{ntc_count} mature NTC/NTB outcomes / {thresholds.ntc_ntb} required",
        ),
        _gate(
            "fairness_slice_support",
            all(len(supported_groups[dimension]) >= 2 for dimension in fairness_dimensions),
            f"at least two groups with >= {thresholds.min_segment} rows per monitored dimension",
        ),
    ]
    blockers = [gate for gate in gates if gate["status"] == "block"]
    return {
        "mode": "idbi_pilot_temporal_readiness",
        "contract_version": "pilot-outcome-v1",
        "as_of": as_of.isoformat(),
        "records": {
            "submitted": len(request.records),
            "mature": len(mature),
            "excluded_immature": len(request.records) - len(mature),
            "duplicate_rows": duplicates,
        },
        "splits": summaries,
        "split_integrity": {
            "chronological": True,
            "random_shuffle": False,
            "oot_is_latest_period": bool(splits["out_of_time"]),
            "decision_months": decision_months,
        },
        "source_coverage": source_coverage,
        "segment_counts": segments,
        "supported_fairness_groups": supported_groups,
        "thresholds": asdict(thresholds),
        "gates": gates,
        "blockers": blockers,
        "status": "ready_for_temporal_training" if not blockers else "blocked",
        "privacy_note": "Submitted records are validated in memory and are not persisted by this endpoint; application identifiers are never returned.",
    }
