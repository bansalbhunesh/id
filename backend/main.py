"""SaakhScore API - MSME Financial Health Card."""

from env_compat import env_setting
from pathlib import Path
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import audit_log
from auth import require_role
from deployment_gate import assert_deployment_allowed, build_deployment_readiness
from feed_ingestion import IDBISandboxPayload, readiness, to_profile
from pilot_readiness import (
    PilotReadinessRequest,
    build_pilot_readiness_report,
    outcome_contract,
)
from pilot_metrics import build_pilot_metrics
from operational import (
    APP_VERSION,
    MAX_BODY_BYTES,
    BodySizeLimitMiddleware,
    SecurityHeaderContext,
    release_metadata,
    request_id,
    security_headers as build_security_headers,
)
from consent_surface import consent_contract
from portfolio import build_governance_summary, build_portfolio_snapshot
from rails import build_ocen_offer, rails_registry
from rate_limit import rate_limit
from whatif import parse_levers, run_stress, run_whatif, run_whatif_multi
from recalibration import SandboxRecalibrationRequest, build_recalibration_report
from scoring import MSMEProfile, score_profile
from sample_data import SAMPLE_PROFILES
from screening import screen
from submission_proof import build_submission_proof
from validation import ValidationRecord, ValidationRequest, build_validation_report

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

assert_deployment_allowed()

app = FastAPI(
    title="SaakhScore",
    version=APP_VERSION,
    description=(
        "Explainable MSME credit-review and governance API for the IDBI Innovate "
        "public prototype. Public model evidence is explicitly not IDBI calibration."
    ),
    contact={"name": "Team Looper", "url": "https://github.com/bansalbhunesh/id"},
)

# The frontend is served from this same FastAPI process (StaticFiles mount
# below) so the live demo never needs CORS at all -- it's same-origin. This
# list is only for local dev (opening the frontend on a different port) and
# any future external API consumer; wildcard is gone.
_DEFAULT_ORIGINS = "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000,https://id-ysm9.onrender.com"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in env_setting("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Real body-ceiling enforcement (holds for chunked requests that declare no
# Content-Length); the header check in the security middleware is a fast-path.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Report which fields failed and why, but never echo the raw invalid input
    # back. This avoids reflecting attacker-controlled payloads and guarantees
    # the 422 body is always JSON-serialisable -- FastAPI's default handler
    # includes the offending `input`, which for a non-finite number (inf/NaN)
    # is not JSON compliant and would otherwise crash error serialisation.
    safe_errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": safe_errors,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.middleware("http")
async def security_headers(request, call_next):
    started = perf_counter()
    trace_id = request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = trace_id
    declared_size = request.headers.get("Content-Length")
    try:
        body_too_large = declared_size is not None and int(declared_size) > MAX_BODY_BYTES
    except ValueError:
        body_too_large = False
    if body_too_large:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": f"Request body exceeds the {MAX_BODY_BYTES}-byte service limit.",
                "request_id": trace_id,
            },
        )
    else:
        response = await call_next(request)
    duration_ms = (perf_counter() - started) * 1000
    content_type = response.headers.get("content-type", "")
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    context = SecurityHeaderContext(
        request_id=trace_id,
        duration_ms=duration_ms,
        is_https=request.url.scheme == "https" or forwarded_proto == "https",
        is_json=content_type.startswith("application/json"),
        path=request.url.path,
    )
    for name, value in build_security_headers(context).items():
        response.headers[name] = value
    response.headers["X-SaakhScore-Mode"] = env_setting("MODE", "public_demo")
    return response


@app.get("/health")
def health():
    deployment = build_deployment_readiness()
    return {
        "status": "ok",
        "release": release_metadata(),
        "mode": deployment["mode"],
        "pilot_ready": deployment["pilot_ready"],
    }


@app.get("/health/live")
def health_live():
    return {"status": "live", "release": release_metadata()}


@app.get("/health/ready")
def health_ready():
    from ml import model_status

    deployment = build_deployment_readiness()
    artifact_gate = next(
        gate for gate in deployment["gates"] if gate["code"] == "artifact_integrity"
    )
    return {
        "status": "ready" if deployment["runtime_allowed"] else "blocked",
        "release": release_metadata(),
        "runtime_allowed": deployment["runtime_allowed"],
        "model_provider": model_status()["active_provider"],
        "artifact_integrity": artifact_gate,
    }


@app.get("/deployment/readiness")
def deployment_readiness():
    return build_deployment_readiness()


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
    # A public, unauthenticated GET is a *view*, not a lending decision. It must
    # be safe/idempotent: browsing the demo or switching borrowers must never
    # append audit events or inflate governance counts. Real audit records come
    # only from the authenticated POST decision routes (and the one-time demo
    # seed below), so the audit trail reflects decisions, not page loads.
    return score_profile(profile, record_audit=False)


@app.get("/msmes/{msme_id}/whatif",
         dependencies=[Depends(rate_limit(max_requests=60))])
def get_whatif(msme_id: str, field: str = Query(...), value: float = Query(...)):
    profile = SAMPLE_PROFILES.get(msme_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="MSME not found")
    # Same safety contract as GET score: a hypothetical is a view, never an
    # audit event. Rate-limited because it runs the full pipeline twice.
    return run_whatif(profile, field, value)


@app.get("/msmes/{msme_id}/whatif/multi",
         dependencies=[Depends(rate_limit(max_requests=30))])
def get_whatif_multi(msme_id: str, levers: str = Query(..., max_length=500)):
    profile = SAMPLE_PROFILES.get(msme_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="MSME not found")
    # "field:value,field:value" -- same view contract as the single lever,
    # tighter rate budget because interactions invite rapid replays.
    return run_whatif_multi(profile, parse_levers(levers))


@app.get("/msmes/{msme_id}/stress",
         dependencies=[Depends(rate_limit(max_requests=30))])
def get_stress(msme_id: str):
    profile = SAMPLE_PROFILES.get(msme_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="MSME not found")
    # Fixed adverse battery over the identical pipeline; view-only.
    return run_stress(profile)


@app.get("/rails")
def get_rails():
    return rails_registry()


@app.get("/rails/ocen/offer/{msme_id}")
def get_ocen_offer(msme_id: str):
    profile = SAMPLE_PROFILES.get(msme_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="MSME not found")
    return build_ocen_offer(msme_id, score_profile(profile, record_audit=False))


@app.get("/consent/contract")
def get_consent_contract():
    return consent_contract()


@app.get("/screening/check", dependencies=[Depends(rate_limit(max_requests=60))])
def get_screening_check(
    name: str = Query(..., min_length=1, max_length=200),
    gstin: str | None = Query(default=None, max_length=15),
    pan: str | None = Query(default=None, max_length=10),
    cin: str | None = Query(default=None, max_length=21),
):
    # Advisory view over the loaded negative registries; not wired into the
    # decision path on this deployment (see screening.py docstring).
    return screen(name, gstin=gstin, pan=pan, cin=cin)


@app.post("/score", dependencies=[Depends(rate_limit(max_requests=60))])
def score_custom(
    profile: MSMEProfile,
    role: str = Depends(require_role("underwriter")),
):
    return score_profile(profile)


@app.post("/sandbox/score", dependencies=[Depends(rate_limit(max_requests=60))])
def score_sandbox_payload(
    payload: IDBISandboxPayload,
    role: str = Depends(require_role("underwriter")),
):
    if payload.consent.is_expired():
        raise HTTPException(
            status_code=403,
            detail=f"Consent {payload.consent.consent_id} expired at {payload.consent.expires_at.isoformat()}.",
        )
    profile = to_profile(payload)
    source_readiness = readiness(payload)
    missing_pillar_sources = frozenset(source_readiness["missing_sources"]) & {
        "Account Aggregator",
        "GST",
        "UPI",
    }
    result = score_profile(profile, missing_data_sources=missing_pillar_sources)
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


@app.post(
    "/sandbox/recalibration/report",
    dependencies=[Depends(rate_limit(max_requests=20))],
)
def sandbox_recalibration_report(
    request: SandboxRecalibrationRequest,
    role: str = Depends(require_role("underwriter")),
):
    return build_recalibration_report(request)


@app.get("/sandbox/outcome-contract")
def sandbox_outcome_contract():
    return outcome_contract()


@app.post(
    "/sandbox/pilot-readiness",
    dependencies=[Depends(rate_limit(max_requests=10))],
)
def sandbox_pilot_readiness(
    request: PilotReadinessRequest,
    role: str = Depends(require_role("underwriter")),
):
    return build_pilot_readiness_report(request)


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


@app.get("/model/sme-benchmark")
def get_sme_benchmark():
    from sme_benchmark import sme_benchmark

    evaluation = sme_benchmark()
    if evaluation is None:
        raise HTTPException(
            status_code=404,
            detail="No SME benchmark artifact found. Run backend/model_training/train_sme_pd_model.py.",
        )
    return evaluation


@app.get("/submission/proof")
def get_submission_proof():
    return build_submission_proof(audit_log.read_recent())


@app.post("/validation/report", dependencies=[Depends(rate_limit(max_requests=20))])
def validation_report(
    request: ValidationRequest,
    role: str = Depends(require_role("underwriter")),
):
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


def seed_demo_audit_trail() -> int:
    """Populate the audit trail once with the demo cohort so `/governance` is
    meaningful on a fresh deploy -- without letting unauthenticated browsing
    fabricate decisions. Idempotent: only seeds when the trail is empty, so it
    runs once per cold start and never grows from page loads.
    """
    if audit_log.read_recent(1):
        return 0
    seeded = 0
    for profile in SAMPLE_PROFILES.values():
        score_profile(profile, record_audit=True)
        seeded += 1
    return seeded


seed_demo_audit_trail()

# Mounted last so it doesn't shadow the API routes above -- serves the
# static frontend at "/", making this one process a single deployable unit.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
