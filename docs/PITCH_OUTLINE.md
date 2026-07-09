# UdyamPulse - Content for the Official IDBI Innovate Deck

This maps onto the IDBI Innovate prototype submission template. Keep the official visual template, but refresh screenshots and copy from the current app.

## Slide 1 - Team Details

- Team name: Looper
- Project: UdyamPulse
- Problem Statement: PS3 - Financial Health Score
- One-liner: Consented alternate data in; explainable financial health card, eligible credit line, and improvement plan out.

## Slide 2 - Brief About The Idea

UdyamPulse is a banker-grade MSME Financial Health Card. It turns consented alternate data - GST, UPI, Account Aggregator-style bank statements, EPFO, sector, geography, vintage, and bureau status - into an explainable 0-100 score, A-E grade, risk band, eligible credit limit, underwriter memo, and borrower improvement plan.

It is built for New-to-Credit and New-to-Bank MSMEs that traditional bureau-first underwriting rejects even when their real operating data is healthy.

## Slide 3 - Opportunities

- Difference from existing ideas: most teams and fintech demos stop at a score. UdyamPulse exposes the decision path, reason codes, Shapley attribution, audit trail, policy guardrails, source map, validation metrics, pilot KPIs, and fairness monitor.
- Problem solved: it makes viable thin-file MSMEs visible to IDBI without turning AI into a black box.
- USP: the rejected-to-approved NTC reversal is visible in the first minute and backed by regulator-ready evidence.

## Slide 4 - List Of Features

- Five-pillar score: Liquidity, Discipline, Momentum, Leverage, Digital Footprint.
- Traditional bureau-only verdict vs alternate-data verdict.
- Eligible working-capital limit.
- Exact Shapley attribution from a trained dependency-free linear model.
- Plain-language reason codes.
- Underwriter memo.
- Borrower improvement plan.
- Policy guardrails and source map.
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
- Traditional Rejected vs UdyamPulse Approved verdict boxes.

## Slide 7 - Architecture Diagram

Single-service architecture:

- FastAPI backend serving REST API and static frontend.
- `backend/scoring.py` for five-pillar policy scoring and guardrails.
- `backend/ml.py` and `backend/linear_model.py` for trained Shapley attribution.
- `backend/feed_ingestion.py` for AA/GST/UPI/EPFO/Bureau payload normalization.
- `backend/validation.py` for AUC, Gini, KS, PSI, and reason-code stability.
- `backend/pilot_metrics.py` for NTC/NTB lift, decision time, NPA guardrail, and diversification.
- `backend/agent_memo.py` for deterministic underwriter memo with optional AWS Bedrock Runtime provider.
- `backend/audit_log.py` for reconstructable decision events.
- `backend/portfolio.py` for impact and governance summaries.
- `frontend/index.html` for the no-build underwriter cockpit.

## Slide 8 - Technologies Used

Python, FastAPI, Pydantic, pytest, vanilla HTML/CSS/JS, Docker, Render web service, render.yaml Blueprint, GitHub Actions.

Stage 2 targets: live IDBI sandbox credentials and repayment labels, XGBoost/LightGBM, SHAP, Postgres audit store, and production monitoring. The repo already includes sandbox-style feed contracts, validation metrics, fairness slices, pilot KPIs, and optional Bedrock fallback wiring.

## Slide 9 - Estimated Implementation Cost

- Stage 1 prototype: single service, lightweight infra, synthetic data.
- Stage 2 pilot: cloud container service, managed Postgres, Bedrock usage, monitoring, and authenticated sandbox API integration.
- Cost control: deterministic memo fallback and dependency-light ML keep demo/pilot resilient.

## Slide 10 - Snapshots Of The Prototype

Use the committed screenshots from `docs/deck/assets/`:

1. First viewport of the cockpit - portfolio impact, case queue, grade A, Rs 27,00,000 limit, Traditional Rejected / UdyamPulse Approved.
2. Middle of decision pack - pillar bars, reason codes, Shapley attribution, and memo.
3. Governance rail - source map, policy guardrails, audit count, validation metrics, pilot KPIs, fairness summary, and Sunrise Auto Parts improvement plan.

## Slide 11 - Prototype Performance Report / Benchmarking

- 21 automated tests passing.
- Coverage includes scoring, grade boundaries, NTC reversal, improvement plan, audit logging, ML Shapley invariant, known linear coefficient recovery, sandbox feed mapping, validation metrics, portfolio impact, governance summary, and API endpoints.
- Stage-1 portfolio impact: 5 synthetic MSME files, 4 alternate-data approvals, 2 NTC rescues, Rs 30,80,000 credit unlocked.
- Runtime browser verification: no console errors and no horizontal overflow at desktop or mobile widths.
- Stage 2 validation APIs: KS, AUC, Gini, PSI drift, reason-code stability, and disparate-impact slices.

## Slide 12 - Additional Details / Future Development

1. Connect authenticated IDBI sandbox AA/GST/UPI/EPFO feeds to the implemented `/sandbox/score` contract.
2. Recalibrate score and limits on real repayment/portfolio outcomes.
3. Benchmark XGBoost/LightGBM + SHAP against the transparent scorecard.
4. Enable AWS Bedrock memo generation in the pilot environment, with deterministic fallback already present.
5. Add RBAC and persistent audit storage.
6. Use the implemented pilot metrics to track NTC/NTB approval lift, decision-time reduction, early-NPA guardrail, and portfolio diversification.

## Slide 13 - Links

- GitHub repository: https://github.com/bansalbhunesh/id
- Live product link: https://id-ysm9.onrender.com
- Recorded walkthrough: https://github.com/bansalbhunesh/id/blob/main/docs/demo.webm
