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
    assert body["validation_metrics"]["auc"] == 1.0

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
