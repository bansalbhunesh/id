<div align="center">

# UdyamPulse

**An explainable MSME Financial Health Card that turns consented alternate data into credit decisions traditional underwriting cannot make.**

[![tests](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml/badge.svg)](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Dependencies](https://img.shields.io/badge/ML%20layer-zero%20new%20dependencies-brightgreen)
![Status](https://img.shields.io/badge/status-working%20PoC-brightgreen)

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
- Governance is live product surface: policy guardrails, model-risk controls, source map, audit count, and fairness-by-bureau-history checks.
- The NTC money-shot is quantified at portfolio level: 2 NTC rescues and Rs 30,80,000 credit unlocked in the Stage-1 synthetic cohort.
- The stack is intentionally deployable: one FastAPI process serves API plus static UI; no fragile frontend build step.
- The ML layer is inspectable: a trained dependency-free linear model with exact Shapley attribution, designed as a swap point for XGBoost/LightGBM + SHAP in Stage 2.

## What it does

1. Ingests synthetic, consented-style MSME signals across AA, GST, UPI, EPFO, bureau, geography, sector, vintage, and employment.
2. Scores five health pillars: Liquidity, Discipline, Momentum, Leverage, and Digital Footprint.
3. Produces a 0-100 score, A-E grade, risk band, and eligible working-capital limit.
4. Shows the rejected-vs-approved contrast between traditional bureau-only and alternate-data underwriting.
5. Explains every decision with plain-language reason codes and exact Shapley feature attribution.
6. Generates a stable underwriter memo and borrower improvement plan.
7. Records every scoring event in `/audit-log`.
8. Exposes portfolio impact through `/portfolio` and model-risk controls through `/governance`.

## Architecture

```text
Synthetic MSME cohort / custom MSME JSON
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
        |      deterministic underwriter memo; Stage 2 seam for AWS Bedrock
        |
        +--> backend/audit_log.py
        |      reconstructable decision trail
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
- `GET /audit-log`
- `POST /score`

## Testing

```bash
cd backend
pytest -q
```

Current suite: 15 tests covering scoring, traditional-vs-alternate verdicts, improvement plans, audit logging, ML Shapley invariants, portfolio impact, governance summaries, and API endpoints.

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

`Dockerfile` and `vercel.json` are included. The current Render deployment URL is:

[https://id-ysm9.onrender.com](https://id-ysm9.onrender.com)

## Project layout

```text
backend/              FastAPI service, scoring engine, ML layer, governance API
frontend/index.html   Static underwriter cockpit served by FastAPI
docs/deck/            Submission deck HTML
docs/PITCH_OUTLINE.md Deck content mapped to the IDBI template
docs/COMPETITIVE_RESEARCH.md Public repo scan and differentiation notes
docs/demo.gif         Recorded walkthrough
MODEL_CARD.md         Model purpose, training data, explainability, limitations
```

## Stage 2 roadmap

1. Replace synthetic data with IDBI sandbox AA/GST/UPI/EPFO feeds and recalibrate on real distributions.
2. Upgrade to XGBoost/LightGBM with SHAP on production-scale data.
3. Add out-of-time validation, KS/AUC/Gini, PSI drift monitoring, and reason-code stability checks.
4. Wire underwriter memo generation to AWS Bedrock with the deterministic memo as fallback.
5. Expand fairness monitoring by sector, geography, vintage, gender where available, and bureau-history status.
6. Pilot metrics: NTC/NTB approval lift, decision-time reduction, early-NPA guardrail, and portfolio diversification.
