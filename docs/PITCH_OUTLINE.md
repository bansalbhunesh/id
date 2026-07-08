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

- Difference from existing ideas: most teams and fintech demos stop at a score. UdyamPulse exposes the decision path, reason codes, Shapley attribution, audit trail, policy guardrails, source map, and fairness monitor.
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
- Portfolio impact endpoint and governance endpoint.
- Fairness view by bureau-history status and sector.

## Slide 5 - Process Flow Diagram

Draw left to right:

Consented data sources -> Feature engine -> Five-pillar score -> ML attribution -> Policy guardrails -> Credit line -> Underwriter memo + borrower plan -> Audit log.

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
- `backend/agent_memo.py` for deterministic underwriter memo with AWS Bedrock seam.
- `backend/audit_log.py` for reconstructable decision events.
- `backend/portfolio.py` for impact and governance summaries.
- `frontend/index.html` for the no-build underwriter cockpit.

## Slide 8 - Technologies Used

Python, FastAPI, Pydantic, pytest, vanilla HTML/CSS/JS, Docker, Render web service, render.yaml Blueprint, GitHub Actions.

Stage 2 targets: IDBI sandbox AA/GST/UPI/EPFO APIs, AWS Bedrock, XGBoost/LightGBM, SHAP, Postgres audit store, drift and fairness monitoring.

## Slide 9 - Estimated Implementation Cost

- Stage 1 prototype: single service, lightweight infra, synthetic data.
- Stage 2 pilot: cloud container service, managed Postgres, Bedrock usage, monitoring, and sandbox API integration.
- Cost control: deterministic memo fallback and dependency-light ML keep demo/pilot resilient.

## Slide 10 - Snapshots Of The Prototype

Use the committed screenshots from `docs/deck/assets/`:

1. First viewport of the cockpit - portfolio impact, case queue, grade A, Rs 27,00,000 limit, Traditional Rejected / UdyamPulse Approved.
2. Middle of decision pack - pillar bars, reason codes, Shapley attribution, and memo.
3. Governance rail - source map, policy guardrails, audit count, fairness summary, and Sunrise Auto Parts improvement plan.

## Slide 11 - Prototype Performance Report / Benchmarking

- 15 automated tests passing.
- Coverage includes scoring, grade boundaries, NTC reversal, improvement plan, audit logging, ML Shapley invariant, known linear coefficient recovery, portfolio impact, governance summary, and API endpoints.
- Stage-1 portfolio impact: 5 synthetic MSME files, 4 alternate-data approvals, 2 NTC rescues, Rs 30,80,000 credit unlocked.
- Runtime browser verification: no console errors and no horizontal overflow at desktop or mobile widths.
- Stage 2 validation metrics: KS, AUC, Gini, PSI drift, reason-code stability, and disparate-impact checks.

## Slide 12 - Additional Details / Future Development

1. Replace synthetic fields with IDBI sandbox AA/GST/UPI/EPFO feeds.
2. Recalibrate score and limits on real repayment/portfolio outcomes.
3. Add out-of-time validation and model monitoring.
4. Wire underwriter memo generation to AWS Bedrock with deterministic fallback.
5. Add RBAC and persistent audit storage.
6. Pilot metrics: NTC/NTB approval lift, decision-time reduction, early-NPA guardrail, and portfolio diversification.

## Slide 13 - Links

- GitHub repository: https://github.com/bansalbhunesh/id
- Live product link: https://id-ysm9.onrender.com
- Recorded walkthrough: https://github.com/bansalbhunesh/id/blob/main/docs/demo.gif
