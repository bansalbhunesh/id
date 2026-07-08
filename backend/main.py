"""UdyamPulse API — MSME Financial Health Card."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import audit_log
from scoring import MSMEProfile, score_profile
from sample_data import SAMPLE_PROFILES

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="UdyamPulse", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/msmes")
def list_msmes():
    return [{"id": key, "name": profile.name} for key, profile in SAMPLE_PROFILES.items()]


@app.get("/msmes/{msme_id}/score")
def get_score(msme_id: str):
    profile = SAMPLE_PROFILES.get(msme_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="MSME not found")
    return score_profile(profile)


@app.post("/score")
def score_custom(profile: MSMEProfile):
    return score_profile(profile)


@app.get("/audit-log")
def get_audit_log(limit: int = 50):
    return audit_log.read_recent(limit)


# Mounted last so it doesn't shadow the API routes above -- serves the
# static frontend at "/", making this one process a single deployable unit.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
