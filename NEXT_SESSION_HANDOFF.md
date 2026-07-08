# Handoff — UdyamPulse

## What's done

Full working PoC for **IDBI Innovate 2026, Problem Statement 3 (MSME Financial Health Score)**:

- Rule-based 5-pillar scorer (`backend/scoring.py`) — 0–100 score, A–E grade, eligible credit limit.
- ML explainability layer (`backend/linear_model.py`, `backend/ml.py`) — a real, trained linear model (pure Python, zero new dependencies) with **exact closed-form Shapley attribution**.
- Traditional-vs-alternate-data verdict — the rejected→approved money-shot for thin-file (NTC/NTB) businesses.
- Borderline-improving persona + a computed **improvement plan** (weakest pillar → action → projected grade/limit uplift).
- Agentic underwriter memo (`backend/agent_memo.py`) — template-based now; documented seam to swap in AWS Bedrock later.
- Compliance layer — audit log (`backend/audit_log.py`, serverless-safe) + `MODEL_CARD.md` targeting RBI's FREE-AI/Model Risk Management draft.
- Single-service deploy: FastAPI serves the static frontend too (`Dockerfile`, `vercel.json`).
- CI (`.github/workflows/tests.yml`) running the 11-test pytest suite on every push.
- `docs/PITCH_OUTLINE.md` — rewritten to match the **actual official template** (`D:\Downloads\Prototype Submission Deck _ IDBI Innovate.pdf`), slide-by-slide, with ready-to-paste content. Important correction: the demo video requirement is **3 minutes**, not 60–90s.
- `docs/demo.gif` — a short recorded walkthrough of the live app (NTC hero rejected→approved, then the improvement plan on the borderline persona).
- **`docs/deck/index.html` — the actual 13-slide submission deck**, built to match the official template's exact section structure, self-contained (fonts embedded as base64, no external dependencies), verified via JS to have zero content overflow on any slide. Print-ready at 1280×720 (16:9) via `Ctrl+P` → Save as PDF. See `docs/deck/README.md` for exact steps.

**5 synthetic MSME personas** in `backend/sample_data.py`, including two distinct NTC/NTB stories.

Repo confirmed **public** on GitHub (template requires this). All 16 commits pushed to `git@github.com:bansalbhunesh/id.git` (main branch). Working tree is clean.

## What's left (blocked on your credentials/hands, or on a safety constraint I won't cross)

1. **Live deployment** — needs your GitHub OAuth consent in the Vercel dashboard (Add New Project → import `bansalbhunesh/id` → Framework: Other → Deploy). No Vercel project exists yet under your account for this repo. `vercel.json` is ready; if the build fails, check `get_deployment_build_logs` for the `@vercel/python` builder output.
2. **Replace the two placeholder slides in the deck** — slides 6 and 10 (`docs/deck/index.html`) currently use a stock photo / illustrative stats instead of real screenshots. Run `uvicorn`, open `localhost:8000`, screenshot the NTC hero card and the borderline persona's improvement plan, and swap them in.
3. **Print the deck to PDF** — `Ctrl+P` → Save as PDF on `docs/deck/index.html`. I did not automate this step myself: triggering a browser print dialog risks freezing the automation session the same way a JS `alert()` does, and the harness explicitly warns against that.
4. **Demo video (3 minutes, per the real template)** — walk through: NTC hero rejected traditionally → approved on alternate data → SHAP reasons → memo → switch to the borderline persona → improvement plan. Add the link into slide 13.
5. **Submission form** — Challenge = PS3, deployment link (once live), GitHub link (already filled into slide 13, confirmed public), PDF deck.

## Commands to run next

```bash
cd backend
source venv/Scripts/activate   # venv already created and populated
pytest -q                       # 11 tests, all passing
uvicorn main:app --port 8000    # serves API + frontend at http://localhost:8000
```

## Current branch / commit

`main` @ `34a46d8` ("build the actual 13-slide submission deck").
