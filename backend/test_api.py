from fastapi.testclient import TestClient

import audit_log
from main import app


client = TestClient(app)


def test_portfolio_endpoint_returns_impact_summary():
    response = client.get("/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["credit_unlocked"] > 0
    assert body["cases"]


def test_governance_endpoint_includes_audit_count(monkeypatch):
    monkeypatch.setattr(audit_log, "_memory_log", [])

    score_response = client.get("/msmes/ntc_hero/score")
    governance_response = client.get("/governance")

    assert score_response.status_code == 200
    assert governance_response.status_code == 200
    body = governance_response.json()
    assert body["audit"]["events_recorded"] >= 1
    assert body["controls"][0]["status"] == "Live"


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
        "production_model": "optional_stage2_gbm_shap_requires_labelled_outcomes",
    }
