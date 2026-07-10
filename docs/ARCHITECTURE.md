# Architecture

This is the engineering-depth companion to the README's judge-facing diagram: module responsibilities, model versioning, deployment topology, and security boundaries.

## Runtime topology

One FastAPI process serves both the JSON API and the static frontend (`backend/main.py` mounts `frontend/` as `StaticFiles` after all API routes, so it never shadows them). This is intentional for a hackathon deployable: one Render service, one Dockerfile, no separate frontend build step, and no CORS requirement in production because the frontend and API are same-origin. `UDYAMPULSE_ALLOWED_ORIGINS` exists only for local dev (opening the frontend on a different port) and any future external API consumer.

```
Browser (judge)
   |
   v
FastAPI process (single Render/Docker deployable)
   |-- StaticFiles: frontend/index.html
   `-- API routes: backend/main.py
          |
          v
   Request pipeline (per scoring call)
   Pydantic validation (feed_ingestion.py / scoring.py)
     -> consent enforcement (sandbox path only)
     -> rate limiting (rate_limit.py, scoring endpoints)
     -> scoring.py: 5-pillar rule score (descriptive)
     -> ml.py: pd_model.LogisticModel.predict_proba (risk estimate)
     -> policy object (decision, versioned)
     -> agent_memo.py: deterministic memo (+ optional Bedrock)
     -> audit_log.py: hash-chained append
```

## Module map

| Module | Responsibility | Depends on |
|---|---|---|
| `main.py` | Route definitions, auth/rate-limit wiring, CORS config | everything below |
| `auth.py` | Bearer-token role check (`require_role`) | stdlib + FastAPI |
| `rate_limit.py` | In-memory sliding-window limiter | stdlib + FastAPI |
| `scoring.py` | `MSMEProfile` contract, 5-pillar rule score, policy object, guardrails | `ml.py`, `agent_memo.py`, `audit_log.py` (local imports to avoid a cycle) |
| `feed_ingestion.py` | IDBI sandbox feed contracts, `ConsentRecord`, normalization to `MSMEProfile` | `scoring.py` |
| `ml.py` | Loads the committed PD artifact, exposes `explain()` / `model_status()` / `model_evaluation()`; optional GBM+SHAP upgrade gate | `pd_model.py`, `feature_bridge.py`, `linear_model.py` (fallback only) |
| `pd_model.py` | Dependency-free logistic regression + exact logit-space Shapley | stdlib only |
| `feature_bridge.py` | Runtime half of the universal-feature mapping (MSME pillars -> 0-1 features the PD model expects) | stdlib only |
| `model_training/` | Offline-only: dataset fetch+verify, training, evaluation. Never imported by the serving app. | pandas/xlrd (training-only, see `requirements-training.txt`) |
| `portfolio.py` | Synthetic-cohort aggregates, fairness slices, governance summary, PII redaction for public views | `pilot_metrics.py`, `sample_data.py`, `scoring.py`, `ml.py`, `audit_log.py` |
| `audit_log.py` | Append-only, hash-chained decision log | stdlib only |
| `validation.py` | AUC/KS/PSI/reason-stability calculators used by `/validation/*` | stdlib only |
| `recalibration.py` | Sandbox distribution/coverage profiling and GBM-readiness checks | `feed_ingestion.py`, `ml.py`, `validation.py` |
| `submission_proof.py` | Judge-facing evidence packet; pulls real numbers from the modules above, never its own fixtures | `portfolio.py`, `ml.py`, `scoring.py` |

## Model versioning

Three layers are versioned independently so upgrading one never silently changes the meaning of another:

1. **Rule-based score**: implicit version via `scoring.py`'s pillar formulas (no separate version tag today; changes are visible via the git history of `scoring.py`).
2. **PD model**: `ml.model_status()["active_provider"]` reports which model is live (`logistic_pd_v1` by default, `xgboost`/`lightgbm` when configured with real sandbox labels, `linear_synthetic_fallback` only if no artifact is committed). The artifact itself carries `trained_at_utc` and `dataset_sha256` so any served prediction is traceable to an exact training run and exact input data.
3. **Policy**: `policy.version` (`"policy-v1"` today) on every score response. A future PD-threshold-based policy becomes `"policy-v2"` without touching the score or PD fields.

**Retraining is one command** (`python backend/model_training/train_pd_model.py`) and is deterministic (fixed split seed). It overwrites `artifacts/artifact.json` and `artifacts/evaluation.json` together, so the served model and its published evaluation numbers can never drift apart.

## Deployment

- `Dockerfile` + `render.yaml`: single-service deploy, same image serves API and static assets.
- No database: audit log is in-memory (source of truth) with best-effort append to `audit_log.jsonl` on disk; both are ephemeral on typical serverless/PaaS filesystems by design (see `audit_log.py`'s module docstring). A pilot deployment swaps this for a persistent store behind the same `record`/`read_recent`/`verify_chain` interface.
- No secrets are required to run the public demo: the PD model artifact is committed (not fetched from a secret store), and `auth.py` ships a published demo credential (see `docs/SECURITY_COMPLIANCE.md`) so judges can exercise the auditor-gated endpoint without provisioning anything.

## Security boundaries

See `docs/SECURITY_COMPLIANCE.md` for the full control-by-control breakdown. Summary of what crosses a trust boundary and how it's handled:

| Boundary | Control |
|---|---|
| Public internet -> scoring endpoints | Rate-limited (`rate_limit.py`), Pydantic-validated, no auth required (synthetic/caller-owned data only) |
| Public internet -> `/audit-log` | Bearer-token, `auditor`-role-gated (`auth.py`) -- this is the endpoint the external audit named as a bank-grade risk |
| Public internet -> `/governance`, `/submission/proof` | Public, but PII-redacted (`portfolio._redact_latest_decision`) |
| Sandbox feed -> scoring | `ConsentRecord` (purpose/scope/expiry) required and enforced; expired consent is a 403, not a warning |
| Browser -> API | CORS restricted to an explicit origin allowlist (`UDYAMPULSE_ALLOWED_ORIGINS`), not wildcard |
| Past audit entries -> tampering | SHA-256 hash chain (`audit_log.verify_chain`), surfaced live in `/governance`'s "Audit reconstruction" control |
