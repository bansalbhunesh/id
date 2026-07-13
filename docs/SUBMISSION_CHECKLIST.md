# Submission Checklist

Use this as the final IDBI Innovate / H2S submission source of truth.

## Links

- GitHub repository: https://github.com/bansalbhunesh/id
- Live product: https://id-ysm9.onrender.com
- Demo video (YouTube): https://youtu.be/0I5BY6DKB1E
- Submission deck PDF (official IDBI Innovate template): `docs/deck/SaakhScore-IDBI-Submission-Deck.pdf` (source PPTX alongside)
- Extended deck (13-slide detail edition): `docs/deck/SaakhScore-Extended-Deck.pdf`
- Animated walkthrough: `docs/demo.gif` (browser-automation capture of the live app)

## Required Proof

- Working prototype: live Render deployment serves the underwriter cockpit and API.
- Source code: public GitHub repository with backend, frontend, tests, Dockerfile, and Render Blueprint.
- Backend proof API: `/submission/proof` exposes the truth boundary, rubric scorecard, competitor gap map, API catalog, and judge runbook.
- Pitch deck: built on the official IDBI Innovate template (all 13 required sections filled; branded cover and closers untouched).
- Demo video: narrated walkthrough at https://youtu.be/0I5BY6DKB1E, plus the committed GIF walkthrough at `docs/demo.gif`.
- Screenshots: live cockpit, decision pack, governance/evidence rail, proof tab, and mobile flow.
- Model governance: `MODEL_CARD.md`, audit log endpoint, source map, policy guardrails, validation metrics, pilot KPIs, fairness summary.
- Architecture and security posture: `docs/ARCHITECTURE.md`, `docs/SECURITY_COMPLIANCE.md`, `docs/THREAT_MODEL.md`.
- Pilot operations: `docs/PILOT_RUNBOOK.md` defines data gates, sign-off, release, rollback and evidence retention.

## Verification Gates

- Backend tests: `135 passed` (clean-venv reproducible; see pinned `backend/requirements.txt` + `backend/requirements-dev.txt`); the UI suites add 9 frontend-unit + 18 Playwright e2e tests (162 total).
- Public proxy evidence: `GET /model/evaluation` reports random-holdout AUC 0.7497 (95% bootstrap 0.7314-0.7678), Gini 0.4993, KS 0.4225, Brier 0.1415, ECE 0.0122, and explicit no-OOT-yet disclosure; reproducible via `python backend/model_training/train_pd_model.py`.
- Security: `GET /audit-log` requires the `auditor` role; CORS is allowlisted; JSON is no-store; app CSP, request tracing, body/array bounds and fail-closed promotion are tested. See `docs/SECURITY_COMPLIANCE.md`.
- Deck export: submission deck is the filled official template (15 pages including the branded cover and closing pages), exported to PDF from the PPTX; the extended deck re-exports from `docs/deck/index.html` (13 pages) after changing model evidence or screenshots.
- Browser smoke test: desktop/tablet/mobile render with no console errors, no horizontal overflow, WCAG AA Axe violations, keyboard trap, or undersized visible controls.
- Live app proof: 5 cases, 4 impact cards, 5 source signals, 5 governance controls, validation metrics, pilot KPIs, and expanded fairness slices.
- Review packet: Decision, Evidence, Model, Governance, Proof, and Sources views render from live API state in a permanent side panel and can be deep-linked with `?case=...&view=...`.
- Frontend test evidence: `node --test frontend/tests/lib.test.mjs` (9 unit) and `python -m pytest e2e -q` (18 Playwright end-to-end, self-booting server) -- including the sensitivity lab, stress battery, borrower comparison, and portfolio risk map.
- Core demo moment: Shree Ganesh Textiles is traditional `Rejected` but SaakhScore alternate-data `Approved`, grade A, score 86/100, Rs 27,00,000 indicative limit.

## Form Copy

**Project title:** SaakhScore

**One-line description:** Banker-grade MSME Financial Health Card that converts consented alternate data into explainable credit decisions, indicative limits, audit trails, and borrower improvement plans.

**Problem statement:** IDBI Innovate 2026 PS3 - MSME Financial Health Score.

**Differentiator:** Most competitor demos stop at an alternate-data score. SaakhScore shows the full bank decision pack: rejected-vs-approved reversal, reason codes, Shapley attribution, memo, source map, policy guardrails, audit log, validation metrics, pilot KPIs, governance summary, portfolio impact, and backend-verifiable proof endpoint.

**Stage 2 ask:** IDBI sandbox AA/GST/UPI/EPFO access and dated repayment outcomes. The implemented outcome contract, temporal readiness report, and fail-closed promotion gate will turn those inputs into an IDBI-scoped champion and genuine OOT evidence without weakening the public truth boundary.
