# Handoff - UdyamPulse

## Current state

UdyamPulse is a working IDBI Innovate 2026 PS3 PoC for MSME Financial Health Score.

What is now in the repo:

- FastAPI single-service app serving API plus static frontend.
- Banker-grade underwriter cockpit in `frontend/index.html`.
- Five-pillar score, A-E grade, risk band, eligible limit, reason codes, policy guardrails, source map, decision path, memo, and improvement plan.
- NTC/NTB rejected-vs-approved money-shot for Shree Ganesh Textiles.
- Portfolio impact endpoint (`GET /portfolio`) showing 2 NTC rescues and Rs 30,80,000 credit unlocked in the synthetic cohort.
- Governance endpoint (`GET /governance`) exposing model controls, audit count, fairness-by-bureau-history summary, and deployment notes.
- Audit log endpoint (`GET /audit-log`) for reconstructable decisions.
- Dependency-free trained linear model with exact Shapley attribution.
- Updated `README.md`, `MODEL_CARD.md`, and `.impeccable.md` design context.
- Tests expanded to 15 passing tests.

## Verified this session

Commands/results:

```bash
cd backend
..\.venv\Scripts\python -m pytest -q --basetemp ..\.pytest_tmp
# 15 passed, 1 Starlette/httpx deprecation warning
```

Runtime checks:

- `GET /health` returned `ok`.
- `GET /portfolio` returned 5 cases, 4 alternate-data approvals, 2 NTC rescues, Rs 30,80,000 credit unlocked.
- `GET /msmes/ntc_hero/score` returned traditional `Rejected`, alternate-data `Approved`, grade A, score 86, Rs 27,00,000 limit.
- Playwright browser verification against a spawned local server found no console errors, no horizontal overflow at 1366px desktop or 390px mobile, 4 impact metrics, 5 case buttons, 5 source signals, and governance controls rendered.

Note: this Codex harness reaps background uvicorn processes after tool calls. Use the command below to keep a local server open in a normal terminal.

```bash
cd backend
..\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Public/live status

- Current live URL checked: https://id-ysm9.onrender.com
- It was live and returned the old deployed app before these local changes.
- Push/redeploy is still needed for the live URL to show the new cockpit.

## Competitor research snapshot

Public search surfaced PS3 competitor repos including:

- `rohilkohli/msme-health-score`: broad React/FastAPI app shell with many routes, auth, Docker, data-source modules.
- `pixie0718/finhealth-ai`: feature-heavy owner/manager platform with loan products, dashboards, MySQL, Docker docs.
- `Abhiroop-hgv/msme-health-card`: lighter Vite prototype with mock services and default README.

Differentiation target applied here: make UdyamPulse look more bank-ready and regulator-ready than the field without adding brittle infrastructure.

## Still worth doing

1. Commit and push the local changes, then confirm Render redeploys `https://id-ysm9.onrender.com`.
2. Update `docs/PITCH_OUTLINE.md` and `docs/deck/index.html` screenshots/content to match the new cockpit and the 15-test suite.
3. Export the final deck PDF and record the 3-minute demo video required by the template.
4. Re-check the live URL in a fresh browser after deploy.
