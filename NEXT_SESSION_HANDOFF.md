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
- `docs/PITCH_OUTLINE.md` — 10-slide deck structure mapped to IDBI's template.

**5 synthetic MSME personas** in `backend/sample_data.py`, including two distinct NTC/NTB stories.

All 12 commits pushed to `git@github.com:bansalbhunesh/id.git` (main branch). Working tree is clean.

## What's left (needs your action, not code)

1. **Live deployment** — you chose to connect the GitHub repo via the Vercel dashboard yourself (Add New Project → import `bansalbhunesh/id` → Framework: Other → Deploy). As of this handoff, no Vercel project named `id`/`udyampulse` exists yet under your account — this step is still pending. `vercel.json` is ready to go; if the build fails, check `get_deployment_build_logs` for the `@vercel/python` builder output.
2. **The pitch deck (mandatory PDF)** — build it in IDBI's official template using `docs/PITCH_OUTLINE.md` as the script. Needs real screenshots from a running instance (local `uvicorn` or the live Vercel URL once connected).
3. **Demo video** — 60–90s screen recording of the NTC hero flow (rejected traditionally → approved on alternate data → SHAP reasons → memo → improvement plan).
4. **Submission form** — Challenge = PS3, deployment link (once live), GitHub link (already have it), PDF deck.

## Commands to run next

```bash
cd backend
source venv/Scripts/activate   # venv already created and populated
pytest -q                       # 11 tests, all passing
uvicorn main:app --port 8000    # serves API + frontend at http://localhost:8000
```

## Current branch / commit

`main` @ `b08dc71` ("add more demo personas and CI badge").
