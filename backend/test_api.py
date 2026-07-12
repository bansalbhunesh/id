import json

from fastapi.testclient import TestClient

import audit_log
from main import app


client = TestClient(app)

UNDERWRITER_HEADERS = {"Authorization": "Bearer udyampulse-demo-underwriter-key"}
AUDITOR_HEADERS = {"Authorization": "Bearer udyampulse-demo-auditor-key"}
CUSTOM_PROFILE = {
    "name": "Audit Contract Test Co",
    "avg_monthly_inflow": 100000,
    "inflow_volatility": 0.1,
    "cheque_bounce_rate": 0.0,
    "gst_filing_streak_months": 24,
    "gst_turnover_growth_pct": 5,
    "upi_txn_count_monthly": 100,
    "unique_counterparties": 20,
    "outstanding_debt_to_inflow": 0.1,
}


def test_portfolio_endpoint_returns_impact_summary():
    response = client.get("/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["credit_unlocked"] > 0
    assert body["cases"]


def test_get_score_is_side_effect_free():
    # Regression guard: an unauthenticated GET is a view, not a decision. It
    # must never append audit events or inflate governance counts.
    before = len(audit_log.read_recent(500))
    assert client.get("/msmes/ntc_hero/score").status_code == 200
    assert client.get("/msmes/steady_wholesaler/score").status_code == 200
    after = len(audit_log.read_recent(500))
    assert after == before


def test_governance_endpoint_includes_audit_count():
    # The demo cohort is seeded once at startup, so governance is populated
    # without page loads inflating it.
    governance_response = client.get("/governance")

    assert governance_response.status_code == 200
    body = governance_response.json()
    assert body["audit"]["events_recorded"] >= 1
    assert body["controls"][0]["status"] == "Live"


def test_authenticated_decision_records_one_audit_event():
    # Only an authenticated decision writes to the audit trail, and it writes
    # exactly one event per decision.
    before = len(audit_log.read_recent(500))
    response = client.post("/score", json=CUSTOM_PROFILE, headers=UNDERWRITER_HEADERS)
    assert response.status_code == 200
    after = len(audit_log.read_recent(500))
    assert after == before + 1


def test_auditor_cannot_submit_scores():
    # Separation of duties: an auditor token must not be able to make a lending
    # decision. This is the maker-checker boundary the old rank ladder collapsed.
    response = client.post("/score", json=CUSTOM_PROFILE, headers=AUDITOR_HEADERS)
    assert response.status_code == 403


def test_underwriter_cannot_read_audit_log():
    # The inverse duty: an underwriter must not be able to read the audit trail.
    response = client.get("/audit-log", headers=UNDERWRITER_HEADERS)
    assert response.status_code == 403


def test_non_finite_numeric_inputs_are_rejected():
    # `1e309` / inf / NaN must be rejected at the validation boundary, not scored.
    body = json.dumps({**CUSTOM_PROFILE, "avg_monthly_inflow": float("inf")})
    response = client.post(
        "/score",
        content=body,
        headers={**UNDERWRITER_HEADERS, "Content-Type": "application/json"},
    )
    assert response.status_code in (400, 422)


def test_submission_proof_endpoint_exposes_backend_evidence():
    response = client.get("/submission/proof")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submission_ready_backend_proof"
    assert body["truth_boundary"]["private_idbi_data"] == "not_claimed"
    assert body["hero_reversal"]["traditional_decision"] == "Rejected"
    assert body["hero_reversal"]["alternate_data_decision"] == "Approved"
    assert body["portfolio_impact"]["credit_unlocked"] > 0
    assert body["validation_metrics"]["evidence_type"] == "held_out_model_evaluation"
    assert body["validation_metrics"]["auc"] > 0.65
    assert len(body["rubric_scorecard"]) >= 6
    assert len(body["competitor_gap_map"]) >= 5
    assert len(body["judge_runbook"]) >= 5
    assert {item["criterion"] for item in body["rubric_scorecard"]} >= {
        "Innovation",
        "Feasibility",
        "Business impact",
        "Governance readiness",
    }

    capability_layers = {item["layer"] for item in body["backend_capabilities"]}
    assert {
        "Scoring engine",
        "Explainability",
        "Sandbox ingestion",
        "Model governance",
        "Audit and memo",
    } <= capability_layers

    api_paths = {item["path"] for item in body["api_catalog"]}
    assert {
        "/sandbox/score",
        "/sandbox/recalibration/report",
        "/validation/report",
        "/governance",
        "/audit-log",
    } <= api_paths


def test_submission_proof_maps_judging_rubric_to_verifiable_routes():
    response = client.get("/submission/proof")

    assert response.status_code == 200
    body = response.json()
    rubric_evidence = {
        evidence
        for item in body["rubric_scorecard"]
        for evidence in item["evidence"]
    }
    gap_proofs = {item["proof"] for item in body["competitor_gap_map"]}
    runbook_endpoints = {item["endpoint"] for item in body["judge_runbook"]}

    assert "/submission/proof" in rubric_evidence
    assert "/msmes/ntc_hero/score" in rubric_evidence
    assert "/submission/proof" in gap_proofs
    assert {
        "/health",
        "/msmes/ntc_hero/score",
        "/governance",
        "/submission/proof",
    } <= runbook_endpoints
    assert body["truth_boundary"] == {
        "public_data": "synthetic_demo_cohort",
        "private_idbi_data": "not_claimed",
        "sandbox_access": "designed_for_post_shortlisting_api_access",
        "production_model": "public_proxy_xgboost_not_bank_calibrated; retraining_on_idbi_outcomes_required",
    }
