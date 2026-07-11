# Submission Checklist

Use this as the final IDBI Innovate / H2S submission source of truth.

## Links

- GitHub repository: https://github.com/bansalbhunesh/id
- Live product: https://id-ysm9.onrender.com
- Submission deck PDF: `docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf`
- Recorded walkthrough video: `docs/demo.webm`
- Lightweight walkthrough fallback: `docs/demo.gif`
- Demo script for voiceover/video: `docs/DEMO_SCRIPT.md`

## Required Proof

- Working prototype: live Render deployment serves the underwriter cockpit and API.
- Source code: public GitHub repository with backend, frontend, tests, Dockerfile, and Render Blueprint.
- Backend proof API: `/submission/proof` exposes the truth boundary, rubric scorecard, competitor gap map, API catalog, and judge runbook.
- Pitch deck: 13-slide deck mapped to the IDBI template sections.
- Demo video: captioned WebM walkthrough recorded from the live Render app.
- Screenshots: live cockpit, decision pack, governance/evidence rail, proof tab, and mobile flow.
- Model governance: `MODEL_CARD.md`, audit log endpoint, source map, policy guardrails, validation metrics, pilot KPIs, fairness summary.
- Architecture and security posture: `docs/ARCHITECTURE.md`, `docs/SECURITY_COMPLIANCE.md`, `docs/THREAT_MODEL.md`.
- Pilot operations: `docs/PILOT_RUNBOOK.md` defines data gates, sign-off, release, rollback and evidence retention.
- Competitor research: `docs/COMPETITIVE_RESEARCH.md`.

## Verification Gates

- Backend tests: `69 passed` (clean-venv reproducible; see `backend/requirements.txt` pinned versions).
- Public proxy evidence: `GET /model/evaluation` reports random-holdout AUC 0.7497 (95% bootstrap 0.7314-0.7678), Gini 0.4993, KS 0.4225, Brier 0.1415, ECE 0.0122, and explicit no-OOT-yet disclosure; reproducible via `python backend/model_training/train_pd_model.py`.
- Security: `GET /audit-log` requires the `auditor` role; CORS is allowlisted; JSON is no-store; app CSP, request tracing, body/array bounds and fail-closed promotion are tested. See `docs/SECURITY_COMPLIANCE.md`.
- Deck export: 13 pages, not encrypted. Re-export from the refreshed `docs/deck/index.html` after changing model evidence or screenshots.
- Browser smoke test: desktop/tablet/mobile render with no console errors, no horizontal overflow, WCAG AA Axe violations, keyboard trap, or undersized visible controls.
- Live app proof: 5 cases, 4 impact cards, 5 source signals, 5 governance controls, validation metrics, pilot KPIs, and expanded fairness slices.
- Proof tab: Decision, Evidence, Governance, Proof, and Sources views render from live API state and can be deep-linked with `?case=...&view=...`.
- Core demo moment: Shree Ganesh Textiles is traditional `Rejected` but UdyamPulse alternate-data `Approved`, grade A, score 86/100, Rs 27,00,000 eligible limit.

## Form Copy

**Project title:** UdyamPulse

**One-line description:** Banker-grade MSME Financial Health Card that converts consented alternate data into explainable credit decisions, eligible limits, audit trails, and borrower improvement plans.

**Problem statement:** IDBI Innovate 2026 PS3 - MSME Financial Health Score.

**Differentiator:** Most competitor demos stop at an alternate-data score. UdyamPulse shows the full bank decision pack: rejected-vs-approved reversal, reason codes, Shapley attribution, memo, source map, policy guardrails, audit log, validation metrics, pilot KPIs, governance summary, portfolio impact, and backend-verifiable proof endpoint.

**Stage 2 ask:** IDBI sandbox AA/GST/UPI/EPFO access and dated repayment outcomes. The implemented outcome contract, temporal readiness report, and fail-closed promotion gate will turn those inputs into an IDBI-scoped champion and genuine OOT evidence without weakening the public truth boundary.
