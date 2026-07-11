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
| Audit integrity | Genesis-anchored SHA256 event chain, fsync append, restart recovery, tamper detection, and one-time pseudonymising migration of legacy logs | Audit chain/restart/genesis/tamper tests |
| CORS | Explicit origin allowlist from `UDYAMPULSE_ALLOWED_ORIGINS` | `main.py` |
| Abuse control | Thread-safe per-process IP sliding windows, stale-key cleanup, route-specific quotas, retry and remaining-budget headers | rate-limit tests |
| Resource bounds | 8 MiB declared-body ceiling; bounded pilot, recalibration, validation and reason-code arrays; O(n log n) AUC/KS | operational and validation-scale tests |
| Request trace | Validated or generated `X-Request-ID` plus `Server-Timing` on every response | operational tests |
| Browser hardening | Strict app CSP, frame denial, `nosniff`, no-referrer, permissions policy, opener isolation, HSTS on HTTPS and no-store JSON | operational tests |
| Runtime isolation | Non-root container user, liveness/readiness separation and Docker health check | Dockerfile and CI container job |
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
| Distributed rate limiting | Current bounded window is in-process | Shared Redis/API-gateway quota, concurrency limits and abuse monitoring |
| Consent revocation service | Payload can state revoked and is rejected, but no external consent-manager lookup exists | Verify consent artefact/signature/status against approved AA/IDBI service |
| Encryption and localisation | No real data exists to classify or localise | IDBI-approved encryption, field classification, key ownership and India-region controls |
| Formal DPDP/RBI mapping | Requires actual data flows and legal interpretation | DPIA, retention/deletion schedule, model-risk approval and independent validation |
| Incident operations | No production SOC integration | Central logs, alerts, runbooks, breach process and access reviews |
| Approved MSME model artifact | Committed model is an external-domain public proxy | Retrain on approved dated sandbox outcomes and write an `idbi_pilot`/`true_oot` champion manifest |

## Threat Boundary

Sample GET routes remain public because they return a fixed synthetic cohort. Any route accepting custom or sandbox financial data is role-gated. The proxy PD may route a file to human review but cannot automatically decline, limiting cross-domain model risk until sandbox calibration is complete.

The full asset, trust-boundary and abuse-case analysis is in [THREAT_MODEL.md](THREAT_MODEL.md). The promotion and rollback procedure is in [PILOT_RUNBOOK.md](PILOT_RUNBOOK.md).

## External Alignment

These controls are engineering alignment, not a compliance certification or legal opinion:

- [RBI Handbook on Regulations at a Glance, 2025](https://website.rbi.org.in/documents/d/rbi/handbookg27022025d0f3f53f5d3c4310a6bb2f8ac2175d3a) summarises prior explicit-consent expectations for digital lending.
- [OWASP API4:2023 Unrestricted Resource Consumption](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/) recommends payload bounds, parameter bounds and operation-specific rate limits.
- [W3C WAI-ARIA modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) informs the cockpit focus trap, inert background, Escape handling and focus return.
