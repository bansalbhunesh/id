# Security Policy

UdyamPulse is a public hackathon prototype. The public deployment serves only
synthetic MSME cases and a public credit-default proxy model -- it never holds
real IDBI customer data. See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) for
the full trust-boundary model and [`docs/SECURITY_COMPLIANCE.md`](docs/SECURITY_COMPLIANCE.md)
for the enforced-control checklist and disclosed residual gaps.

## Reporting a vulnerability

If you find a security issue, please report it privately rather than opening a
public GitHub issue:

- Email the maintainer with a description, reproduction steps, and the
  affected route or component.
- Do not include real financial data, live credentials, or personal
  information in the report -- the public demo should never receive any.
- Please allow reasonable time to investigate and remediate before any public
  disclosure.

## Scope

In scope: the FastAPI service (`backend/`), the static cockpit (`frontend/`),
and the training/evaluation pipeline (`backend/model_training/`).

Out of scope: the demo bearer keys published in
[`docs/SECURITY_COMPLIANCE.md`](docs/SECURITY_COMPLIANCE.md) are intentionally
public evaluator credentials for the synthetic demo -- using them against the
public demo is expected, not a vulnerability. A pilot deployment replaces them
entirely; see `deployment_gate.py` for the fail-closed startup checks that
enforce this.

## Current posture (summary)

Enforced today: role-gated writes and audit access, purpose/scope/expiry
consent validation, per-process rate limiting, a strict CSP and browser
hardening headers, HMAC-pseudonymised audit events with a genesis-anchored
hash chain, and artifact-hash verification at startup. Disclosed and not yet
implemented: IDBI SSO, KMS-managed secrets, a durable shared audit store, and
distributed rate limiting -- all fail-closed gates for pilot/production mode
in `deployment_gate.py`, not silent gaps.
