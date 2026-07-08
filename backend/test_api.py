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
