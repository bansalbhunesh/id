# Handoff - UdyamPulse

## Current State

UdyamPulse is a competition-ready IDBI Innovate 2026 PS3 prototype for MSME Financial Health Score.

What is in the repo:

- FastAPI single-service app serving API plus static frontend.
- Banker-grade underwriter cockpit in `frontend/index.html`.
- Five-pillar score, A-E grade, risk band, eligible limit, reason codes, EWS-style monitoring signals, policy guardrails, source map, decision path, underwriter next-best-action, memo, and improvement plan.
- A sandbox source the caller never connects always routes to mandatory review instead of being scored as worst-case; a counterparty-concentration guardrail reduces the eligible limit 15% when a single buyer accounts for 40%+ of digital inflow value; a generative memo that contradicts the computed score/grade/limit is rejected in favour of the deterministic fallback.
- NTC/NTB rejected-vs-approved money-shot for Shree Ganesh Textiles.
- Portfolio impact endpoint (`GET /portfolio`) showing 2 NTC rescues and Rs 30,80,000 credit unlocked in the synthetic cohort.
- Governance endpoint (`GET /governance`) exposing model controls, audit count, fairness-by-bureau-history summary, and deployment notes.
- Audit log endpoint (`GET /audit-log`) for reconstructable decisions.
- Calibrated monotonic XGBoost champion with native exact TreeSHAP, calibrated logistic fallback, and score/PD/policy separation -- see MODEL_CARD.md and docs/ARCHITECTURE.md.
- `MODEL_CARD.md`, `docs/COMPETITIVE_RESEARCH.md`, `docs/SUBMISSION_CHECKLIST.md`, and `docs/DEMO_SCRIPT.md`.
- `SECURITY.md` at the repo root pointing to `docs/THREAT_MODEL.md`/`docs/SECURITY_COMPLIANCE.md`.
- All Mermaid diagrams (README, ARCHITECTURE, THREAT_MODEL, PILOT_RUNBOOK) have committed SVG fallbacks under `docs/diagrams/` so they render regardless of viewer.
- Submission deck source and PDF under `docs/deck/` (screenshots and PDF regenerated 11 July 2026 against the current build).
- Render Blueprint at `render.yaml`.
- 83 passing tests; RBAC; scoped consent; genesis-anchored audit; request/resource controls; dated pilot-outcome and temporal/OOT readiness gates; fail-closed pilot promotion; random-holdout proxy evidence at `GET /model/evaluation` (AUC 0.7497, explicitly not OOT). See `docs/ARCHITECTURE.md` and `docs/SECURITY_COMPLIANCE.md`.

An independent technical audit (`IDBI_EXTERNAL_TECHNICAL_AUDIT.md`, outside this repo, in the parent working directory) scores the current build at 85/100 and, after deep hands-on verification of the two nearest rivals, places it ahead of both: TRINETRA (Track 4, verified 70/100) and ArthNiti (Track 3, verified 51/100).

## Verified

Backend tests:

```bash
cd backend
..\.venv\Scripts\python -m pytest -q --basetemp ..\.pytest_tmp2
# 83 passed, 2 warnings (third-party Starlette TestClient deprecation notice, pytest cache dir)
```

Note: `backend/.pytest_tmp` at the repo root may be a permission-locked leftover on some machines (unrelated to the code); point `--basetemp` at a fresh directory name if `rm_rf` warnings appear.

Full model-evidence pipeline (reproducible, byte-identical on re-run):

```bash
cd backend/model_training
pip install -r requirements-training.txt
python train_pd_model.py
```

Deck/export checks (11 July 2026):

- `docs/deck/index.html` renders 13 slides.
- Screenshots re-captured against the current build (`decision-pack.png`, `governance-evidence.png`, `proof-runbook.png`, `live-cockpit-viewport.png`) so they show the EWS signals and next-best-action sections.
- `docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf` regenerated: 13 pages, not encrypted.

Live app checks:

- Live URL: https://id-ysm9.onrender.com
- `GET /health` on the live URL reports the exact latest commit hash -- auto-deploy confirmed current, not stale.
- Chrome/Puppeteer-driven desktop and mobile checks found no console errors and no horizontal overflow.
- Live cockpit rendered 4 impact metrics, 5 borrower cases, 5 source signals, 4 governance controls, and the Rejected -> Approved NTC reversal.

## Submission Links

- GitHub: https://github.com/bansalbhunesh/id
- Live product: https://id-ysm9.onrender.com
- Deck PDF: `docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf`
- Recorded walkthrough video: `docs/demo.webm`
- Lightweight walkthrough fallback: `docs/demo.gif`
- Demo narration script: `docs/DEMO_SCRIPT.md`

## Remaining Human Step

Submit the final form with the GitHub URL, live product URL, deck PDF, and `docs/demo.webm`. If the form requires hosted video instead of a repository file, upload `docs/demo.webm` and paste that hosted link. `docs/demo.webm`/`docs/demo.gif` were not re-recorded this session -- they predate the newest features and may be worth refreshing before submission if the walkthrough narration references specific on-screen content.
