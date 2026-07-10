# Model Card - UdyamPulse MSME Financial Health Model

## Purpose

UdyamPulse produces an explainable MSME financial health score, credit grade, risk band, eligible limit, PD (probability-of-default) estimate, reason codes, and underwriter memo from consented alternate-data signals. It is aimed at New-to-Credit and New-to-Bank enterprises that traditional bureau-based underwriting cannot evaluate fairly.

## Model type

The public prototype ships three separately-labeled layers so a health score, a risk estimate, and a policy decision are never conflated into one opaque number:

1. **Rule-based pillar scorer** (`backend/scoring.py`) -- descriptive
   - Five pillars: Liquidity, Discipline, Momentum, Leverage, Digital Footprint.
   - Each pillar is 0-20; total is 0-100 with A-E grade and risk band.
   - Also emits data-source signals, policy guardrails, decision path, and improvement plan.

2. **Logistic-regression PD model** (`backend/pd_model.py`, `backend/ml.py`) -- risk estimate
   - Trained on a **real binary default-outcome label** from a public dataset (UCI "default of credit card clients", 30,000 rows), not a synthetic score proxy. See "Training data" below for exactly how this is bridged to the MSME feature space and what it does and doesn't prove.
   - Dependency-free at serve time: `backend/pd_model.py` is stdlib-only gradient-descent logistic regression, loaded from a committed JSON artifact (`backend/model_training/artifacts/artifact.json`). No scikit-learn/numpy is required to run the API.
   - Exact Shapley attribution in logit space (`weight_i * (x_i - mean_i)`), plus a first-order probability-scale approximation for display, both returned by every score.
   - Optional `UDYAMPULSE_MODEL_PROVIDER=xgboost|lightgbm` plus `UDYAMPULSE_TRAINING_DATA` still enables a production-scale SHAP-backed runtime once real IDBI sandbox repayment labels exist -- unchanged from the prior design, now layered on top of a real default-model baseline instead of a synthetic one.

3. **Versioned policy** (`policy` field on every score response) -- decision
   - `policy_version: "policy-v1"`: approve grades A-C, grade C routed to human review.
   - Kept separate from both the score and the PD estimate so a future PD-threshold-based policy can be introduced without silently changing what "score" or "PD" mean.

The UI surfaces all three together so an underwriter can cross-check a transparent policy score against a learned risk model and see the actual decision rule applied.

## Training data

**Real default-outcome label, public proxy dataset.** No public dataset of real Indian MSME GST/UPI/EPFO alternate-data with an observed default outcome exists -- that gap is exactly what the IDBI sandbox (available post-shortlisting) is for. `backend/model_training/train_pd_model.py` instead trains on the UCI "default of credit card clients" dataset (Yeh & Lien, 2009; SHA256-verified against `backend/model_training/dataset_manifest.json`), which has a real, observed binary default label.

**How the domain bridge works** (`backend/feature_bridge.py` + `backend/model_training/uci_feature_bridge.py`): both the UCI dataset and MSMEProfile are reduced to the same 3 "universal risk concepts", each 0-1:

| Universal feature | UCI signal | MSME signal |
|---|---|---|
| `discipline` | Repayment-status columns (PAY_0..PAY_6) | Cheque bounce rate + GST filing streak (scoring.py pillar) |
| `leverage` | Average bill / credit limit (utilization) | Outstanding debt / monthly inflow (scoring.py pillar) |
| `liquidity` | Coefficient of variation of monthly bill amounts | Coefficient of variation of monthly inflow (scoring.py pillar) |

**Deliberately excluded from the PD model**, with reasoning kept in the code, not hidden:

- `momentum` (GST turnover growth pillar): a rising credit-card bill in the UCI data means *more borrowing* (higher risk); rising GST turnover for an MSME means business growth (lower risk). The sign flips between domains, so there is no honest single mapping. It remains a descriptive-only pillar in the rule-based score, pending real GST trend data from the IDBI sandbox.
- `digital_footprint` (UPI breadth/velocity pillar): the UCI dataset has no transaction-count/counterparty-breadth analog at all.
- **Demographic columns** (SEX, EDUCATION, MARRIAGE, AGE in UCI; gender/district in MSMEProfile): excluded from model inputs on both sides, by design -- fair-lending practice is to never use protected/proxy-for-protected attributes as risk-model inputs. Demographic parity is instead monitored on model *outputs* (`GET /portfolio`, `GET /governance` fairness slices), not baked into training features.

`POST /sandbox/score` still accepts IDBI sandbox-style AA/GST/UPI/EPFO/Bureau payloads and converts them into the same underwriting feature contract; the public cohort remains synthetic because the repository does not contain private IDBI sandbox credentials, customer data, or repayment labels. `POST /sandbox/recalibration/report` profiles real feature distributions and coverage from submitted sandbox payloads and checks whether labelled volume is sufficient for GBM/SHAP mode.

**What this proxy model does and does not prove**: it proves the training/evaluation *pipeline* -- real label, real split, real held-out metrics, reproducible end to end -- works correctly and produces a well-discriminating model (OOT ROC-AUC 0.745, real rank-ordering power). It does **not** prove Indian MSME default risk is predicted by these exact coefficients, and its *absolute* PD outputs are not calibrated when applied to MSME-derived inputs; that requires retraining on real IDBI sandbox repayment outcomes, which is the documented Stage 2 swap (same `train_pd_model.py` entry point, real data source).

**A specific, verified calibration caveat**: `discipline` dominates the model (weight -8.15, far larger than `leverage` or `liquidity`), and the UCI training population's mean discipline is 0.953 -- most cardholders in that dataset have a near-perfect repayment record, so the distribution is tightly concentrated near 1.0. The rule-based scorer's own "Strong" threshold (`reasons_codes()`, pillar >= 16/20 = 0.80 universal) sits *below* that training-population mean. A borrower the rule-based scorer calls a strong performer can therefore get a higher `pd_estimate` than intuition suggests, purely because the two domains' "discipline" distributions have different shapes, not because of any error in the arithmetic (verified: `sigmoid(intercept + sum(weight_i * feature_i))` reproduces the served `pd_estimate` exactly). Trust `pd_estimate` for its rank-ordering (which case is riskier than another) more than for its absolute percentage until it is recalibrated on real MSME outcome data.

## Reproducing the evidence

```bash
cd backend/model_training
pip install -r requirements-training.txt   # training-time only; never required to serve
python train_pd_model.py
```

This downloads the dataset (SHA256-checked against the manifest), fits the model with a fixed seed, and rewrites `artifacts/artifact.json` (served by `ml.py`) and `artifacts/evaluation.json` (served by `GET /model/evaluation`). Re-running it is deterministic.

**Current held-out (true out-of-time split, 4,500 rows the model never trained or calibrated on) results:**

| Metric | Value |
|---|---:|
| ROC-AUC | 0.745 |
| Gini | 0.489 |
| KS | 0.418 |
| PR-AUC | 0.498 |
| Brier score | 0.146 |
| PSI (train vs OOT) | see `GET /model/evaluation` -- stable by construction (same seeded split) |

Calibration bins in `evaluation.json` show predicted-PD tracking observed default rate closely across all 10 deciles (e.g. bottom decile: predicted 13.0%, actual 12.7%; top decile: predicted 63.6%, actual 65.6%).

## Explainability

Every score returns:

- Plain-language pillar reason codes (rule-based layer).
- `pd_estimate`: the PD model's probability of default, plus exact logit-space Shapley contributions and a probability-scale approximation.
- Traditional bureau-only verdict and alternate-data verdict.
- A versioned `policy` object describing the actual decision rule.
- Policy guardrail status, including a real consent-verification detail (not a hardcoded pass).
- Decision path from bureau screen to credit-line recommendation.
- Optional AWS Bedrock-generated underwriter memo when configured, with deterministic fallback.

## Auditability

Every scoring call is appended to a **hash-chained** audit log (`backend/audit_log.py`): each entry's hash covers its own fields plus the previous entry's hash, so `audit_log.verify_chain()` detects retroactive edits to any past decision. `GET /audit-log` (full records, including borrower name) requires the `auditor` role via bearer-token auth (`backend/auth.py`); every public surface that touches audit data (e.g. `GET /governance`'s `latest_decision`) redacts the borrower name first.

`GET /governance` reports model version, runtime provider, live controls (including current chain-integrity status), audit count, fairness summary, pilot KPI *targets*, and deployment notes. `GET /model/status` returns the active model provider. `GET /model/evaluation` returns the real held-out metrics above.

## Fairness and monitoring

The demo includes a small synthetic-cohort fairness view grouped by sector, geography, vintage, gender where available, and bureau-history status (`GET /portfolio`, `GET /governance`). This is not a production fairness certification, and is separate from the PD model's own excluded-demographic-inputs design (see "Training data" above).

Monitoring APIs:

- `GET /model/evaluation`: real held-out AUC, Gini, KS, PR-AUC, Brier, calibration bins, and train-vs-OOT PSI drift on the trained model's own scores.
- `GET /validation/demo`: an explicitly-tagged (`evidence_type: illustrative_fixture`) 6+6 hand-built fixture, kept only to demonstrate the validation-report contract shape -- never shown next to real model claims.
- `POST /validation/report`: computes the same metrics on caller-submitted records (`evidence_type: submitted_batch_validation`).
- Pilot KPI tracking (`GET /pilot-metrics`): every field is tagged `status: pilot_target` with its formula and the minimum real sample size a measured claim would need -- these are not observed results.

**Disclosed, not faked**: true NTC/NTB slice validation and demographic-slice validation on the PD model are not computed, because the public proxy dataset has no NTC/NTB concept (every UCI row already has a bureau file) and demographic columns are deliberately excluded from training inputs. Faking either on the 5-10-row synthetic demo cohort would recreate the exact "fixture presented as evidence" problem this rewrite exists to fix. See `evaluation.json`'s `disclosed_gaps` field.

Production fairness sign-off still requires statistically meaningful IDBI sandbox volume and legally approved protected/proxy attributes.

## Known limitations

- The PD model's real default label comes from a public proxy dataset (personal credit-card defaults), not real Indian MSME outcomes -- see "What this proxy model does and does not prove" above. Coefficients are illustrative of a correctly-built pipeline, not production-calibrated for MSME lending.
- The fairness view is a demo-cohort monitor, not statistically significant.
- AWS Bedrock memo generation is optional and requires configured AWS credentials plus a Bedrock model ID; the deterministic underwriter memo remains the default fallback.
- API authentication (`backend/auth.py`) is a real, enforced bearer-token/role scheme sized for a public hackathon demo (no login flow, no per-underwriter session/identity), not full multi-tenant IDBI SSO -- see `docs/SECURITY_COMPLIANCE.md` for the disclosed scope and sandbox-phase upgrade path.

## Intended use

Decision support for MSME credit underwriting. The current prototype should not be treated as a fully automated approve/decline system without human review.
