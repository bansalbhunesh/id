# Architecture

## Runtime

One Python 3.12 Docker service runs FastAPI and serves the static review cockpit. The zero-build frontend and API stay same-origin; API route definitions are mounted before `StaticFiles`.

![UdyamPulse runtime architecture](diagrams/architecture-flow.svg)

<details>
<summary>Mermaid source (renders live on GitHub too; the image above is a committed fallback so the diagram never depends on a client-side renderer)</summary>

```mermaid
flowchart TB
  subgraph Experience["Review experience"]
    Reviewer["Judge / underwriter"] --> Cockpit["Static same-origin cockpit"]
    Cockpit --> Views["Decision | Evidence | Governance | Proof | Sources"]
  end

  subgraph Runtime["FastAPI runtime boundary"]
    Edge["Request ID | body limit | CSP | rate limit"] --> Routes["Public sample + protected bank-data routes"]
    Routes --> Intake["Pydantic + consent + feed normalisation"]
    Intake --> Score["Five-pillar health score + proposed limit"]
    Score --> Champion["Calibrated monotonic XGBoost"]
    Champion --> Explain["Exact TreeSHAP in calibrated logit space"]
    Explain --> Policy["Versioned approve / review / reject policy"]
    Policy --> Memo["Deterministic memo; optional Bedrock"]
  end

  subgraph Evidence["Evidence and control plane"]
    Audit["Genesis-anchored pseudonymous audit chain"]
    Monitor["AUC | Gini | KS | calibration | PSI | fairness"]
    Readiness["Dated outcomes | 365-day maturity | temporal split"]
    Promotion["Artifact | OOT | identity | audit promotion gates"]
  end

  subgraph Pilot["Approved pilot boundary - absent from public demo"]
    BankFeeds["IDBI / AA sandbox feeds"]
    Outcomes["Dated repayment outcomes"]
    Offline["Offline champion / challenger training"]
    Durable["Private identity + WORM audit"]
  end

  Views --> Edge
  Memo --> Audit
  Champion --> Monitor
  Audit --> Promotion
  Monitor --> Promotion
  Readiness --> Promotion
  BankFeeds -.-> Intake
  Outcomes -.-> Readiness
  Outcomes -.-> Offline
  Offline -.-> Champion
  Durable -.-> Promotion
  Promotion -->|"all pass"| PilotRuntime["Pilot runtime starts"]
  Promotion -->|"any block"| Refuse["Startup refused"]
```

Regenerate the image after editing the source: save the block above to a `.mmd` file and run `mmdc -i file.mmd -o diagrams/architecture-flow.svg`.

</details>

## Decision Contract

UdyamPulse intentionally avoids one opaque "AI score":

1. `scoring.py` computes five descriptive pillars, grade and proposed limit.
2. `ml.py` loads the committed champion manifest and returns PD plus exact attribution.
3. `apply_decision_policy` combines grade and the calibrated PD review threshold.
4. The public proxy may route an A/B disagreement to review, but cannot auto-decline.
5. Grade C is always reviewed; D/E remains a transparent scorecard-policy decline.
6. A sandbox source the caller never connected (as opposed to one that reported a genuinely weak signal) always routes to review, regardless of what the score or PD say -- a missing pillar input is not the same as an observed risk, and `POST /sandbox/score` cannot auto-approve or auto-decline on a pillar it never actually measured.

## Champion/Challenger Training

`model_training/train_pd_model.py` verifies the 30,000-row source hash, creates development/calibration/holdout splits, fits calibrated logistic and monotonic XGBoost candidates, selects on calibration, and evaluates once on holdout. It writes:

| Artifact | Purpose |
|---|---|
| `artifact.json` | Calibrated logistic fallback |
| `xgboost_model.json` | Monotonic XGBoost trees |
| `xgboost_metadata.json` | Calibration and exact TreeSHAP contract |
| `champion.json` | Serving provider, threshold and artifact map |
| `evaluation.json` | Candidate comparison, holdout metrics, intervals, fairness, PSI, gaps and hashes |

The cross-sectional source cannot provide OOT validation. `evaluation.json` states this explicitly and reserves the term OOT for future dated IDBI outcomes.

## Module Map

| Module | Responsibility |
|---|---|
| `main.py` | Routes, role wiring, liveness/readiness, middleware and static mount |
| `operational.py` | Release metadata, payload ceiling, request IDs and browser/security header policy |
| `auth.py` | API-key role hierarchy |
| `rate_limit.py` | Thread-safe sliding windows, stale-key cleanup and quota response headers |
| `feed_ingestion.py` | AA/GST/UPI/EPFO/Bureau contracts and consent enforcement |
| `pilot_readiness.py` | Dated outcome schema, maturity checks, chronological splits, segment/source gates and privacy-safe report |
| `deployment_gate.py` | Runtime modes and fail-closed model/identity/OOT/audit promotion policy |
| `scoring.py` | Health score, proposed limit, decision policy, reasons and guardrails |
| `feature_bridge.py` | Explicit MSME-to-universal risk mapping |
| `ml.py` | Champion loading, fallback, PD and explanation response |
| `xgb_pd_model.py` | XGBoost inference and exact calibrated TreeSHAP reconstruction |
| `pd_model.py` | Calibrated dependency-free logistic fallback and exact linear Shapley |
| `model_training/` | Offline training, metrics, selection, uncertainty and fairness evidence |
| `validation.py` | Production-scale O(n log n) AUC/KS, PSI and reason-code stability |
| `audit_log.py` | HMAC pseudonyms, fsync persistence, genesis verification, migration and hash chain |
| `portfolio.py` | Synthetic portfolio views, public redaction and governance controls |
| `submission_proof.py` | Judge-facing proof assembled from live backend state |

## Security Boundaries

| Boundary | Enforcement |
|---|---|
| Public browser to sample data | Fixed synthetic GET responses only |
| Caller data to API | Underwriter bearer role, rate limit and Pydantic validation |
| Internet request to runtime | Declared-body ceiling, request trace, CSP, frame denial and no-store JSON |
| Sandbox sources to scoring | Active purpose-bound consent with complete source scope |
| Audit reader | Auditor role |
| Audit subject identity | HMAC pseudonym; no raw borrower name retained |
| Historical event mutation | Genesis-anchored SHA256 chain verified after restart and on governance reads |
| Model evidence | Dataset/artifact hashes and deterministic retraining command |
| Public proxy to bank pilot | Startup block until artifact scope, true OOT, private credentials/HMAC and durable audit storage pass |
| Pilot outcome upload | Underwriter role, in-memory analysis only, no returned identifiers, explicit 365-day maturity |

## Stage 2 Swap Points

- Replace the public proxy loader with approved dated IDBI MSME outcomes while preserving the universal serving contract.
- Supply approved dated records to the implemented outcome contract; the service now constructs true temporal development/calibration/OOT windows and blocks insufficient NTC/NTB or monitoring slices.
- Calibrate policy thresholds to IDBI loss economics and early-NPA guardrails.
- Replace demo API keys with IDBI SSO and JSONL with a durable WORM-capable audit store.
- Enable Bedrock only behind approved prompts, output schema checks and the deterministic fallback.

The operational sequence, sign-offs and rollback triggers are in [PILOT_RUNBOOK.md](PILOT_RUNBOOK.md). Threats and residual controls are in [THREAT_MODEL.md](THREAT_MODEL.md).

## Promotion State Machine

![UdyamPulse promotion state machine](diagrams/promotion-state.svg)

<details>
<summary>Mermaid source (renders live on GitHub too; the image above is a committed fallback so the diagram never depends on a client-side renderer)</summary>

```mermaid
stateDiagram-v2
  [*] --> PublicDemo
  PublicDemo --> PilotBlocked: pilot mode requested with any blocker
  PublicDemo --> PilotReady: IDBI artifact + true OOT + private identity/HMAC + durable audit
  PilotBlocked --> PilotReady: all gates remediated
  PilotReady --> ProductionReview: independent model-risk and policy approval
```

Regenerate the image after editing the source: save the block above to a `.mmd` file and run `mmdc -i file.mmd -o diagrams/promotion-state.svg`.

</details>

The current repository remains in `PublicDemo`. It cannot enter `PilotReady` with the committed public-proxy manifest.
