<div align="center">

# UdyamPulse

**An explainable MSME Financial Health Card that turns consented alternate data into credit decisions traditional underwriting can't make.**

[![tests](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml/badge.svg)](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Dependencies](https://img.shields.io/badge/ML%20layer-zero%20new%20dependencies-brightgreen)
![License](https://img.shields.io/badge/status-working%20PoC-orange)

Built for **IDBI Innovate 2026** — Problem Statement 3: Financial Health Score · Team **Looper**

</div>

---

## The 10-second pitch

A New-to-Credit business with **zero bureau history** gets declined by every traditional lender on day one — regardless of how healthy its actual cash flow is. UdyamPulse looks at what it *can* see instead: GST filings, UPI velocity, Account Aggregator bank statements, EPFO records — and turns that into a decision a bank can defend and a borrower can act on.

| | Traditional (bureau-only) | UdyamPulse (alternate data) |
|---|:---:|:---:|
| **Shree Ganesh Textiles** (no bureau history) | ❌ **Rejected** | ✅ **Approved** — Grade A, Score 86/100 |
| Eligible credit limit | ₹0 | **₹27,00,000** |
| Reason given | "No credit bureau history on file" | 4 explicit, ranked reason codes (Shapley-attributed) |

That reversal — reproducible, explained, and audited — is the whole thesis. See it live in [`docs/demo.gif`](docs/demo.gif).

---

## Why this wins the brief

**The regulatory gap almost nobody closes.** RBI's draft Guidance on Model Risk Management (Jun 2024) requires AI-assisted credit decisions to be *"consistent, unbiased, explainable and verifiable."* Of 127 AI-using regulated entities surveyed, only **15 use SHAP/LIME-style explainability** and only **18 keep audit logs**. UdyamPulse ships both by default — not as a roadmap item, but as the core of every response.

**The market it's built for is real, not hypothetical.** India's MSME credit gap runs **₹25–30 lakh crore** (SIDBI), with only ~14% of demand met through the formal financial system — while the Account Aggregator rail alone moved **₹1.47 lakh crore** in loan disbursals in a single half-year (Apr–Sep 2025). This isn't a toy dataset problem; it's a live, government-backed data-availability problem that finally has an answer.

**Two engines, one verdict — not a black box.** A transparent, hand-inspectable rule engine and an independently trained ML model run side by side on every request. When they agree, that's confidence. When a business would be rejected on bureau data alone but approved on alternate data, that contrast is surfaced explicitly, not buried.

---

## What it actually does

1. **Ingest** consented alternate data — bank statements, GST filings, UPI trails, EPFO records (synthetic for this prototype; real IDBI sandbox feeds in Stage 2).
2. **Score** across five pillars — Liquidity, Discipline, Momentum, Leverage, Digital Footprint — into a 0–100 composite and an A–E grade.
3. **Explain** every score two ways: plain-language reason codes from the rule engine, and exact per-feature Shapley attribution from a genuinely trained ML model.
4. **Compare** verdicts — what bureau-only underwriting would decide vs. what alternate data reveals, side by side.
5. **Recommend** an eligible credit limit, a plain-language underwriter memo, and a concrete improvement plan (which lever to pull, and by how much your limit would rise).
6. **Audit** — every decision is appended to a queryable log (`GET /audit-log`), because a decision nobody can reconstruct isn't a decision a regulator will accept.

## Architecture

```
MSME data (synthetic, or AA/GST/UPI/EPFO in Stage 2)
        |
        v
  backend/scoring.py  --  5-pillar rule-based score (0-100, A-E grade)
        |                       |
        |                       v
        |              backend/ml.py  --  linear PD-proxy model,
        |              exact Shapley (SHAP-equivalent) reason codes
        |                       |
        +-----------------------+
        v
  backend/agent_memo.py  --  plain-language underwriter memo
        |
        v
  backend/audit_log.py  --  every decision recorded (GET /audit-log)
        |
        v
  frontend/index.html  --  health card, traditional-vs-alternate verdict,
                            AI risk model reasons, memo, improvement plan
```

One process, single deployable service — FastAPI serves the API and the static frontend together (`Dockerfile` + `vercel.json` both ready to go).

**A deliberate engineering choice, not a corner cut:** the ML layer is a from-scratch linear model (OLS via pure-Python Gauss-Jordan elimination) with **exact closed-form Shapley attribution** — mathematically identical to what the `shap` library produces for a linear model, with zero external dependencies. It's a genuinely trained, genuinely explainable model, and the interface (`fit` / `predict` / `shap_contributions`) is designed as a drop-in swap point for XGBoost/LightGBM + `shap` once real transaction volume justifies it.

See [`MODEL_CARD.md`](MODEL_CARD.md) for training data, explainability approach, and known limitations.

## Quick start

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://localhost:8000` — FastAPI serves both the API and the frontend together. (Opening `frontend/index.html` directly also works and auto-detects the local API.)

## Testing & CI

```bash
cd backend
pytest -q
```

11 tests covering the scoring logic, ML weight recovery against known linear relationships, the Shapley-sum invariant, the traditional-vs-alternate verdict, the improvement plan, and audit logging — enforced by GitHub Actions on every push.

## Deploy

Single-service, one process — any container host works:

```bash
docker build -t udyampulse .
docker run -p 8000:8000 udyampulse
```

Or directly, on any platform that runs a `Procfile`-style start command (working directory `backend/`):

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Project layout

```
backend/          FastAPI service — scoring engine, ML layer, API
frontend/          Static demo UI (single page, no build step)
docs/deck/          The submission deck (self-contained, print-to-PDF ready)
docs/PITCH_OUTLINE.md  Deck content mapped to IDBI's official template
docs/demo.gif       Recorded walkthrough of the live app
MODEL_CARD.md       Model purpose, training data, explainability, limitations
```

## Stage 2 roadmap

Once shortlisted, the path from PoC to pilot is already scoped:

1. Swap synthetic data for real IDBI sandbox AA/GST/UPI/EPFO feeds; recalibrate on real distributions.
2. Upgrade to a gradient-boosted model (XGBoost/LightGBM) with the `shap` library at production data volume.
3. Add fairness/disparate-impact auditing across sector and geography, plus score-drift (PSI) monitoring.
4. Wire the underwriter memo to AWS Bedrock for richer narratives.
5. Report **KS statistic, AUC, and Gini coefficient** — the correct metrics for imbalanced credit risk, not raw accuracy.
6. Pilot metrics: approval-rate lift on NTC/NTB, decision-time reduction, early-NPA guardrail — quantified against IDBI's book.

## Links

- **Repository:** [github.com/bansalbhunesh/id](https://github.com/bansalbhunesh/id) (public)
- **Submission deck:** [`docs/deck/index.html`](docs/deck/index.html)
- **Demo walkthrough:** [`docs/demo.gif`](docs/demo.gif)
- **Model card:** [`MODEL_CARD.md`](MODEL_CARD.md)

---

<div align="center">

*Working PoC. See <a href="NEXT_SESSION_HANDOFF.md">NEXT_SESSION_HANDOFF.md</a> for current status and next steps.*

</div>
