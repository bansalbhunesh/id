# SaakhScore - Content for the Official IDBI Innovate Deck

This maps onto the IDBI Innovate prototype submission template. Keep the official visual template, but refresh screenshots and copy from the current app.

## Slide 1 - Team Details

- Team name: Looper
- Project: SaakhScore
- Problem Statement: PS3 - Financial Health Score
- One-liner: Consented alternate data in; explainable financial health card, indicative credit line, and improvement plan out.

## Slide 2 - Brief About The Idea

SaakhScore is a banker-grade MSME Financial Health Card. It turns consented alternate data - GST, UPI, Account Aggregator-style bank statements, EPFO, sector, geography, vintage, and bureau status - into an explainable 0-100 score, A-E grade, risk band, indicative credit limit, underwriter memo, and borrower improvement plan.

It is built for New-to-Credit and New-to-Bank MSMEs that traditional bureau-first underwriting rejects even when their real operating data is healthy.

## Slide 3 - Opportunities

- Difference from existing ideas: most teams and fintech demos stop at a score. SaakhScore exposes the decision path, reason codes, Shapley attribution, audit trail, policy guardrails, source map, validation metrics, pilot KPIs, and fairness monitor.
- Problem solved: it makes viable thin-file MSMEs visible to IDBI without turning model-assisted underwriting into a black box.
- USP: the rejected-to-approved NTC reversal is visible in the first minute and backed by regulator-ready evidence.

## Slide 4 - List Of Features

- Five-pillar score: Liquidity, Discipline, Momentum, Leverage, Digital Footprint.
- Traditional bureau-only verdict vs alternate-data verdict.
- Indicative working-capital limit sized from spare EMI capacity at documented policy inputs, with the grade multiple as a cap and a full `limit_basis` breakdown per decision.
- Native exact TreeSHAP from a calibrated monotonic XGBoost champion, with a calibrated dependency-free logistic fallback.
- Plain-language reason codes in English and Hindi.
- Underwriter memo.
- Borrower improvement plan.
- Policy guardrails and source map, including EWS-style monitoring signals, a counterparty-concentration limit guardrail, a GST-vs-bank turnover reconciliation guardrail (the looks-fine-on-paper red flag, both directions), and a deterministic bilingual underwriter next-best-action.
- Audit log.
- IDBI sandbox-style AA/GST/UPI/EPFO feed endpoint.
- Portfolio impact, pilot metrics, validation report, and governance endpoints.
- Fairness view by sector, geography, vintage, gender where available, and bureau-history status.

## Slide 5 - Process Flow Diagram

Draw left to right:

Consented data sources -> Sandbox feed adapter -> Feature engine -> Five-pillar score -> ML attribution -> Policy guardrails -> Credit line -> Underwriter memo + borrower plan -> Validation/governance -> Audit log.

## Slide 6 - Wireframes / Mock Diagrams

Use the first viewport of the current underwriter cockpit:

- Portfolio impact strip.
- Case queue.
- Decision pack for Shree Ganesh Textiles.
- Traditional Rejected vs SaakhScore Approved verdict boxes.

## Slide 7 - Architecture Diagram

Single-service architecture:

- FastAPI backend serving REST API and static frontend.
- `backend/scoring.py` for five-pillar policy scoring, versioned policy object, and guardrails.
- `backend/ml.py`, `backend/xgb_pd_model.py`, and `backend/pd_model.py` for the calibrated monotonic XGBoost champion, native exact TreeSHAP, and calibrated logistic fallback.
- `backend/model_training/` for the offline, reproducible dataset-to-artifact training and held-out evaluation pipeline (never imported by the serving app).
- `backend/auth.py` and `backend/rate_limit.py` for bearer-token/RBAC access control and rate limiting.
- `backend/feed_ingestion.py` for AA/GST/UPI/EPFO/Bureau payload normalization and enforced consent (purpose/scope/expiry).
- `backend/recalibration.py` for sandbox distribution profiling, outcome-label validation, and GBM/SHAP readiness checks.
- `backend/validation.py` for AUC, Gini, KS, PSI, and reason-code stability.
- `backend/pilot_metrics.py` for NTC/NTB lift, decision time, NPA guardrail, and diversification (all tagged as pilot targets, not measured results).
- `backend/agent_memo.py` for deterministic underwriter memo with optional AWS Bedrock Runtime provider.
- `backend/audit_log.py` for a hash-chained, tamper-evident, reconstructable decision log.
- `backend/portfolio.py` for impact and governance summaries with PII redaction on public routes.
- `frontend/index.html` for the no-build underwriter cockpit.

## Slide 8 - Technologies Used

Python, FastAPI, Pydantic, pytest, vanilla HTML/CSS/JS, Docker, Render web service, render.yaml Blueprint, GitHub Actions.

Stage 2 targets: live IDBI sandbox credentials and repayment labels, an IDBI-calibrated champion, SSO/KMS, durable audit storage, and production monitoring. The repo already includes feed contracts, a dated 12-month outcome schema, chronological development/calibration/OOT readiness gates, fail-closed promotion, validation metrics, fairness support checks, pilot KPIs, and optional Bedrock fallback wiring.

## Slide 9 - Estimated Implementation Cost

- Public prototype: single service, lightweight infra, synthetic data.
- Stage 2 pilot: cloud container service, managed Postgres, Bedrock usage, monitoring, and authenticated sandbox API integration.
- Cost control: deterministic memo fallback and dependency-light ML keep demo/pilot resilient.

## Slide 10 - Snapshots Of The Prototype

Use the committed screenshots from `docs/deck/assets/`:

1. First viewport of the cockpit - portfolio impact, case queue, grade A, Rs 27,00,000 limit, Traditional Rejected / SaakhScore Approved.
2. Middle of decision pack - pillar bars, reason codes, Shapley attribution, and memo.
3. Governance rail - source map, policy guardrails, audit count, validation metrics, pilot KPIs, fairness summary, and Sunrise Auto Parts improvement plan.

## Slide 11 - Prototype Performance Report / Benchmarking

- 150 automated tests passing (127 backend + 9 frontend unit + 14 Playwright e2e), plus a non-root container build/runtime/fail-closed CI job.
- Public proxy holdout evidence: ROC-AUC 0.7497 (bootstrap 95% interval 0.7314-0.7678), Gini 0.4993, KS 0.4225, Brier 0.1415, ECE 0.0122 on 4,500 untouched rows. Cross-sectional random holdout, not OOT; reproducible with `python backend/model_training/train_pd_model.py`.
- Real small-business benchmark (`GET /model/sme-benchmark`): the v2 champion is selected across 418,947 resolved real SBA 7(a) loans at natural base rates (197,716-loan train split) and validated on a true later-in-time window (FY2017-19: 114,770 loans, ROC-AUC 0.9623, KS 0.82) plus a 257k-loan recession stress cohort (ROC-AUC 0.9255), with a registry-tracked experiment programme behind it (docs/research/BENCHMARK_REPORT.md). US proxy domain, disclosed; not an IDBI calibration.
- Coverage includes scoring, input validation, grade boundaries, NTC reversal, improvement plan, hash-chained audit logging and tamper detection, consent enforcement, auth/RBAC, ML Shapley invariants, sandbox feed mapping, recalibration reports, validation metrics, portfolio impact, governance summary, and API endpoints.
- Public cohort impact (pilot targets, not measured lift): 5 synthetic MSME files, 3 alternate-data approvals, 2 NTC rescues, Rs 30,23,000 credit unlocked.
- Runtime browser verification: no console errors and no horizontal overflow at desktop or mobile widths.
- Stage 2 validation APIs: KS, AUC, Gini, PSI drift, reason-code stability, dated-outcome maturity, chronological OOT, source coverage, NTC volume, and fairness-slice support.

## Slide 12 - Additional Details / Future Development

1. Connect authenticated IDBI sandbox AA/GST/UPI/EPFO feeds to the implemented `/sandbox/score` contract.
2. Validate dated repayment outcomes through `/sandbox/pilot-readiness`, then retrain the champion/challenger pipeline offline and promote only after `/deployment/readiness` passes.
3. Enable `UDYAMPULSE_MODEL_PROVIDER=xgboost|lightgbm` and benchmark SHAP-backed GBM output against the transparent scorecard.
4. Enable AWS Bedrock memo generation in the pilot environment, with deterministic fallback already present.
5. Move policy from grade-based to PD-threshold-based (`policy-v2`), and move RBAC/audit storage from the current public-demo scope (bearer-token roles, in-memory hash-chained log) to full IDBI SSO and persistent multi-instance storage -- see `docs/SECURITY_COMPLIANCE.md` for what's already implemented versus deferred.
6. Use the implemented pilot metrics to track NTC/NTB approval lift, decision-time reduction, early-NPA guardrail, and portfolio diversification against real, not target, numbers.

## Slide 13 - Links

- GitHub repository: https://github.com/bansalbhunesh/id
- Live product link: https://id-ysm9.onrender.com
- Animated walkthrough: https://github.com/bansalbhunesh/id/blob/main/docs/demo.gif
