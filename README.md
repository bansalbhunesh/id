<div align="center">

# UdyamPulse

**Explainable MSME Financial Health Card for IDBI Innovate 2026 PS3.**

[Live demo](https://id-ysm9.onrender.com) |
[Submission deck](docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf) |
[Walkthrough video](docs/demo.webm) |
[Model card](MODEL_CARD.md)

[![tests](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml/badge.svg)](https://github.com/bansalbhunesh/id/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Dependencies](https://img.shields.io/badge/ML%20layer-zero%20new%20dependencies-brightgreen)
![Status](https://img.shields.io/badge/status-first--round%20ready-brightgreen)

Built for **IDBI Innovate 2026** - Problem Statement 3: Financial Health Score - Team **Looper**

</div>

---

## Table Of Contents

- [Overview](#overview)
- [Demo](#demo)
- [Features](#features)
- [Architecture](#architecture)
- [Setup](#setup)
- [Evidence](#evidence)
- [Screenshots](#screenshots)
- [Judging Proof](#judging-proof)
- [Limitations](#limitations)

## Overview

UdyamPulse turns consented alternate-data signals into a bank-reviewable credit decision for thin-file MSMEs. The public prototype uses a synthetic cohort and sandbox-ready API contracts; it does not claim private IDBI data access.

The core demo moment is a New-to-Credit case traditional underwriting rejects because there is no bureau file. UdyamPulse approves the same business with a defensible Grade A health score, reason codes, Shapley attribution, policy guardrails, and an underwriter memo.

| Case | Traditional bureau-only | UdyamPulse alternate data |
|---|:---:|:---:|
| Shree Ganesh Textiles, no bureau file | Rejected | Approved - Grade A, Score 86/100 |
| Eligible credit limit | Rs 0 | Rs 27,00,000 |
| Explanation | No credit bureau history | Ranked reason codes, Shapley attribution, policy guardrails |

## Demo

- Live app: [https://id-ysm9.onrender.com](https://id-ysm9.onrender.com)
- Walkthrough video: [docs/demo.webm](docs/demo.webm)
- Lightweight fallback: [docs/demo.gif](docs/demo.gif)
- Submission deck: [docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf](docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf)
- First-round rules check: [docs/FIRST_ROUND_RULES_CHECK.md](docs/FIRST_ROUND_RULES_CHECK.md)

What to verify in under three minutes:

1. Open the live app and keep the default Shree Ganesh Textiles case selected.
2. Compare `Traditional bureau-only: Rejected` with `UdyamPulse alternate data: Approved`.
3. Inspect the health-card pillars, reason codes, model attribution, decision path, and policy guardrails.
4. Switch to governance/evidence and confirm audit, validation, pilot KPI, fairness, and source-map proof.

## Features

- Underwriter cockpit with borrower queue, score, grade, risk band, credit-line recommendation, and decision comparison.
- Five-pillar financial health card: Liquidity, Discipline, Momentum, Leverage, and Digital Footprint.
- Exact linear Shapley attribution plus plain-language reason codes.
- Deterministic underwriter memo and borrower improvement plan; optional AWS Bedrock memo generation is a Stage 2 configuration path.
- Audit log for scoring events and governance summary endpoints.
- Sandbox-ready ingestion via `POST /sandbox/score` for AA/GST/UPI/EPFO/Bureau-style payloads.
- Recalibration and monitoring APIs for AUC, Gini, KS, PSI drift, reason-code stability, pilot KPIs, and fairness slices.

## Architecture

```text
Synthetic demo cohort / custom MSME JSON / IDBI sandbox-style feeds
        |
        v
FastAPI scoring service
  - five-pillar scorecard and policy guardrails
  - linear PD-proxy model with exact Shapley attribution
  - sandbox feed normalization and recalibration reports
  - audit log, validation, pilot metrics, governance summaries
        |
        v
Static underwriter cockpit
  - served by the same FastAPI process
  - no frontend build step
```

Important endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /msmes` and `GET /msmes/{id}/score` | Demo cohort and score packets |
| `POST /score` | Score a custom MSME profile |
| `POST /sandbox/score` | Normalize and score sandbox-style AA/GST/UPI/EPFO/Bureau payloads |
| `POST /sandbox/recalibration/report` | Profile sandbox distributions and readiness for GBM/SHAP |
| `GET /portfolio`, `/governance`, `/pilot-metrics` | Portfolio impact and control evidence |
| `GET /validation/demo`, `POST /validation/report` | AUC, Gini, KS, PSI, and reason-code stability |
| `GET /audit-log`, `GET /model/status` | Audit trail and active model metadata |

## Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://localhost:8000`.

Run tests:

```bash
cd backend
pytest -q
```

Container deploy:

```bash
docker build -t udyampulse .
docker run -p 8000:8000 udyampulse
```

`Dockerfile` and `render.yaml` are included for a single-service Render deployment.

## Evidence

- Test suite: 28 tests covering scoring, validation, NTC reversal, improvement plans, audit logging, ML Shapley invariants, sandbox mapping, recalibration reports, validation metrics, fairness monitoring, pilot KPIs, governance summaries, and API endpoints.
- Public cohort impact: 2 NTC rescues and Rs 30,80,000 credit unlocked in the synthetic demo cohort.
- Governance evidence: policy guardrails, source map, audit count, validation metrics, pilot KPIs, fairness slices, and model status are visible in the app.
- UI verification: desktop `1440x950` and mobile `390x900` browser smoke checks passed with no console errors, no horizontal overflow, four working review tabs, and 44px minimum interactive targets.
- Model transparency: [MODEL_CARD.md](MODEL_CARD.md) documents synthetic training data, explainability, intended use, and limitations.

## Screenshots

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/deck/assets/live-cockpit-viewport.png" width="100%" alt="UdyamPulse first viewport with impact metrics, borrower queue, and NTC approval reversal" />
      <br />
      <strong>First viewport</strong><br />
      Judge path starts with the NTC rejected-to-approved reversal, service status, model mode, and portfolio impact.
    </td>
    <td width="50%" valign="top">
      <img src="docs/deck/assets/decision-pack.png" width="100%" alt="Decision pack showing score, health pillars, reason codes, memo, and policy guardrails" />
      <br />
      <strong>Decision pack</strong><br />
      Health pillars, reason codes, Shapley attribution, memo, decision path, and guardrails in one review surface.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/deck/assets/governance-evidence.png" width="100%" alt="Governance evidence view with validation, pilot KPIs, fairness checks, and source map" />
      <br />
      <strong>Governance evidence</strong><br />
      Audit count, model-risk controls, OOT validation, pilot KPIs, fairness slices, and source-map proof.
    </td>
    <td width="50%" valign="top">
      <img src="docs/deck/assets/mobile-live.png" width="45%" alt="Mobile UdyamPulse review flow" />
      <br />
      <strong>Mobile review</strong><br />
      Same borrower review flow compressed for a phone screen without hiding the decision evidence.
    </td>
  </tr>
</table>

Full-resolution images remain in [docs/deck/assets](docs/deck/assets) for detailed inspection.

## Judging Proof

- Track fit: IDBI's public MSME Inclusion track asks for a Financial Health Card using alternate data for faster credit decisions and finance access for underserved MSMEs.
- Public event surface: the official public event venue found during review is [IDBI Innovate 2026 on Hack2skill](https://hack2skill.com/event/idbinnovate); no official IDBI Devpost page was found.
- Sandbox interpretation: public summaries indicate sandbox APIs, synthetic datasets, cloud resources, and mentorship are provided after shortlisting. This repo therefore ships synthetic proof data plus sandbox-ready ingestion, validation, recalibration, monitoring, and governance contracts.
- Differentiation: many PS3 demos stop at a score; UdyamPulse shows the bank decision pack around that score - rejection reversal, reasons, attribution, memo, source map, guardrails, audit, validation, pilot metrics, and fairness checks.
- Competitive notes: [docs/COMPETITIVE_RESEARCH.md](docs/COMPETITIVE_RESEARCH.md)
- Submission checklist: [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md)

## Limitations

- Public data is synthetic and illustrative; it is not IDBI customer, sandbox, or repayment-outcome data.
- The default ML model is a transparent linear PD-proxy trained on synthetic data; optional XGBoost/LightGBM + SHAP requires approved labelled data and installed production ML packages.
- Fairness slices are demo-cohort monitors, not statistically significant production fairness certification.
- AWS Bedrock memo generation is optional and requires configured credentials and a model ID; deterministic memo generation remains the default fallback.
- UdyamPulse is decision support for underwriters, not a fully automated approve/decline system without human review.
