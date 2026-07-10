# Security & Compliance Posture

This document responds directly to the external technical audit's P1 finding: *"The public API is not suitable for financial data"* (wildcard CORS, no auth on any route, publicly readable mutable audit data). It lists what is now implemented and enforced, cites the code and tests that prove it, and states plainly what is still out of scope for a public hackathon demo versus what a real IDBI pilot deployment would need.

RBI's draft Guidance on Model Risk Management requires AI-assisted credit decisions to be "consistent, unbiased, explainable and verifiable." The controls below map to that language directly.

## Implemented controls

| Control | Implementation | Evidence |
|---|---|---|
| Authentication | Bearer-token API keys, checked per-request (`backend/auth.py:require_role`) | `test_stage2.py::test_audit_log_requires_authentication`, `::test_audit_log_rejects_bad_key`, `::test_audit_log_accepts_demo_auditor_key` |
| Role-based access control | Two roles (`auditor`, `admin`) ranked and enforced; `GET /audit-log` requires `auditor` or higher | `backend/auth.py:_ROLE_RANK`, same tests as above |
| CORS restriction | `allow_origins` changed from `["*"]` to an explicit allowlist (`UDYAMPULSE_ALLOWED_ORIGINS`, default: local dev ports + the live Render origin); `allow_methods`/`allow_headers` narrowed from wildcard | `backend/main.py` |
| Rate limiting | In-memory sliding-window limiter (60 req/min/IP) on `POST /score` and `POST /sandbox/score` | `backend/rate_limit.py` |
| Consent enforcement | `ConsentRecord` (purpose, scope, expiry) required on every sandbox feed; expired consent returns 403, not a silent pass | `backend/feed_ingestion.py:ConsentRecord`, `test_stage2.py::test_sandbox_score_rejects_missing_consent`, `::test_sandbox_score_rejects_expired_consent`, `::test_sandbox_score_guardrail_reflects_verified_consent` |
| Tamper-evident audit trail | SHA-256 hash chain over every audit entry; `verify_chain()` detects any retroactive edit | `backend/audit_log.py`, `test_audit_log.py::test_hash_chain_links_consecutive_entries`, `::test_verify_chain_detects_tampering` |
| PII minimisation on public routes | `GET /governance` and `GET /submission/proof` redact the most recent borrower's name before returning `latest_decision`; full records require the `auditor` role via `GET /audit-log` | `backend/portfolio.py:_redact_latest_decision`, `test_stage2.py::test_governance_redacts_latest_borrower_name` |
| Fair-lending-aware model inputs | Demographic fields excluded from PD-model training and inference inputs on both sides of the domain bridge (SEX/EDUCATION/MARRIAGE/AGE in the training data; gender/district in the served profile) | `backend/model_training/dataset_manifest.json:columns_deliberately_excluded`, `backend/feature_bridge.py` |
| Evidence integrity | Model artifact is SHA256-tied to its exact training dataset and re-derivable by one command; served evaluation numbers can never drift from what was actually trained | `backend/model_training/train_pd_model.py` |

## What "authentication" means here, precisely

This is a real, enforced check -- not a placeholder. It is deliberately **not** full multi-tenant identity: there is no login flow, no per-underwriter session, and no "view only your own submissions" concept, because the public demo has no user accounts to attach that to. A demo `auditor` key is published (`docs/DEMO_SCRIPT.md`, fallback value in `auth.py` when `UDYAMPULSE_API_KEYS` is unset) so judges can exercise the gated endpoint without provisioning secrets -- the same pattern real fintech sandboxes use for evaluator access. Any real deployment sets `UDYAMPULSE_API_KEYS` to real, per-integrator credentials and drops the built-in demo key entirely.

## Explicitly out of scope for this repository (disclosed, not silently skipped)

| Gap | Why it's deferred | Sandbox-phase plan |
|---|---|---|
| Full identity/session management (per-underwriter login, "my submissions only") | No user accounts exist in a public synthetic-cohort demo; building a login system for data that isn't real would be security theater | IDBI SSO/OAuth integration once real underwriter accounts exist |
| Persistent, durable audit storage | In-memory + best-effort JSONL matches the single-process deployable this ships as; a real pilot needs multi-instance durability | Swap `audit_log.py`'s storage behind the same `record`/`read_recent`/`verify_chain` interface for a real database/log store |
| Distributed rate limiting | Current limiter is per-process in-memory; fine for one Render instance, not for a multi-instance production fleet | Move to a shared store (Redis or equivalent) behind the same `rate_limit()` dependency signature |
| DPDP Act / RBI data-localisation compliance mapping | Requires real customer data flows and a legal review that don't exist for a synthetic-cohort public demo | Formal compliance mapping once real IDBI sandbox data categories are known |
| Secrets management (KMS/Vault for API keys) | No real secrets exist yet -- the demo key is intentionally public | Standard secrets manager once real per-integrator keys are issued |

## Known residual risk in the public demo

- The in-memory rate limiter resets on process restart (Render free-tier instances can restart); this bounds abuse per-instance-lifetime, not permanently. Acceptable for a judge-facing demo, not for production.
- `UDYAMPULSE_API_KEYS` falls back to a published demo key when unset. This is intentional (see above) but means anyone who reads this repository can access `GET /audit-log` on the live demo -- which only ever contains synthetic/demo-submitted data, never real customer data, so the blast radius is bounded by design.
