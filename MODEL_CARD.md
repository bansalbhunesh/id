# Model Card - UdyamPulse MSME Financial Health Model

## Purpose

UdyamPulse produces an explainable MSME financial health score, credit grade, risk band, eligible limit, reason codes, and underwriter memo from consented alternate-data signals. It is aimed at New-to-Credit and New-to-Bank enterprises that traditional bureau-based underwriting cannot evaluate fairly.

## Model type

The public prototype intentionally uses two auditable scoring layers:

1. **Rule-based pillar scorer** (`backend/scoring.py`)
   - Five pillars: Liquidity, Discipline, Momentum, Leverage, Digital Footprint.
   - Each pillar is 0-20; total is 0-100 with A-E grade and risk band.
   - Also emits data-source signals, policy guardrails, decision path, and improvement plan.

2. **Linear PD-proxy model with optional GBM runtime** (`backend/linear_model.py`, `backend/ml.py`)
   - OLS regression fit on a synthetic training set.
   - Exact Shapley attribution for a linear model: `weight_i * (x_i - mean_i)`.
   - Dependency-free implementation so the PoC remains transparent and easy to run.
   - Optional `UDYAMPULSE_MODEL_PROVIDER=xgboost|lightgbm` plus `UDYAMPULSE_TRAINING_DATA` enables a production-scale SHAP-backed runtime when approved labelled data and packages are present.

The UI surfaces both layers together so an underwriter can cross-check a transparent policy score against a learned risk model.

## Training data

Training data is synthetic only (`backend/synthetic_training.py`). It is generated from a domain-informed formula plus noise and does not contain real customer or bank data.

`POST /sandbox/score` accepts IDBI sandbox-style AA/GST/UPI/EPFO/Bureau payloads and converts them into the same underwriting feature contract. The public cohort remains synthetic because the repository does not contain private IDBI sandbox credentials, customer data, or repayment labels.

`POST /sandbox/recalibration/report` accepts batches of sandbox payloads with optional repayment labels, profiles real feature distributions, reports source coverage, and checks whether labelled development/out-of-time volume is sufficient for GBM/SHAP mode. Stage 2 should retrain and recalibrate on real IDBI sandbox feeds and repayment outcomes under bank data-governance controls.

## Explainability

Every score returns:

- Plain-language pillar reason codes.
- Ranked Shapley feature contributions.
- Traditional bureau-only verdict and alternate-data verdict.
- Policy guardrail status.
- Decision path from bureau screen to credit-line recommendation.
- Optional AWS Bedrock-generated underwriter memo when configured, with deterministic fallback.

This directly targets model-risk expectations around explainable, verifiable AI-assisted credit decisions.

## Auditability

Every scoring call is appended to the audit log (`backend/audit_log.py`) with timestamp, borrower name, score, grade, risk band, eligible limit, traditional verdict, alternate-data verdict, and reason codes. The audit trail is exposed through `GET /audit-log`.

The governance endpoint (`GET /governance`) exposes model version, runtime provider, live controls, audit count, fairness summary, pilot metrics, and deployment notes. `GET /model/status` returns the active model provider and fallback reason when optional GBM/SHAP mode is not available.

## Fairness and monitoring

The demo includes a small synthetic cohort fairness view grouped by sector, geography, vintage, gender where available, and bureau-history status (`GET /portfolio`, `GET /governance`). It also reports approval-rate gaps for each dimension. This is not a production fairness certification.

Monitoring APIs now include:

- Out-of-time validation demo/report endpoints.
- AUC, Gini, and KS rank-order checks.
- PSI drift monitoring.
- Reason-code stability monitoring.
- Pilot KPI tracking for NTC/NTB lift, decision-time reduction, early-NPA guardrail, and diversification.

Production fairness sign-off still requires statistically meaningful IDBI sandbox volume and legally approved protected/proxy attributes.

## Known limitations

- Synthetic training data means coefficients are illustrative, not production-calibrated.
- The fairness view is a demo-cohort monitor, not statistically significant.
- AWS Bedrock memo generation is optional and requires configured AWS credentials plus a Bedrock model ID; the deterministic underwriter memo remains the default fallback.
- The default linear model is intentionally simple; optional XGBoost/LightGBM + SHAP mode still requires approved production-scale labelled data and installed ML packages.

## Intended use

Decision support for MSME credit underwriting. The current prototype should not be treated as a fully automated approve/decline system without human review.
