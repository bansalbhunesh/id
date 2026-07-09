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
- [Backend Proof](#backend-proof)
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
- Live API proof: [https://id-ysm9.onrender.com/submission/proof](https://id-ysm9.onrender.com/submission/proof)
- OpenAPI docs: [https://id-ysm9.onrender.com/docs](https://id-ysm9.onrender.com/docs)
- Walkthrough video: [docs/demo.webm](docs/demo.webm)
- Lightweight fallback: [docs/demo.gif](docs/demo.gif)
- Submission deck: [docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf](docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf)
- First-round rules check: [docs/FIRST_ROUND_RULES_CHECK.md](docs/FIRST_ROUND_RULES_CHECK.md)

What to verify in under three minutes:

1. Open the live app and keep the default Shree Ganesh Textiles case selected.
2. Compare `Traditional bureau-only: Rejected` with `UdyamPulse alternate data: Approved`.
3. Inspect the health-card pillars, reason codes, model attribution, decision path, and policy guardrails.
4. Switch to `Proof` and `Governance` to confirm audit, validation, pilot KPI, fairness, source-map, rubric, and competitor-gap proof.

## Backend Proof

The backend is not a mock response behind a polished screen. The judge can verify the product through live API surfaces:

| Proof surface | What it proves |
|---|---|
| `GET /submission/proof` | One payload summarizing the NTC reversal, truth boundary, backend capability map, judge runbook, rubric scorecard, competitor gap map, API catalog, validation metrics, controls, and Stage 2 swap points. |
| `GET /msmes/ntc_hero/score` | Full decision packet: score, grade, limit, reason codes, exact Shapley attribution, memo, guardrails, source map, and decision path. |
| `POST /sandbox/score` | AA/GST/UPI/EPFO/Bureau-style payloads normalize into the same score contract used by the cockpit. |
| `POST /sandbox/recalibration/report` | Sandbox feature distributions, source coverage, outcome labels, and GBM/SHAP readiness are profiled before model upgrade. |
| `POST /validation/report` | Out-of-time AUC, Gini, KS, PSI drift, and reason-code stability are computed from supplied records. |
| `GET /governance` | Audit count, model status, live controls, fairness slices, pilot KPIs, and deployment caveats are inspectable. |

Quick backend checks:

```bash
curl https://id-ysm9.onrender.com/submission/proof
curl https://id-ysm9.onrender.com/msmes/ntc_hero/score
curl https://id-ysm9.onrender.com/governance
```

Rubric coverage is implemented as backend data, not only README copy:

| Judge lens | Verifiable proof |
|---|---|
| Innovation | NTC bureau rejection becomes an explainable alternate-data approval with memo, reasons, guardrails, and audit. |
| Feasibility | One FastAPI service, static cockpit, Dockerfile, Render Blueprint, GitHub Actions, and no mandatory paid API dependency. |
| Scalability | Separate ingestion, scoring, attribution, validation, audit, governance, and Stage 2 model swap points. |
| Business impact | Portfolio impact, NTC rescues, credit unlocked, pilot KPIs, early-risk guardrail, and diversification measures. |
| Technical implementation | Pydantic validation, exact linear Shapley attribution, sandbox contracts, validation metrics, fairness slices, and API proof. |
| Governance readiness | Truth boundary, human review lane, audit reconstruction, drift/reason stability, model card, and deterministic memo fallback. |

## Features

- Underwriter cockpit with borrower queue, score, grade, risk band, credit-line recommendation, and decision comparison.
- Five-pillar financial health card: Liquidity, Discipline, Momentum, Leverage, and Digital Footprint.
- Exact linear Shapley attribution plus plain-language reason codes.
- Deterministic underwriter memo and borrower improvement plan; optional AWS Bedrock memo generation is a Stage 2 configuration path.
- Audit log for scoring events and governance summary endpoints.
- Sandbox-ready ingestion via `POST /sandbox/score` for AA/GST/UPI/EPFO/Bureau-style payloads.
- Recalibration and monitoring APIs for AUC, Gini, KS, PSI drift, reason-code stability, pilot KPIs, and fairness slices.

## Architecture

```mermaid
flowchart TB
  Judge["Judge / underwriter reviewer"]

  subgraph Review["Review surfaces"]
    UI["Static credit cockpit<br/>Decision, Evidence, Governance, Proof, Sources"]
    README["README + deck + model card"]
    OpenAPI["OpenAPI docs"]
  end

  subgraph FastAPI["Single FastAPI deployable"]
    Routes["main.py routes"]
    Health["/health"]
    Proof["/submission/proof<br/>rubric, runbook, gap map, truth boundary"]
    ScoreAPI["/msmes/{id}/score + /score"]
    SandboxAPI["/sandbox/score + /sandbox/recalibration/report"]
    GovernanceAPI["/governance + /portfolio + /pilot-metrics"]
    ValidationAPI["/validation/demo + /validation/report"]
    AuditAPI["/audit-log + /model/status"]
  end

  subgraph Core["Decision core"]
    Validate["Pydantic profile/feed validation"]
    Ingest["AA/GST/UPI/EPFO/Bureau feed normalization"]
    Score["Five-pillar scorecard<br/>health grade, verdict, eligible limit"]
    Explain["Exact linear Shapley attribution<br/>optional GBM/SHAP gate"]
    Memo["Deterministic memo<br/>optional Bedrock provider"]
    Audit["Reconstructable audit event"]
  end

  subgraph Controls["Governance and monitoring"]
    Portfolio["NTC rescues + credit unlocked"]
    Validation["AUC, Gini, KS, PSI, reason stability"]
    Fairness["Sector, geography, vintage, gender-ready, bureau-history slices"]
    Pilot["Approval lift, decision-time reduction, early-NPA guardrail"]
  end

  subgraph Stage2["Post-shortlisting swap points"]
    IDBI["Approved IDBI sandbox feeds"]
    Outcomes["Repayment outcomes"]
    Storage["Persistent audit storage"]
    ModelUpgrade["XGBoost/LightGBM + SHAP"]
  end

  Judge --> UI
  Judge --> README
  Judge --> OpenAPI
  UI --> Routes
  README --> Proof
  OpenAPI --> Routes
  Routes --> Health
  Routes --> Proof
  Routes --> ScoreAPI
  Routes --> SandboxAPI
  Routes --> GovernanceAPI
  Routes --> ValidationAPI
  Routes --> AuditAPI
  ScoreAPI --> Validate --> Score
  SandboxAPI --> Ingest --> Validate
  Score --> Explain --> Memo --> Audit
  Audit --> GovernanceAPI
  Score --> Portfolio
  Score --> Validation
  Score --> Fairness
  Score --> Pilot
  Portfolio --> Proof
  Validation --> Proof
  Fairness --> Proof
  Pilot --> Proof
  Audit --> Proof
  IDBI -.-> Ingest
  Outcomes -.-> Validation
  Storage -.-> Audit
  ModelUpgrade -.-> Explain
```

Important endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /msmes` and `GET /msmes/{id}/score` | Demo cohort and score packets |
| `GET /submission/proof` | Judge-facing capability, architecture, rubric, runbook, competitor-gap, and truth-boundary proof |
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

- Test suite: 30 tests covering scoring, validation, NTC reversal, improvement plans, audit logging, ML Shapley invariants, sandbox mapping, recalibration reports, validation metrics, fairness monitoring, pilot KPIs, governance summaries, submission proof, and API endpoints.
- Public cohort impact: 2 NTC rescues and Rs 30,80,000 credit unlocked in the synthetic demo cohort.
- Governance evidence: policy guardrails, source map, audit count, validation metrics, pilot KPIs, fairness slices, and model status are visible in the app.
- Backend evidence: `/submission/proof` exposes the capability map, judge runbook, route catalog, rubric scorecard, competitor gap map, architecture flow, validation metrics, controls, and Stage 2 swap points directly from backend functions.
- UI verification: desktop `1440x950` and mobile `390x900` browser smoke checks passed with no console errors, no horizontal overflow, five working review tabs, and 44px minimum interactive targets.
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
      <img src="docs/deck/assets/proof-runbook.png" width="100%" alt="Proof tab showing truth boundary, rubric scorecard, judge runbook, and backend API catalog" />
      <br />
      <strong>Judge proof tab</strong><br />
      Rubric scorecard, truth boundary, competitor gap map, runbook, and backend API catalog pulled from `/submission/proof`.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/deck/assets/mobile-live.png" width="45%" alt="Mobile UdyamPulse review flow" />
      <br />
      <strong>Mobile review</strong><br />
      Same borrower review flow compressed for a phone screen without hiding the decision evidence.
    </td>
    <td width="50%" valign="top">
      <strong>Full-resolution assets</strong><br />
      The gallery stays intentionally compact. Reviewers can open the PNGs in `docs/deck/assets/` for larger inspection.
    </td>
  </tr>
</table>

Full-resolution images remain in [docs/deck/assets](docs/deck/assets) for detailed inspection.

## Judging Proof

- Track fit: IDBI's public MSME Inclusion track asks for a Financial Health Card using alternate data for faster credit decisions and finance access for underserved MSMEs.
- Public event surface: the official public event venue found during review is [IDBI Innovate 2026 on Hack2skill](https://hack2skill.com/event/idbinnovate); no official IDBI Devpost page was found.
- Sandbox interpretation: public summaries indicate sandbox APIs, synthetic datasets, cloud resources, and mentorship are provided after shortlisting. This repo therefore ships synthetic proof data plus sandbox-ready ingestion, validation, recalibration, monitoring, and governance contracts.
- Differentiation: many PS3 demos stop at a score; UdyamPulse shows the bank decision pack around that score - rejection reversal, reasons, attribution, memo, source map, guardrails, audit, validation, pilot metrics, fairness checks, and a backend-verifiable judge proof endpoint.
- Competitive notes: [docs/COMPETITIVE_RESEARCH.md](docs/COMPETITIVE_RESEARCH.md)
- Submission checklist: [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md)

## Limitations

- Public data is synthetic and illustrative; it is not IDBI customer, sandbox, or repayment-outcome data.
- The default ML model is a transparent linear PD-proxy trained on synthetic data; optional XGBoost/LightGBM + SHAP requires approved labelled data and installed production ML packages.
- Fairness slices are demo-cohort monitors, not statistically significant production fairness certification.
- AWS Bedrock memo generation is optional and requires configured credentials and a model ID; deterministic memo generation remains the default fallback.
- UdyamPulse is decision support for underwriters, not a fully automated approve/decline system without human review.
