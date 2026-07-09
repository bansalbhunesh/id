from fastapi.testclient import TestClient

from agent_memo import generate_memo
from feed_ingestion import IDBISandboxPayload, readiness, to_profile
from main import app
from portfolio import build_governance_summary, build_portfolio_snapshot
from sample_data import SAMPLE_PROFILES
from scoring import score_profile


client = TestClient(app)


def sandbox_payload() -> dict:
    return {
        "consent_id": "consent-demo-001",
        "profile": {
            "name": "Asha Precision Works",
            "sector": "Manufacturing",
            "district": "Pune",
            "gender": "Female",
            "vintage_months": 42,
        },
        "account_aggregator": {
            "monthly_inflows": [480000, 510000, 535000, 560000, 590000, 625000],
            "cheque_bounces": 1,
            "cheque_presentations": 42,
            "outstanding_debt": 180000,
        },
        "gst": {
            "filing_streak_months": 18,
            "trailing_6m_turnover": [460000, 480000, 505000, 530000, 570000, 615000],
        },
        "upi": {
            "monthly_transaction_count": 310,
            "unique_counterparties": 54,
        },
        "epfo": {
            "employees": 14,
        },
        "bureau": {
            "has_bureau_history": False,
        },
    }


def test_sandbox_feed_maps_to_scoreable_profile():
    payload = IDBISandboxPayload.model_validate(sandbox_payload())
    profile = to_profile(payload)

    assert profile.name == "Asha Precision Works"
    assert profile.gender == "Female"
    assert profile.avg_monthly_inflow > 500000
    assert profile.has_bureau_history is False
    assert readiness(payload)["coverage_pct"] == 100.0


def test_sandbox_score_endpoint_marks_connected_real_feeds():
    response = client.post("/sandbox/score", json=sandbox_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["source_mode"] == "idbi_sandbox_payload"
    assert body["profile"]["gender"] == "Female"
    assert body["sandbox_readiness"]["coverage_pct"] == 100.0
    assert {item["status"] for item in body["data_sources"]} <= {"Connected", "Present"}


def test_validation_report_exposes_auc_gini_ks_psi_and_reason_stability():
    payload = {
        "development": [
            {"score": 82, "defaulted": False, "period": "dev", "reasons": ["Strong GST"]},
            {"score": 74, "defaulted": False, "period": "dev", "reasons": ["Strong UPI"]},
            {"score": 48, "defaulted": True, "period": "dev", "reasons": ["Watch leverage"]},
            {"score": 35, "defaulted": True, "period": "dev", "reasons": ["Watch volatility"]},
        ],
        "out_of_time": [
            {"score": 78, "defaulted": False, "period": "oot", "reasons": ["Strong GST"]},
            {"score": 69, "defaulted": False, "period": "oot", "reasons": ["Strong UPI"]},
            {"score": 44, "defaulted": True, "period": "oot", "reasons": ["Watch leverage"]},
            {"score": 31, "defaulted": True, "period": "oot", "reasons": ["Watch volatility"]},
        ],
    }

    response = client.post("/validation/report", json=payload)

    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["auc"] == 1.0
    assert metrics["gini"] == 1.0
    assert metrics["ks"] >= 0.5
    assert "psi" in metrics
    assert metrics["reason_code_stability"] == 1.0


def test_portfolio_snapshot_has_stage2_fairness_and_pilot_kpis():
    snapshot = build_portfolio_snapshot()

    assert "pilot_metrics" in snapshot
    assert snapshot["pilot_metrics"]["decision_time_reduction_pct"] > 90
    assert snapshot["fairness"]["by_sector"]
    assert snapshot["fairness"]["by_geography"]
    assert snapshot["fairness"]["by_vintage"]
    assert snapshot["fairness"]["by_gender"]
    assert len(snapshot["fairness"]["by_bureau_history"]) == 2


def test_governance_summary_includes_validation_and_pilot_controls():
    summary = build_governance_summary([])
    controls = {item["control"] for item in summary["controls"]}

    assert "Out-of-time validation" in controls
    assert "Fairness monitor" in controls
    assert "pilot_metrics" in summary


def test_bedrock_memo_provider_falls_back_without_model_id(monkeypatch):
    monkeypatch.setenv("UDYAMPULSE_MEMO_PROVIDER", "bedrock")
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_BEDROCK_MODEL_ID", raising=False)
    score = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)

    memo = generate_memo(score)

    assert score["name"] in memo
    assert "eligible limit" in memo
