# Security And Compliance Posture

This is a public hackathon control set, not an assertion of IDBI production certification. The public deployment contains synthetic borrower cases and a public credit-default proxy model; no private IDBI data is present.

## Enforced Controls

| Control | Current implementation | Verification |
|---|---|---|
| Authentication | Bearer API keys parsed from `UDYAMPULSE_API_KEYS` | Protected-route tests |
| RBAC | `underwriter`, `auditor`, `admin` role hierarchy | Underwriter write tests; auditor log tests |
| Protected writes | `/score`, `/sandbox/score`, `/sandbox/recalibration/report`, `/sandbox/pilot-readiness`, `/validation/report` require `underwriter` | protected-route and pilot-phase tests |
| Audit access | `/audit-log` requires `auditor` or higher | 401/bad-key/valid-key tests |
| Consent | Fixed underwriting purpose, active status, grant/expiry order, no future grant, maximum 365 days, supported unique scopes, and every supplied feed covered by scope | Consent and missing-scope tests |
| Data minimisation | Audit events store an HMAC `subject_ref`, not borrower name | `test_scoring_appends_to_audit_log` |
| Audit integrity | SHA256 event chain, restart recovery, tamper detection, and one-time pseudonymising migration of legacy logs | Audit chain/restart/tamper tests |
| CORS | Explicit origin allowlist from `UDYAMPULSE_ALLOWED_ORIGINS` | `main.py` |
| Abuse control | Per-process IP sliding windows on protected write routes | `rate_limit.py` |
| Browser hardening | `nosniff`, frame denial, no-referrer, permissions policy and no-store on audit paths | `main.py` middleware |
| Model input fairness | Demographic fields excluded from model input; gender/age used only for holdout outcome monitoring | dataset manifest and evaluation fairness slices |
| Artifact integrity | Dataset and every model/manifest artifact are SHA256-linked in evaluation evidence and rechecked by the runtime promotion gate | `test_committed_evidence_hashes_match_artifacts`, `test_pilot_gate_blocks_failed_artifact_integrity` |
| Temporal outcome integrity | Observation follows decision, 365-day maturity, no duplicate IDs, chronological 70/15/15 splits and both classes per cohort | `test_pilot_phase.py` |
| Fail-closed promotion | `pilot`/`production` startup blocks the public proxy, demo credentials/HMAC, absent true OOT evidence and local JSONL | `test_public_demo_is_allowed_but_pilot_mode_fails_closed` |
| Upload minimisation | Pilot readiness validates in memory, persists no submitted records and returns no application IDs | pilot endpoint contract test |

## Demo Credentials

When `UDYAMPULSE_API_KEYS` is unset, the synthetic public demo exposes:

- `udyampulse-demo-underwriter-key` with `underwriter` scope;
- `udyampulse-demo-auditor-key` with `auditor` scope.

They are intentionally public and must never be used with real data. A pilot sets its own credentials and `UDYAMPULSE_AUDIT_HMAC_KEY`; it does not inherit the demo defaults.

Setting `UDYAMPULSE_MODE=pilot` does not bypass this requirement. Startup fails unless every gate exposed by `GET /deployment/readiness` passes.

Example:

```bash
curl -H "Authorization: Bearer udyampulse-demo-auditor-key" \
  https://id-ysm9.onrender.com/audit-log
```

## Residual Gaps

| Gap | Why it remains | Pilot requirement |
|---|---|---|
| IDBI SSO and per-user tenancy | Public demo has no real identities or accounts | OIDC/SSO, user/branch/role claims, row-level tenant boundaries |
| Managed secrets | Public keys are evaluator credentials | KMS/Vault/Secrets Manager with rotation and revocation |
| Durable shared audit store | JSONL is restart-safe on a filesystem but not multi-instance durable on ephemeral PaaS | WORM-capable database/log store, retention policy, signed exports |
| Distributed rate limiting | Current window is in-process | Shared Redis/API-gateway quota and abuse monitoring |
| Consent revocation service | Payload can state revoked and is rejected, but no external consent-manager lookup exists | Verify consent artefact/signature/status against approved AA/IDBI service |
| Encryption and localisation | No real data exists to classify or localise | IDBI-approved encryption, field classification, key ownership and India-region controls |
| Formal DPDP/RBI mapping | Requires actual data flows and legal interpretation | DPIA, retention/deletion schedule, model-risk approval and independent validation |
| Incident operations | No production SOC integration | Central logs, alerts, runbooks, breach process and access reviews |
| Approved MSME model artifact | Committed model is an external-domain public proxy | Retrain on approved dated sandbox outcomes and write an `idbi_pilot`/`true_oot` champion manifest |

## Threat Boundary

Sample GET routes remain public because they return a fixed synthetic cohort. Any route accepting custom or sandbox financial data is role-gated. The proxy PD may route a file to human review but cannot automatically decline, limiting cross-domain model risk until sandbox calibration is complete.
