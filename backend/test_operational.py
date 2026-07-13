from __future__ import annotations

from collections import defaultdict
from time import perf_counter

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import rate_limit as rate_limit_module
from main import app
from operational import APP_VERSION, MAX_BODY_BYTES
from rate_limit import rate_limit
from validation import ValidationRecord, build_validation_report


client = TestClient(app)
UNDERWRITER_HEADERS = {"Authorization": "Bearer saakhscore-demo-underwriter-key"}


def test_liveness_and_readiness_expose_release_and_integrity():
    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["release"]["version"] == APP_VERSION
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["runtime_allowed"] is True
    assert ready.json()["artifact_integrity"]["status"] == "pass"


def test_security_headers_trace_requests_without_weakening_app_csp():
    response = client.get(
        "/health",
        headers={"X-Request-ID": "audit-request-1234", "X-Forwarded-Proto": "https"},
    )

    assert response.headers["X-Request-ID"] == "audit-request-1234"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")
    assert response.headers["Server-Timing"].startswith("app;dur=")
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert "unsafe-inline" not in response.headers["Content-Security-Policy"]


def test_docs_csp_allows_only_the_documentation_runtime_exception():
    response = client.get("/docs")

    assert response.status_code == 200
    policy = response.headers["Content-Security-Policy"]
    assert "https://cdn.jsdelivr.net" in policy
    assert "script-src 'self' 'unsafe-inline'" in policy


def test_declared_oversized_request_is_rejected_before_parsing():
    response = client.post(
        "/score",
        content=b"{}",
        headers={
            **UNDERWRITER_HEADERS,
            "Content-Type": "application/json",
            "Content-Length": str(MAX_BODY_BYTES + 1),
            "X-Request-ID": "oversize-request-1",
        },
    )

    assert response.status_code == 413
    assert response.json()["request_id"] == "oversize-request-1"
    assert response.headers["X-Request-ID"] == "oversize-request-1"


def test_rate_limit_returns_budget_headers_and_retry_after(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "_hits", defaultdict(list))
    monkeypatch.setattr(rate_limit_module, "_last_cleanup", 0.0)
    fixture = FastAPI()

    @fixture.get("/limited", dependencies=[Depends(rate_limit(2, 60))])
    def limited():
        return {"ok": True}

    local = TestClient(fixture)
    first = local.get("/limited")
    second = local.get("/limited")
    blocked = local.get("/limited")

    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"]
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


def test_validation_metrics_handle_production_scale_without_quadratic_work():
    development = [
        ValidationRecord(
            score=90 if index % 2 == 0 else 10,
            defaulted=index % 2 == 1,
            period="development",
            reasons=["Stable reason"],
        )
        for index in range(5000)
    ]
    out_of_time = [record.model_copy(update={"period": "out-of-time"}) for record in development]

    started = perf_counter()
    report = build_validation_report(development, out_of_time)
    duration = perf_counter() - started

    assert report["metrics"]["auc"] == 1.0
    assert report["metrics"]["ks"] == 1.0
    assert duration < 2.5


def test_validation_contract_bounds_reason_codes():
    response = client.post(
        "/validation/report",
        headers=UNDERWRITER_HEADERS,
        json={
            "development": [
                {
                    "score": 50,
                    "defaulted": False,
                    "period": "dev",
                    "reasons": [f"reason-{index}" for index in range(21)],
                }
            ],
            "out_of_time": [],
        },
    )

    assert response.status_code == 422
