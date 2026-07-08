# UdyamPulse

AI-powered MSME Financial Health Card — built for **IDBI Innovate 2026** (Problem Statement 3: Financial Health Score).

## Problem

MSME credit evaluation relies on traditional financial documents that New-to-Credit (NTC) and New-to-Bank (NTB) enterprises often lack. Meanwhile rich alternate data (GST, UPI, Account Aggregator bank statements, EPFO) goes unused. UdyamPulse turns that consented alternate data into an explainable financial health score, an eligible credit line, and a plain-language improvement plan.

## How it works

1. **Ingest** consented alternate data (bank statements, GST filings, UPI trails, EPFO) — synthetic for the prototype.
2. **Score** across five pillars — Liquidity, Discipline, Momentum, Leverage, Digital Footprint — into a 0–100 score and A–E grade.
3. **Explain** every score with plain-language reason codes, so a thin-file business rejected by traditional scoring can see exactly why it's approved here.
4. **Recommend** an eligible credit limit and an improvement plan.

## Status

Early build. See `NEXT_SESSION_HANDOFF.md` (if present) for the latest handoff notes.

## Project layout

```
backend/     FastAPI service — scoring engine + API
frontend/    Static demo UI (single page, no build step)
tests/       pytest suite for the scoring engine
```

## Run it

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

This serves both the API and the frontend at `http://localhost:8000` (FastAPI mounts `frontend/` as static files). Opening `frontend/index.html` directly also works and auto-detects the local API.

## Deploy

Single-service, one process. Any container host works:

```bash
docker build -t udyampulse .
docker run -p 8000:8000 udyampulse
```

Or directly, on any platform that runs a `Procfile`-style start command:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

(working directory: `backend/`)

## Tests

```bash
cd backend
pytest
```
