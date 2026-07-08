# Model Card - UdyamPulse MSME Financial Health Model

## Purpose

UdyamPulse produces an explainable MSME financial health score, credit grade, risk band, eligible limit, reason codes, and underwriter memo from consented alternate-data signals. It is aimed at New-to-Credit and New-to-Bank enterprises that traditional bureau-based underwriting cannot evaluate fairly.

## Model type

The Stage-1 prototype intentionally uses two auditable scoring layers:

1. **Rule-based pillar scorer** (`backend/scoring.py`)
   - Five pillars: Liquidity, Discipline, Momentum, Leverage, Digital Footprint.
   - Each pillar is 0-20; total is 0-100 with A-E grade and risk band.
   - Also emits data-source signals, policy guardrails, decision path, and improvement plan.

2. **Linear PD-proxy model** (`backend/linear_model.py`, `backend/ml.py`)
   - OLS regression fit on a synthetic training set.
   - Exact Shapley attribution for a linear model: `weight_i * (x_i - mean_i)`.
   - Dependency-free implementation so the PoC remains transparent and easy to run.

The UI surfaces both layers together so an underwriter can cross-check a transparent policy score against a learned risk model.

## Training data

Training data is synthetic only (`backend/synthetic_training.py`). It is generated from a domain-informed formula plus noise and does not contain real customer or bank data.

Stage 2 should retrain and recalibrate on IDBI sandbox AA/GST/UPI/EPFO feeds under bank data-governance controls.

## Explainability

Every score returns:

- Plain-language pillar reason codes.
- Ranked Shapley feature contributions.
- Traditional bureau-only verdict and alternate-data verdict.
- Policy guardrail status.
- Decision path from bureau screen to credit-line recommendation.

This directly targets model-risk expectations around explainable, verifiable AI-assisted credit decisions.

## Auditability

Every scoring call is appended to the audit log (`backend/audit_log.py`) with timestamp, borrower name, score, grade, risk band, eligible limit, traditional verdict, alternate-data verdict, and reason codes. The audit trail is exposed through `GET /audit-log`.

The governance endpoint (`GET /governance`) exposes model version, live controls, audit count, fairness summary, and deployment notes.

## Fairness and monitoring

The Stage-1 demo includes a small synthetic cohort fairness view grouped by bureau-history status and sector (`GET /portfolio`, `GET /governance`). This is not a production fairness certification. Stage 2 should add:

- Out-of-time validation.
- Disparate-impact checks across sector, geography, vintage, and protected/proxy variables where legally available.
- Score drift and population stability index monitoring.
- Reason-code stability monitoring.

## Known limitations

- Synthetic training data means coefficients are illustrative, not production-calibrated.
- The fairness view is a demo-cohort monitor, not statistically significant.
- The deterministic underwriter memo is a stable fallback, not a live LLM call.
- The linear model is intentionally simple; Stage 2 should evaluate XGBoost/LightGBM with SHAP on real data volume.

## Intended use

Decision support for MSME credit underwriting. The current prototype should not be treated as a fully automated approve/decline system without human review.
