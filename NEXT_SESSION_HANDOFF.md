# Handoff - UdyamPulse

## Current State

UdyamPulse is a competition-ready IDBI Innovate 2026 PS3 prototype for MSME Financial Health Score.

What is in the repo:

- FastAPI single-service app serving API plus static frontend.
- Banker-grade underwriter cockpit in `frontend/index.html`.
- Five-pillar score, A-E grade, risk band, eligible limit, reason codes, policy guardrails, source map, decision path, memo, and improvement plan.
- NTC/NTB rejected-vs-approved money-shot for Shree Ganesh Textiles.
- Portfolio impact endpoint (`GET /portfolio`) showing 2 NTC rescues and Rs 30,80,000 credit unlocked in the synthetic cohort.
- Governance endpoint (`GET /governance`) exposing model controls, audit count, fairness-by-bureau-history summary, and deployment notes.
- Audit log endpoint (`GET /audit-log`) for reconstructable decisions.
- Dependency-free trained linear model with exact Shapley attribution.
- `MODEL_CARD.md`, `docs/COMPETITIVE_RESEARCH.md`, `docs/SUBMISSION_CHECKLIST.md`, and `docs/DEMO_SCRIPT.md`.
- Submission deck source and PDF under `docs/deck/`.
- Render Blueprint at `render.yaml`.
- 15 passing tests.

## Verified

Backend tests:

```bash
cd backend
..\.venv\Scripts\python -m pytest -q --basetemp ..\.pytest_tmp
# 15 passed, 1 Starlette/httpx deprecation warning
```

Deck/export checks:

- `docs/deck/index.html` renders 13 slides.
- All committed screenshot assets load.
- No missing screenshot or link gaps found in the deck text.
- `docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf` is 13 pages and not encrypted.

Live app checks:

- Live URL: https://id-ysm9.onrender.com
- Render app returned `Live`.
- Desktop and mobile Playwright smoke tests found no console errors and no horizontal overflow.
- Live cockpit rendered 4 impact metrics, 5 borrower cases, 5 source signals, 4 governance controls, and the Rejected -> Approved NTC reversal.

## Submission Links

- GitHub: https://github.com/bansalbhunesh/id
- Live product: https://id-ysm9.onrender.com
- Deck PDF: `docs/deck/UdyamPulse-IDBI-Submission-Deck.pdf`
- Recorded walkthrough GIF: `docs/demo.gif`
- Demo narration script: `docs/DEMO_SCRIPT.md`

## Remaining Human Step

Submit the final form with the GitHub URL, live product URL, deck PDF, and either the existing `docs/demo.gif` walkthrough or a voiceover recording made from `docs/DEMO_SCRIPT.md`.
