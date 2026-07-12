# Model Card: UdyamPulse Public Proxy Champion

## Purpose

UdyamPulse is decision support for MSME underwriting. It produces a descriptive financial-health score, a separately labelled probability-of-default proxy, a versioned policy route, reason codes, a proposed limit, and an underwriter memo. It is not a production auto-decision system.

## Three Separate Layers

1. **Health score (`scoring.py`)**
   - Five transparent 0-20 pillars: liquidity, discipline, momentum, leverage, and digital footprint.
   - Produces a 0-100 score, A-E grade, proposed limit, improvement plan, and rule reason codes.

2. **PD champion/challenger (`model_training/`, `ml.py`)**
   - Calibrated monotonic XGBoost champion with native exact TreeSHAP in logit space.
   - Calibrated dependency-free logistic regression fallback with exact linear Shapley attribution.
   - Both use the same three universal risk concepts and a real observed binary default label from a public proxy dataset.

3. **Policy (`apply_decision_policy`)**
   - `policy-v2-score-pd-separation` keeps score, PD and lending action distinct.
   - Grade D/E is a scorecard-policy decline; Grade C is mandatory review.
   - A PD above the calibrated proxy threshold routes an A/B case to human review, but the cross-domain proxy can never auto-decline.

## Training Data

The model uses the UCI **Default of Credit Card Clients** dataset: 30,000 anonymised Taiwan consumer-credit accounts with an observed next-month default label. The file is SHA256-verified against `backend/model_training/dataset_manifest.json`.

This is not IDBI data, Indian MSME data, GST/UPI/EPFO data, or evidence of production MSME performance. It proves that the training, calibration, model-selection, explanation, monitoring and serving contracts are real and reproducible while labelled IDBI sandbox outcomes are unavailable.

### Universal Feature Bridge

| Feature | UCI construction | Runtime MSME construction |
|---|---|---|
| `discipline` | Repayment delinquency history | GST continuity plus cheque conduct; score 17+/20 maps to the no-adverse-conduct state |
| `leverage` | Average bill utilisation | Debt relative to monthly inflow |
| `liquidity` | Bill-amount stability | Cash-inflow stability |

Higher values always mean lower risk. XGBoost enforces monotonic constraints `(-1, -1, -1)`, and tests verify that strengthening any universal feature cannot increase PD.

Momentum and digital footprint remain descriptive scorecard pillars because the UCI source has no economically honest equivalent. Gender, age, education, marital status and geography are excluded from model inputs.

## Training And Selection

`python backend/model_training/train_pd_model.py` performs one deterministic run:

1. Verify the source dataset hash.
2. Make a stratified 70/15/15 development/calibration/holdout split.
3. Fit logistic and monotonic XGBoost candidates on development only.
4. Fit Platt calibration on calibration only.
5. Select the champion on calibration using an AUC materiality guardrail and Brier tie-break.
6. Select a human-review PD threshold on calibration, targeting at least 60% bad capture.
7. Open the untouched holdout once for final metrics, bootstrap intervals and protected-group monitoring.

The source is cross-sectional. The final 15% is an untouched **random holdout, not an out-of-time split**. Genuine OOT validation requires dated IDBI repayment outcomes and remains explicitly pending.

## Current Evidence

Champion: `xgboost_pd_proxy_v1`

Holdout: 4,500 rows

Review threshold: PD 0.258, selected on calibration only

| Metric | Holdout result |
|---|---:|
| ROC-AUC | 0.7497 |
| ROC-AUC bootstrap 95% interval | 0.7314-0.7678 |
| Gini | 0.4993 |
| KS | 0.4225 |
| PR-AUC | 0.4948 |
| Brier score | 0.1415 |
| Expected calibration error | 0.0122 |
| Development-vs-holdout PSI | 0.0003 |

The null Brier benchmark, log loss, decile calibration, confusion matrix, 200-replicate intervals, candidate comparison, artifact hashes and group slices are committed in `backend/model_training/artifacts/evaluation.json` and served by `GET /model/evaluation`.

## Real Small-Business Outcome Benchmark

The consumer-credit proxy above validates the pillar-PD *conduct* concepts on real
default outcomes, but its domain is consumer, not small business. A second,
independent benchmark closes the domain gap: it trains the identical
methodology (monotone-constrained XGBoost, Platt calibration, native exact
TreeSHAP, logistic challenger) on **real U.S. SBA 7(a) small-business loans with
a real charge-off label**, and validates it **out of distribution**.

Model: `sba_sme_pd_v1`. Nine leakage-free origination features
(`term_months`, `employees_log`, `jobs_supported_log`, `gross_approved_log`,
`guarantee_portion`, `new_business`, `real_estate_backed`, `urban`,
`recession_origination`), each with an economically-signed monotone constraint.
Post-outcome columns (`ChgOffPrinGr`, which matches the label 99.2% of the time)
and the causal-study `Selected` flag are excluded.

| Metric | Holdout (943 real SBA loans) | Out-of-distribution (1,159 real SBA loans) |
|---|---:|---:|
| ROC-AUC | 0.9066 | 0.9401 |
| KS | 0.7115 | 0.7946 |
| PR-AUC | 0.8973 | — |
| Brier score | 0.1157 | 0.1482 |
| Holdout-vs-shift PSI | — | 0.631 |
| TreeSHAP max reconstruction error (logit) | 2.15e-06 | — |

The out-of-distribution set is a differently-distributed real SBA sample (16% vs
53% default base rate, PSI 0.63): a model that only memorised the training
distribution would collapse; ranking power that survives is genuine
generalisation evidence, not a re-scored random holdout. To our knowledge no
other public submission in this track validates on real small-business default
outcomes out of distribution.

**Honesty caveats (committed in `sme_evaluation.json`).** This is a *curated,
class-balanced research sample* (~53% default vs the ~18% SBA population rate),
which inflates apparent separation versus a natural-rate book; loan *term*
dominates by gain importance, so it is a loan-*structure* benchmark that is
complementary to — not a replacement for — the GST/UPI/EPFO alternate-data
*conduct* pillars in the served score; and US SBA is a proxy domain for Indian
MSME. It is real-outcome methodology proof, not an IDBI production calibration.
Reproduce with `python backend/model_training/train_sme_pd_model.py`; served by
`GET /model/sme-benchmark`.

## Explainability

XGBoost explanations use native `pred_contribs`, which is exact TreeSHAP in margin/logit space. Platt calibration is linear in that space, so applying the calibration slope to feature contributions and the calibration intercept to the bias preserves exact reconstruction. Every response exposes `shap_sum_check_logit`; tests require absolute error below `1e-5`.

Probability-point contributions are a first-order display approximation at the baseline and are labelled as such. The exact audit invariant is always the logit-space sum.

## Fairness Monitoring

Protected fields are excluded from training and inference, then used only for post-model monitoring on the untouched proxy holdout. `evaluation.json` reports, by gender and age band:

- sample size and observed default rate;
- average predicted PD;
- AUC and Brier score;
- bad-capture/recall and false-positive rate;
- maximum between-group gaps.

The current gender AUC gap is 0.0175. Age-band recall gaps are larger and remain a review signal, not a fairness certification. Sector, geography, vintage and NTC/NTB slices are unavailable in the proxy source and require IDBI sandbox outcomes. The small live synthetic-cohort views are illustrative only.

## Audit And Security

- Custom, sandbox, recalibration, pilot-readiness and submitted-validation routes require the `underwriter` role.
- Audit access requires the `auditor` role.
- Sandbox consent enforces underwriting purpose, active status, expiry, maximum duration, supported scopes, and coverage of every supplied feed.
- Audit events contain a stable HMAC pseudonym instead of borrower name, persist with fsync, and form a genesis-anchored SHA256 chain. Mixed legacy logs are pseudonymised and re-chained during one-time migration.
- CORS is allowlisted; write routes are rate-limited; requests are traced; JSON is `no-store`; and the application emits a strict CSP plus browser hardening headers.
- Request bodies and validation/recalibration arrays are bounded. AUC and KS monitoring use O(n log n) rank/sweep algorithms rather than pairwise work.

## Pilot Promotion Boundary

The public proxy is technically incapable of being promoted by changing a UI label. `deployment_gate.py` defines explicit runtime modes:

- `public_demo` keeps the synthetic review surface available and exposes every blocker.
- `pilot` and `production` fail startup unless the active artifact declares `deployment_scope=idbi_pilot` and `temporal_validation=true_oot`.
- Private role credentials, a private audit HMAC key, and a durable append-only audit backend must also be configured.

`GET /deployment/readiness` exposes the redaction-safe gate state. The current public deployment correctly reports `pilot_ready=false`.

`pilot_readiness.py` defines the future bank-data evidence contract. A record needs a dated decision, a bank-approved `bad_12m` label, a full observation endpoint at least 365 days later, and the consented sandbox payload used at decision time. The report:

1. excludes immature/censored records;
2. rejects duplicate applications and temporal leakage;
3. creates chronological 70/15/15 development, calibration and latest-period OOT cohorts without random shuffle;
4. requires both outcomes in every cohort;
5. gates source coverage, NTC/NTB volume, temporal breadth and fairness-slice support;
6. returns counts and blockers without persisting records or returning application identifiers.

## Reproduction

```bash
pip install -r backend/model_training/requirements-training.txt
python backend/model_training/train_pd_model.py
pytest backend -q
```

The retraining command rewrites the logistic artifact, XGBoost model, XGBoost metadata, champion manifest and evaluation report. Evaluation contains hashes for every committed artifact.

## Known Limitations

- Cross-domain transfer from Taiwan consumer credit to Indian MSMEs is unvalidated. Absolute PD must not be treated as bank calibration.
- There is no true OOT window, NTC/NTB outcome slice, sector/geography/vintage outcome slice, or early-NPA evidence before sandbox labels arrive.
- The public demo uses published scoped credentials and an in-process bounded rate limiter. IDBI SSO, per-user tenancy, KMS-managed secrets, durable shared audit storage and distributed rate limiting remain pilot work.
- The dated outcome and promotion machinery is implemented, but no IDBI records have been supplied. Current pilot blockers are intentional evidence of fail-closed behavior, not production readiness.
- AWS Bedrock memo generation is optional; deterministic generation is the default fallback.

## Intended Use

Underwriter decision support and model-governance demonstration. Any live credit decision requires IDBI-approved data, policy, threshold calibration, validation and human oversight.
