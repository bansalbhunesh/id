<div align="center">

# UdyamPulse

**An explainable MSME Financial Health Card that turns consented alternate data into credit decisions traditional underwriting cannot make.**

[![tests](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml/badge.svg)](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Dependencies](https://img.shields.io/badge/ML%20layer-zero%20new%20dependencies-brightgreen)
![Status](https://img.shields.io/badge/status-stage2--ready%20PoC-brightgreen)

Built for **IDBI Innovate 2026** - Problem Statement 3: Financial Health Score - Team **Looper**

</div>

---

## The 10-second pitch

A New-to-Credit business with zero bureau history gets declined by a traditional lender on day one, even when its real cash-flow data is strong. UdyamPulse uses consented alternate data signals - GST, UPI, Account Aggregator-style bank statements, EPFO, and Udyam-like profile data - to produce a decision a bank can defend and a borrower can act on.

| | Traditional bureau-only | UdyamPulse alternate data |
|---|:---:|:---:|
| Shree Ganesh Textiles, no bureau file | Rejected | Approved - Grade A, Score 86/100 |
| Eligible credit limit | Rs 0 | Rs 27,00,000 |
| Reason given | No credit bureau history | Ranked reason codes, Shapley attribution, policy guardrails |

That reversal is reproducible, explained, audited, and visible on the first screen of the live app.

## Why this can beat the field

Most PS3 competitors converge on "MSME score + alternate data + SHAP." UdyamPulse pushes the demo further into what a bank judge actually scores:

- A banker cockpit, not just a score card: case queue, traditional-vs-alternate decision, limit recommendation, decision path, pillar bars, memo, and improvement plan.
- Governance is live product surface: policy guardrails, model-risk controls, source map, audit count, out-of-time validation metrics, pilot KPIs, and fairness slices.
- The NTC money-shot is quantified at portfolio level: 2 NTC rescues and Rs 30,80,000 credit unlocked in the Stage-1 synthetic cohort.
- The stack is intentionally deployable: one FastAPI process serves API plus static UI; no fragile frontend build step.
- The ML layer is inspectable: a trained dependency-free linear model with exact Shapley attribution, designed as a swap point for XGBoost/LightGBM + SHAP once real outcome labels arrive.

## What it does

1. Ingests the demo MSME cohort and accepts IDBI sandbox-style AA, GST, UPI, EPFO, bureau, geography, sector, vintage, gender, and employment payloads through `POST /sandbox/score`.
2. Scores five health pillars: Liquidity, Discipline, Momentum, Leverage, and Digital Footprint.
3. Produces a 0-100 score, A-E grade, risk band, and eligible working-capital limit.
4. Shows the rejected-vs-approved contrast between traditional bureau-only and alternate-data underwriting.
5. Explains every decision with plain-language reason codes and exact Shapley feature attribution.
6. Generates a stable underwriter memo and borrower improvement plan, with optional AWS Bedrock Runtime memo generation and deterministic fallback.
7. Records every scoring event in `/audit-log`.
8. Exposes portfolio impact, pilot KPIs, validation metrics, drift checks, reason-code stability, and model-risk controls through live APIs.

## Architecture

```text
Synthetic MSME cohort / custom MSME JSON / IDBI sandbox-style feeds
        |
        v
backend/scoring.py
  - five-pillar policy score
  - risk band
  - data-source signals
  - policy guardrails
  - decision path
        |
        +--> backend/ml.py / linear_model.py
        |      trained linear PD-proxy with exact Shapley attribution
        |
        +--> backend/agent_memo.py
        |      deterministic memo plus optional AWS Bedrock Runtime provider
        |
        +--> backend/audit_log.py
        |      reconstructable decision trail
        |
        +--> backend/feed_ingestion.py
        |      AA/GST/UPI/EPFO/Bureau payload normalization
        |
        +--> backend/validation.py
        |      AUC, Gini, KS, PSI, and reason-code stability checks
        |
        +--> backend/pilot_metrics.py
        |      NTC/NTB lift, decision-time reduction, NPA guardrail, diversification
        |
        +--> backend/portfolio.py
               portfolio impact and governance summary

frontend/index.html
  - static underwriter cockpit
  - no build step
  - served by the same FastAPI app
```

## Quick start

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://localhost:8000`.

Useful endpoints:

- `GET /health`
- `GET /msmes`
- `GET /msmes/ntc_hero/score`
- `GET /portfolio`
- `GET /governance`
- `GET /pilot-metrics`
- `GET /validation/demo`
- `POST /validation/report`
- `GET /audit-log`
- `POST /score`
- `POST /sandbox/score`

## Testing

```bash
cd backend
pytest -q
```

Current suite: 21 tests covering scoring, traditional-vs-alternate verdicts, improvement plans, audit logging, ML Shapley invariants, sandbox feed mapping, validation metrics, expanded fairness monitoring, pilot KPIs, governance summaries, and API endpoints.

## Deploy

Single-service container:

```bash
docker build -t udyampulse .
docker run -p 8000:8000 udyampulse
```

Direct process start:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port $PORT
```

`Dockerfile` and `render.yaml` are included for reproducible Render deployment. The current live URL is:

[https://id-ysm9.onrender.com](https://id-ysm9.onrender.com)

## Project layout

```text
backend/              FastAPI service, scoring engine, ML layer, governance API
frontend/index.html   Static underwriter cockpit served by FastAPI
docs/deck/            Submission deck HTML
docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf Submission-ready deck PDF
docs/PITCH_OUTLINE.md Deck content mapped to the IDBI template
docs/COMPETITIVE_RESEARCH.md Public repo scan and differentiation notes
docs/SUBMISSION_CHECKLIST.md Final submission links, proof, and verification gates
docs/DEMO_SCRIPT.md 3-minute demo narration and click path
docs/demo.webm        Captioned recorded walkthrough video
docs/demo.gif         Lightweight walkthrough fallback
MODEL_CARD.md         Model purpose, training data, explainability, limitations
render.yaml           Render Blueprint for the live web service
```

## Stage 2 readiness

Implemented now:

1. `/sandbox/score` accepts IDBI sandbox-style AA/GST/UPI/EPFO/Bureau payloads and normalizes them into the same scoring contract.
2. `/validation/report` and `/validation/demo` expose AUC, Gini, KS, PSI drift, and reason-code stability.
3. `/governance` expands fairness monitoring by sector, geography, vintage, gender where available, and bureau-history status.
4. `/pilot-metrics` tracks NTC/NTB approval lift, decision-time reduction, early-NPA guardrail definition, and portfolio diversification.
5. `backend/agent_memo.py` can call AWS Bedrock Runtime when configured, with deterministic memo fallback.

Requires IDBI sandbox/data-room access:

1. Replace the public synthetic demo cohort with live consented AA/GST/UPI/EPFO feeds and repayment outcomes.
2. Recalibrate limits and score bands on real distributions.
3. Train XGBoost/LightGBM with SHAP on production-scale outcomes and compare it against the transparent scorecard.
