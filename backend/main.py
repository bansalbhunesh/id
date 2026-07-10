"""UdyamPulse API - MSME Financial Health Card."""
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import audit_log
from auth import require_role
from feed_ingestion import IDBISandboxPayload, readiness, to_profile
from pilot_metrics import build_pilot_metrics
from portfolio import build_governance_summary, build_portfolio_snapshot
from rate_limit import rate_limit
from recalibration import SandboxRecalibrationRequest, build_recalibration_report
from scoring import MSMEProfile, score_profile
from sample_data import SAMPLE_PROFILES
from submission_proof import build_submission_proof
from validation import ValidationRecord, ValidationRequest, build_validation_report

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="UdyamPulse", version="0.3.0")

# The frontend is served from this same FastAPI process (StaticFiles mount
# below) so the live demo never needs CORS at all -- it's same-origin. This
# list is only for local dev (opening the frontend on a different port) and
# any future external API consumer; wildcard is gone.
_DEFAULT_ORIGINS = "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000,https://id-ysm9.onrender.com"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("UDYAMPULSE_ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/msmes")
def list_msmes():
    return [
        {
            "id": key,
            "name": profile.name,
            "sector": profile.sector,
            "district": profile.district,
            "gender": profile.gender,
            "has_bureau_history": profile.has_bureau_history,
        }
        for key, profile in SAMPLE_PROFILES.items()
    ]


@app.get("/msmes/{msme_id}/score")
def get_score(msme_id: str):
    profile = SAMPLE_PROFILES.get(msme_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="MSME not found")
    return score_profile(profile)


@app.post("/score", dependencies=[Depends(rate_limit(max_requests=60))])
def score_custom(profile: MSMEProfile):
    return score_profile(profile)


@app.post("/sandbox/score", dependencies=[Depends(rate_limit(max_requests=60))])
def score_sandbox_payload(payload: IDBISandboxPayload):
    if payload.consent.is_expired():
        raise HTTPException(
            status_code=403,
            detail=f"Consent {payload.consent.consent_id} expired at {payload.consent.expires_at.isoformat()}.",
        )
    profile = to_profile(payload)
    source_readiness = readiness(payload)
    result = score_profile(profile)
    result["source_mode"] = "idbi_sandbox_payload"
    result["sandbox_readiness"] = source_readiness
    connected_sources = set(source_readiness["sources_connected"])
    for source in result["data_sources"]:
        if source["source"] == "Bureau":
            source["status"] = "Present"
        elif source["source"] in connected_sources:
            source["status"] = "Connected"
        else:
            source["status"] = "Missing"
    return result


@app.post("/sandbox/recalibration/report")
def sandbox_recalibration_report(request: SandboxRecalibrationRequest):
    return build_recalibration_report(request)


@app.get("/portfolio")
def get_portfolio():
    return build_portfolio_snapshot()


@app.get("/pilot-metrics")
def get_pilot_metrics():
    portfolio = build_portfolio_snapshot()
    return build_pilot_metrics(portfolio)


@app.get("/governance")
def get_governance():
    return build_governance_summary(audit_log.read_recent())


@app.get("/model/status")
def get_model_status():
    from ml import model_status

    return model_status()


@app.get("/model/evaluation")
def get_model_evaluation():
    from ml import model_evaluation

    evaluation = model_evaluation()
    if evaluation is None:
        raise HTTPException(
            status_code=404,
            detail="No trained PD model artifact found. Run backend/model_training/train_pd_model.py.",
        )
    evaluation = dict(evaluation)
    evaluation["evidence_type"] = "held_out_model_evaluation"
    return evaluation


@app.get("/submission/proof")
def get_submission_proof():
    return build_submission_proof(audit_log.read_recent())


@app.post("/validation/report")
def validation_report(request: ValidationRequest):
    report = build_validation_report(request.development, request.out_of_time)
    report["evidence_type"] = "submitted_batch_validation"
    return report


@app.get("/validation/demo")
def validation_demo():
    development = [
        ValidationRecord(score=82, defaulted=False, period="2026-Q1", reasons=["Strong GST filing"]),
        ValidationRecord(score=74, defaulted=False, period="2026-Q1", reasons=["Strong UPI velocity"]),
        ValidationRecord(score=66, defaulted=False, period="2026-Q1", reasons=["Strong counterparty breadth"]),
        ValidationRecord(score=54, defaulted=True, period="2026-Q1", reasons=["Watch: high leverage"]),
        ValidationRecord(score=43, defaulted=True, period="2026-Q1", reasons=["Watch: cheque bounce rate"]),
        ValidationRecord(score=35, defaulted=True, period="2026-Q1", reasons=["Watch: volatile cash flow"]),
    ]
    out_of_time = [
        ValidationRecord(score=81, defaulted=False, period="2026-Q2", reasons=["Strong GST filing"]),
        ValidationRecord(score=73, defaulted=False, period="2026-Q2", reasons=["Strong UPI velocity"]),
        ValidationRecord(score=65, defaulted=False, period="2026-Q2", reasons=["Strong counterparty breadth"]),
        ValidationRecord(score=52, defaulted=True, period="2026-Q2", reasons=["Watch: high leverage"]),
        ValidationRecord(score=44, defaulted=True, period="2026-Q2", reasons=["Watch: cheque bounce rate"]),
        ValidationRecord(score=36, defaulted=True, period="2026-Q2", reasons=["Watch: volatile cash flow"]),
    ]
    report = build_validation_report(development, out_of_time)
    report["mode"] = "demo_validation_fixture"
    report["evidence_type"] = "illustrative_fixture"
    report["evidence_note"] = (
        "This is a 6+6 hand-separated illustrative fixture, not model performance. "
        "For the trained PD model's held-out evaluation, see GET /model/evaluation."
    )
    return report


@app.get("/audit-log")
def get_audit_log(
    limit: int = Query(default=50, ge=1, le=500),
    role: str = Depends(require_role("auditor")),
):
    return audit_log.read_recent(limit)


# Mounted last so it doesn't shadow the API routes above -- serves the
# static frontend at "/", making this one process a single deployable unit.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
