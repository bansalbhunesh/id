# Model Card — UdyamPulse MSME Financial Health Model

## Purpose

Produces an explainable financial health score, credit grade, eligible
limit, and reason codes for an MSME from consented alternate data (bank
statements via Account Aggregator, GST filings, UPI transaction trails,
EPFO), aimed at New-to-Credit (NTC) and New-to-Bank (NTB) enterprises that
traditional bureau-based underwriting cannot evaluate.

## Model type

Two components, intentionally simple and fully auditable for the
prototype stage:

1. **Rule-based pillar scorer** (`backend/scoring.py`) — five weighted,
   hand-specified pillars (Liquidity, Discipline, Momentum, Leverage,
   Digital Footprint), each 0–20, summed to a 0–100 score with an A–E
   grade. Every threshold is inspectable in source.
2. **Linear PD-proxy model** (`backend/linear_model.py`) — an OLS
   regression fit on a synthetic training set, with **exact Shapley
   (SHAP-equivalent) feature attribution** computed in closed form
   (`weight_i × (x_i − mean_i)`), requiring no external ML library.

Both outputs are surfaced together so a reviewer can cross-check the
transparent rule engine against the learned model.

## Training data

Synthetic only (`backend/synthetic_training.py`), generated from a
domain-informed formula plus noise. **No real customer or bank data is
used in this prototype.** Stage 2 (post-shortlist) retrains on IDBI
sandbox AA/GST/UPI/EPFO data under the bank's data-governance controls.

## Explainability

Every score returns per-feature reason codes ("Strong" / "Watch" for the
rule-based pillars; ranked Shapley contributions for the ML layer) so an
underwriter or an applicant can see exactly why a score landed where it
did — directly answering RBI's draft Guidance on Model Risk Management,
which requires AI-assisted credit decisions to be "consistent, unbiased,
explainable and verifiable."

## Auditability

Every scoring call is appended to an audit log (`backend/audit_log.py`,
`backend/audit_log.jsonl`) with a timestamp, score, grade, both the
traditional and alternate-data verdicts, and the reason codes — so any
past decision can be reconstructed. Exposed via `GET /audit-log`.

## Known limitations (prototype stage)

- Trained on synthetic, not real, financial data — coefficients will be
  recalibrated once real AA/GST/UPI data is available.
- No formal fairness/bias audit has been run yet; Stage 2 roadmap
  includes a disparate-impact check across sector and geography.
- The linear model is intentionally simple for transparency; Stage 2
  swaps in a gradient-boosted model (XGBoost/LightGBM) with the `shap`
  library once real data volume justifies the added complexity —
  `linear_model.py`'s `fit` / `predict` / `shap_contributions` interface
  is designed to be a drop-in replacement target.

## Intended use

Decision support for MSME credit underwriting at IDBI Bank. Not intended
as a fully automated approve/decline system without human review at this
stage.
