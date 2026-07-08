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

**5 synthetic MSME personas** in `backend/sample_data.py`, including two distinct NTC/NTB stories.

Repo confirmed **public** on GitHub (template requires this). All 14 commits pushed to `git@github.com:bansalbhunesh/id.git` (main branch). Working tree is clean.

## What's left (needs your action, not code)

1. **Live deployment** — you chose to connect the GitHub repo via the Vercel dashboard yourself (Add New Project → import `bansalbhunesh/id` → Framework: Other → Deploy). As of this handoff, no Vercel project named `id`/`udyampulse` exists yet under your account — this step is still pending. `vercel.json` is ready to go; if the build fails, check `get_deployment_build_logs` for the `@vercel/python` builder output.
2. **The pitch deck (mandatory PDF)** — open `D:\Downloads\Prototype Submission Deck _ IDBI Innovate.pdf` (the real template) and paste in the content from `docs/PITCH_OUTLINE.md`, slide by slide.
3. **Screenshots for slide 10** — take fresh ones yourself from the running app (I captured some via browser automation this session but couldn't locate the saved files on disk to hand off directly — easiest to just recapture: run `uvicorn`, open `localhost:8000`, screenshot the NTC hero card, the AI risk model/memo section, and the borderline persona's improvement plan).
4. **Demo video (3 minutes, per the real template)** — walk through: NTC hero rejected traditionally → approved on alternate data → SHAP reasons → memo → switch to the borderline persona → improvement plan.
5. **Submission form** — Challenge = PS3, deployment link (once live), GitHub link (already have it, confirmed public), PDF deck.

## Commands to run next

```bash
cd backend
source venv/Scripts/activate   # venv already created and populated
pytest -q                       # 11 tests, all passing
uvicorn main:app --port 8000    # serves API + frontend at http://localhost:8000
```

## Current branch / commit

`main` @ `b0f4ff0` ("rewrite pitch outline to match the real official template").
