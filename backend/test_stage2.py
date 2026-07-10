from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from agent_memo import generate_memo
from feed_ingestion import IDBISandboxPayload, readiness, to_profile
from main import app
from portfolio import build_governance_summary, build_portfolio_snapshot
from sample_data import SAMPLE_PROFILES
from scoring import score_profile


client = TestClient(app)
UNDERWRITER_HEADERS = {"Authorization": "Bearer udyampulse-demo-underwriter-key"}


def _consent(*, expired: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    granted = now - timedelta(days=2)
    expires = (now - timedelta(minutes=1)) if expired else (now + timedelta(days=90))
    return {
        "consent_id": "consent-demo-001",
        "purpose": "msme_underwriting",
        "scope": ["account_aggregator", "gst", "upi", "epfo", "bureau"],
        "granted_at": granted.isoformat(),
        "expires_at": expires.isoformat(),
    }


def sandbox_payload(*, expired_consent: bool = False) -> dict:
    return {
        "consent": _consent(expired=expired_consent),
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
    response = client.post("/sandbox/score", json=sandbox_payload(), headers=UNDERWRITER_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["source_mode"] == "idbi_sandbox_payload"
    assert body["profile"]["gender"] == "Female"
    assert body["sandbox_readiness"]["coverage_pct"] == 100.0
    assert {item["status"] for item in body["data_sources"]} <= {"Connected", "Present"}


def test_sandbox_score_rejects_impossible_feed_values():
    payload = sandbox_payload()
    payload["account_aggregator"]["cheque_bounces"] = 4
    payload["account_aggregator"]["cheque_presentations"] = 2

    response = client.post("/sandbox/score", json=payload, headers=UNDERWRITER_HEADERS)

    assert response.status_code == 422


def test_sandbox_score_rejects_missing_consent():
    payload = sandbox_payload()
    del payload["consent"]

    response = client.post("/sandbox/score", json=payload, headers=UNDERWRITER_HEADERS)

    assert response.status_code == 422


def test_sandbox_score_rejects_expired_consent():
    response = client.post(
        "/sandbox/score",
        json=sandbox_payload(expired_consent=True),
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 403
    assert "expired" in response.json()["detail"].lower()


def test_sandbox_score_guardrail_reflects_verified_consent():
    response = client.post("/sandbox/score", json=sandbox_payload(), headers=UNDERWRITER_HEADERS)

    assert response.status_code == 200
    guardrails = {g["control"]: g for g in response.json()["policy_guardrails"]}
    detail = guardrails["Consent data boundary"]["detail"]
    assert "Verified: consent consent-demo-001" in detail
    assert "msme_underwriting" in detail


def test_sandbox_recalibration_report_profiles_real_feed_distributions():
    development = [
        {"payload": sandbox_payload(), "defaulted": False, "period": "2026-Q1"},
        {"payload": sandbox_payload(), "defaulted": True, "period": "2026-Q1"},
    ]
    out_of_time = [
        {"payload": sandbox_payload(), "defaulted": False, "period": "2026-Q2"},
        {"payload": sandbox_payload(), "defaulted": True, "period": "2026-Q2"},
    ]

    response = client.post(
        "/sandbox/recalibration/report",
        json={"development": development, "out_of_time": out_of_time},
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "idbi_sandbox_recalibration_report"
    assert body["records"]["labelled_development"] == 2
    assert body["source_coverage"]["development"]["average_coverage_pct"] == 100.0
    assert body["feature_distributions"]["development"]["avg_monthly_inflow"]["p50"] > 0
    assert body["validation"]["metrics"]["auc"] == 0.5
    assert body["model_upgrade"]["target"] == "XGBoost/LightGBM with SHAP"
    assert body["status"] == "needs_more_sandbox_data"


def test_custom_score_rejects_negative_underwriting_features():
    response = client.post(
        "/score",
        json={
            "name": "Bad Input Traders",
            "avg_monthly_inflow": -1,
            "inflow_volatility": -0.2,
            "cheque_bounce_rate": 0.01,
            "gst_filing_streak_months": 12,
            "gst_turnover_growth_pct": 10,
            "upi_txn_count_monthly": 20,
            "unique_counterparties": 5,
            "outstanding_debt_to_inflow": 0.2,
        },
        headers=UNDERWRITER_HEADERS,
    )

    assert response.status_code == 422


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

    response = client.post("/validation/report", json=payload, headers=UNDERWRITER_HEADERS)

    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["auc"] == 1.0
    assert metrics["gini"] == 1.0
    assert metrics["ks"] >= 0.5
    assert "psi" in metrics
    assert metrics["reason_code_stability"] == 1.0
    assert response.json()["status"] == "insufficient_sample"
    assert response.json()["warnings"]


def test_validation_report_flags_missing_outcome_classes():
    payload = {
        "development": [
            {"score": 82, "defaulted": False, "period": "dev", "reasons": ["Strong GST"]},
        ],
        "out_of_time": [
            {"score": 78, "defaulted": False, "period": "oot", "reasons": ["Strong GST"]},
        ],
    }

    response = client.post("/validation/report", json=payload, headers=UNDERWRITER_HEADERS)

    assert response.status_code == 200
    assert "both defaulted and non-defaulted" in " ".join(response.json()["warnings"])


def test_portfolio_snapshot_has_stage2_fairness_and_pilot_kpis():
    snapshot = build_portfolio_snapshot()

    assert "pilot_metrics" in snapshot
    assert snapshot["pilot_metrics"]["decision_time_reduction_pct"]["status"] == "pilot_target"
    assert snapshot["pilot_metrics"]["decision_time_reduction_pct"]["value"] > 90
    assert snapshot["fairness"]["by_sector"]
    assert snapshot["fairness"]["by_geography"]
    assert snapshot["fairness"]["by_vintage"]
    assert snapshot["fairness"]["by_gender"]
    assert len(snapshot["fairness"]["by_bureau_history"]) == 2


def test_governance_summary_includes_validation_and_pilot_controls():
    summary = build_governance_summary([])
    controls = {item["control"] for item in summary["controls"]}

    assert "Holdout and future OOT validation" in controls
    assert "Fairness monitor" in controls
    assert "pilot_metrics" in summary


def test_model_status_endpoint_exposes_runtime_provider():
    response = client.get("/model/status")

    assert response.status_code == 200
    assert response.json()["active_provider"] in {
        "logistic_pd_v2",
        "logistic_pd_v2_fallback",
        "xgboost_pd_proxy_v1",
        "linear_synthetic_fallback",
    }


def test_bedrock_memo_provider_falls_back_without_model_id(monkeypatch):
    monkeypatch.setenv("UDYAMPULSE_MEMO_PROVIDER", "bedrock")
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_BEDROCK_MODEL_ID", raising=False)
    score = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)

    memo = generate_memo(score)

    assert score["name"] in memo
    assert "eligible limit" in memo


AUDITOR_HEADERS = {"Authorization": "Bearer udyampulse-demo-auditor-key"}


def test_audit_log_limit_is_validated():
    response = client.get("/audit-log?limit=0", headers=AUDITOR_HEADERS)

    assert response.status_code == 422


def test_audit_log_requires_authentication():
    response = client.get("/audit-log")

    assert response.status_code == 401


def test_audit_log_rejects_bad_key():
    response = client.get("/audit-log", headers={"Authorization": "Bearer not-a-real-key"})

    assert response.status_code == 401


def test_audit_log_accepts_demo_auditor_key():
    response = client.get("/audit-log", headers=AUDITOR_HEADERS)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_governance_redacts_latest_borrower_name():
    client.post("/score", json={
        "name": "Should Not Leak Pvt Ltd",
        "avg_monthly_inflow": 100000,
        "inflow_volatility": 0.1,
        "cheque_bounce_rate": 0.0,
        "gst_filing_streak_months": 24,
        "gst_turnover_growth_pct": 5,
        "upi_txn_count_monthly": 100,
        "unique_counterparties": 20,
        "outstanding_debt_to_inflow": 0.1,
    }, headers=UNDERWRITER_HEADERS)

    response = client.get("/governance")

    assert response.status_code == 200
    latest = response.json()["audit"]["latest_decision"]
    if latest is not None:
        assert "Should Not Leak Pvt Ltd" not in latest.get("name", "")


def test_model_evaluation_exposes_real_held_out_metrics():
    response = client.get("/model/evaluation")

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_type"] == "held_out_model_evaluation"
    holdout = body["splits"]["holdout"]
    assert holdout["auc"] > 0.65
    assert holdout["n"] > 1000
    assert "not an out-of-time" in body["validation_design"]


def test_protected_scoring_requires_underwriter_role():
    response = client.post("/sandbox/score", json=sandbox_payload())
    assert response.status_code == 401


def test_sandbox_scope_must_cover_supplied_feeds():
    payload = sandbox_payload()
    payload["consent"]["scope"].remove("gst")
    response = client.post(
        "/sandbox/score", json=payload, headers=UNDERWRITER_HEADERS
    )
    assert response.status_code == 422
    assert "does not cover supplied feeds" in response.text
