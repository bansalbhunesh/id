from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import deployment_gate
from deployment_gate import assert_deployment_allowed, build_deployment_readiness
from main import app
from pilot_readiness import (
    PilotOutcomeRecord,
    PilotReadinessRequest,
    PilotThresholds,
    build_pilot_readiness_report,
)


client = TestClient(app)
UNDERWRITER_HEADERS = {"Authorization": "Bearer udyampulse-demo-underwriter-key"}


def _payload(index: int, decision_at: datetime) -> dict:
    granted = decision_at - timedelta(days=1)
    return {
        "consent": {
            "consent_id": f"pilot-consent-{index:04d}",
            "purpose": "msme_underwriting",
            "scope": ["account_aggregator", "gst", "upi", "epfo", "bureau"],
            "granted_at": granted.isoformat(),
            "expires_at": (granted + timedelta(days=180)).isoformat(),
        },
        "profile": {
            "name": f"Pilot MSME {index}",
            "sector": "Manufacturing" if index % 2 else "Retail",
            "district": "Pune" if index % 2 else "Surat",
            "gender": "Female" if index % 2 else "Male",
            "vintage_months": [18, 36, 72][index % 3],
        },
        "account_aggregator": {
            "monthly_inflows": [400000, 420000, 450000, 470000, 490000, 510000],
            "cheque_bounces": index % 2,
            "cheque_presentations": 40,
            "outstanding_debt": 150000,
        },
        "gst": {
            "filing_streak_months": 18,
            "trailing_6m_turnover": [390000, 410000, 430000, 450000, 480000, 500000],
        },
        "upi": {"monthly_transaction_count": 240, "unique_counterparties": 45},
        "epfo": {"employees": 12},
        "bureau": {"has_bureau_history": index % 2 == 0},
    }


def _records(count: int = 20) -> list[PilotOutcomeRecord]:
    records = []
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        decision_at = start + timedelta(days=31 * index)
        records.append(
            PilotOutcomeRecord.model_validate(
                {
                    "application_id": f"application-{index:04d}",
                    "decision_at": decision_at.isoformat(),
                    "observation_end_at": (decision_at + timedelta(days=366)).isoformat(),
                    "bad_12m": index % 2 == 1,
                    "payload": _payload(index, decision_at),
                }
            )
        )
    return records


def test_temporal_readiness_builds_true_later_period_oot_without_ids():
    records = _records()
    thresholds = PilotThresholds(
        mature_total=20,
        development=14,
        calibration=3,
        out_of_time=3,
        ntc_ntb=5,
        min_segment=1,
        min_decision_months=6,
        source_coverage_pct=80,
    )
    report = build_pilot_readiness_report(
        PilotReadinessRequest(records=records, as_of=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        thresholds=thresholds,
    )

    assert report["status"] == "ready_for_temporal_training"
    assert report["splits"]["development"]["n"] == 14
    assert report["splits"]["calibration"]["n"] == 3
    assert report["splits"]["out_of_time"]["n"] == 3
    assert report["splits"]["development"]["decision_end"] < report["splits"]["calibration"]["decision_start"]
    assert report["splits"]["calibration"]["decision_end"] < report["splits"]["out_of_time"]["decision_start"]
    assert report["split_integrity"]["random_shuffle"] is False
    assert "application-" not in str(report)


def test_temporal_readiness_blocks_duplicates_and_immature_labels():
    records = _records(6)
    records[1] = records[1].model_copy(update={"application_id": records[0].application_id})
    records[-1] = records[-1].model_copy(
        update={"observation_end_at": records[-1].decision_at + timedelta(days=90)}
    )
    report = build_pilot_readiness_report(PilotReadinessRequest(records=records))
    blocker_codes = {item["code"] for item in report["blockers"]}

    assert report["records"]["duplicate_rows"] == 1
    assert report["records"]["excluded_immature"] == 1
    assert "unique_applications" in blocker_codes
    assert "mature_total" in blocker_codes


def test_outcome_record_rejects_temporal_leakage():
    decision_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="observation_end_at must be after decision_at"):
        PilotOutcomeRecord.model_validate(
            {
                "application_id": "application-leak",
                "decision_at": decision_at,
                "observation_end_at": decision_at - timedelta(days=1),
                "bad_12m": False,
                "payload": _payload(1, decision_at),
            }
        )


def test_outcome_record_requires_consent_active_at_decision():
    decision_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    payload = _payload(1, decision_at)
    payload["consent"]["granted_at"] = (decision_at + timedelta(days=1)).isoformat()
    payload["consent"]["expires_at"] = (decision_at + timedelta(days=181)).isoformat()

    with pytest.raises(ValueError, match="consent must be active at decision_at"):
        PilotOutcomeRecord.model_validate(
            {
                "application_id": "application-no-consent",
                "decision_at": decision_at,
                "observation_end_at": decision_at + timedelta(days=366),
                "bad_12m": False,
                "payload": payload,
            }
        )


def test_pilot_readiness_endpoint_is_protected_and_non_persistent():
    assert client.post("/sandbox/pilot-readiness", json={"records": []}).status_code == 401
    response = client.post(
        "/sandbox/pilot-readiness",
        json={"records": []},
        headers=UNDERWRITER_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert "not persisted" in response.json()["privacy_note"]


def test_outcome_contract_is_machine_readable():
    response = client.get("/sandbox/outcome-contract")
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "pilot-outcome-v1"
    assert body["split_policy"]["random_shuffle"] is False
    assert body["privacy"]["identifiers_returned"] is False


def test_public_demo_is_allowed_but_pilot_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("UDYAMPULSE_MODE", "public_demo")
    public = build_deployment_readiness()
    assert public["runtime_allowed"] is True
    assert public["pilot_ready"] is False

    monkeypatch.setenv("UDYAMPULSE_MODE", "pilot")
    with pytest.raises(RuntimeError, match="startup blocked"):
        assert_deployment_allowed()


def test_unknown_runtime_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("UDYAMPULSE_MODE", "typo-mode")
    with pytest.raises(RuntimeError, match="invalid UDYAMPULSE_MODE"):
        assert_deployment_allowed()


def test_pilot_gate_can_pass_only_with_bank_scoped_controls(monkeypatch):
    monkeypatch.setattr(
        deployment_gate,
        "_champion_manifest",
        lambda: {"deployment_scope": "idbi_pilot", "temporal_validation": "true_oot"},
    )
    monkeypatch.setenv("UDYAMPULSE_MODE", "pilot")
    monkeypatch.setenv("UDYAMPULSE_API_KEYS", "private-underwriter:underwriter,private-auditor:auditor")
    monkeypatch.setenv("UDYAMPULSE_AUDIT_HMAC_KEY", "private-hmac-for-approved-pilot")
    monkeypatch.setenv("UDYAMPULSE_AUDIT_BACKEND", "postgres_worm")

    readiness = build_deployment_readiness()
    assert readiness["pilot_ready"] is True
    assert readiness["runtime_allowed"] is True
    assert readiness["authentication"]["secrets_exposed"] is False


def test_pilot_gate_blocks_failed_artifact_integrity(monkeypatch):
    monkeypatch.setattr(
        deployment_gate,
        "_champion_manifest",
        lambda: {"deployment_scope": "idbi_pilot", "temporal_validation": "true_oot"},
    )
    monkeypatch.setattr(
        deployment_gate,
        "_artifact_integrity",
        lambda: (False, "hash mismatch or missing evidence: xgboost_model.json"),
    )
    monkeypatch.setenv("UDYAMPULSE_MODE", "pilot")
    monkeypatch.setenv("UDYAMPULSE_API_KEYS", "private-underwriter:underwriter")
    monkeypatch.setenv("UDYAMPULSE_AUDIT_HMAC_KEY", "private-hmac-for-approved-pilot")
    monkeypatch.setenv("UDYAMPULSE_AUDIT_BACKEND", "postgres_worm")

    readiness = build_deployment_readiness()
    assert readiness["runtime_allowed"] is False
    assert {item["code"] for item in readiness["blockers"]} == {"artifact_integrity"}


def test_deployment_readiness_endpoint_exposes_blockers_without_secrets():
    response = client.get("/deployment/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "public_demo_allowed"
    assert body["pilot_ready"] is False
    assert body["blockers"]
    assert body["authentication"]["secrets_exposed"] is False
