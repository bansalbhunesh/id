# Benchmark Report — `sba_sme_pd_v2`

**Date:** 2026-07-12 · **Branch:** `experiment` · **Registry:** `backend/model_training/experiments/registry.json` (19 tracked runs) · **Reproduce:** `python backend/model_training/experiments/fetch_foia_data.py && python backend/model_training/experiments/run_experiments.py && python backend/model_training/experiments/wave2.py && python backend/model_training/train_sme_pd_model_v2.py`

## 1. What was built

A successor to the v1 case-sample benchmark, selected by a registry-tracked,
significance-gated experiment programme over **418,947 resolved real SBA 7(a)
loans at natural base rates** (7.3% train / 9.4% OOT / 31.5% stress), with a
**genuinely later-in-time out-of-time window** (train FY2010–16 → test
FY2017–19) and a **recession stress cohort** (FY2005–07 vintages, 257k loans).
No synthetic labels anywhere. Every leakage risk is registered and excluded
(`ChargeoffDate`, `GrossChargeoffAmount`, `PaidinFullDate`, `LoanStatus`,
`SoldSecondMarketInd`; `InitialInterestRate` sensitivity-only).

## 2. Headline evidence (served artifact = evaluated artifact)

| Split | n | Base rate | AUC | KS | Brier | 30%-approval book |
|---|---:|---:|---:|---:|---:|---|
| Holdout (FY2010–16) | 45,626 | 7.3% | **0.9634** [0.9614, 0.9662] | 0.812 | 0.030 | — |
| **True OOT (FY2017–19)** | 114,770 | 9.4% | **0.9623** [0.9605, 0.9638] | 0.819 | 0.041 | **0.19% bad rate = 50.7× cleaner than population; 99.4% of defaults kept out** |
| Recession stress (FY2005–07) | 257,465 | 31.5% | **0.9255** | 0.712 | — | — |

Risk bands rank-order strictly on holdout and stress; OOT has one
2-basis-point B/C flip inside binomial noise (both strict and noise-aware
flags are committed). Served TreeSHAP reconstructs the logit exactly
(9.3e-08). Seed stability: AUC σ = 4e-05 across 5 seeds.

**Baselines under the identical protocol (DeLong-tested):**

| Model | OOT AUC | vs v2 |
|---|---:|---|
| Logistic, same features | 0.8571 | z = 51 |
| v1-recipe (blanket monotone, depth-3) | 0.9097 | **Δ +0.0526, z = 44.3** |
| Unconstrained XGBoost | 0.9603 | v2 better, z = 8.6 |
| **v2 (selective monotone, depth-7)** | **0.9623** | — |

## 3. Findings that drove the recipe (all in the registry)

1. **Selective monotonicity is the headline finding (E3/E3b).** Blanket
   economic constraints cost **5.2pp OOT AUC** because real SBA term-risk is
   non-monotone at the short end. Freeing `term_months` while keeping every
   defensible constraint beat *both* blanket constraints *and* the fully
   unconstrained model out-of-time (z = −8.6) and matched it under stress —
   constraints kept where they are true act as shift regularisation.
2. **Significance is not materiality (E6).** The 5-seed bag was
   "statistically better" (p = 0.046) by **0.0001 AUC** — a textbook large-n
   trap. The pre-registered gate (p < 0.05 **and** Δ ≥ 0.003) rejected it.
   Shroff's own artifact shows the opposite failure: an ensemble that *loses*
   to its logistic baseline yet leads their README.
3. **Calibration (E5):** large-sample hist-XGBoost was already tied-best
   calibrated in-distribution (ECE 0.0019); Platt *hurt* (0.0263); isotonic
   matched but breaks exact-SHAP linearity. OOT ECE (~0.03) is **base-rate
   drift** that no static calibrator fixes — the operational recalibration
   API remains the product answer. Identity calibration shipped.
4. **Reject inference is not a free lunch (E10 — negative result).** With
   selection simulated *on-support* (legacy policy on the same features),
   fuzzy parcelling **hurt** (−0.23pp OOT, z = −7.2), including on the
   rejected segment. It can only help when rejection used information outside
   the model's features (exactly the NTC/bureau case for the IDBI sandbox) —
   competitors implement it without ever measuring this.
5. **Shift is quantified, not assumed (E7).** Adversarial validation:
   train-vs-OOT shift AUC 0.737 (drivers: new-business mix, revolver mix);
   train-vs-stress 0.911 (regime change: collateral/fixed-rate era). Ranking
   power holds through both.
6. **Importance-weighted adaptation (E8)** gained +0.0018 OOT (z = 4.5) —
   significant, below materiality; recorded as a drift-regime challenger.
7. **Feature depth matters (E2):** structure-only → full 21 features =
   +5.6pp OOT (z = 39.8). The sensitivity run with the lender-priced interest
   rate is reported and excluded by design.
8. **Geographic OOD (E13):** trained ex-West, scoring West OOT: 0.9726 — no
   regional fragility. **Fairness monitoring (E15):** regional AUC gap 0.019;
   at one national cut-off, approval rates differ (25.5–38.0%) while book
   cleanliness stays uniform (0.12–0.33% bad) — the statistical-parity vs
   equal-risk trade-off is disclosed, and region is never a model input.
9. **Survival (E16):** annual discrete-time hazard produces
   **horizon-aligned PDs** (12m AUC 0.82 at a 0.10% event rate — with a
   disclosed ~6× over-prediction of the tiny 12m rate; 36m AUC 0.854),
   matching the product's dated `bad_12m` outcome contract; a lifetime binary
   cannot do this. Also the honest answer to resolved-only right-censoring.
10. **Stability caveat kept honest (E14 + corrected probe):** deep trees are
    locally sharp — ±5% noise on continuous inputs moves mean |ΔPD| by ~0.10.
    Partly real (±15 months of term *is* different risk), partly tree
    step-boundaries; disclosed rather than hidden.

## 4. Versus the visible competitor field

| Axis | Best visible competitor practice | This work |
|---|---|---|
| Labels | Synthetic personas (Shroff 8k, PARAKH, SehatAI 1k) | **418k real charge-offs, natural rates** |
| Temporal validity | Row-index "OOT" (Sedahoo), random splits | **True dated OOT + recession stress** |
| Model selection | Ensemble shipped despite losing to own baseline (Shroff artifact) | **Pre-registered DeLong + materiality gate; bag correctly rejected** |
| Constraints | Blanket monotone or none | **Selective monotonicity, empirically defended per feature** |
| Reject inference | Implemented, never measured | **Measured; honest negative result with theory-consistent explanation** |
| Uncertainty/stability | Rare | Bootstrap CIs, seed σ, perturbation probe, shift meters |
| Horizon alignment | Lifetime binary only | **12m/36m hazard PDs matching the product's outcome contract** |
| Verifiability | README claims | Registry + hashes + served-artifact == evaluated-artifact + live endpoint |

*(Competitor characterisations come from their own committed public artifacts,
verified by direct inspection; no competitor code, data, or branding is used.)*

## 5. Recommendation

**Ship `sba_sme_pd_v2` as the benchmark champion; keep v1 committed as the
baseline.** Evidence: +5.3pp OOT AUC over the v1 recipe (z = 44), +10.5pp over
logistic, stress-validated, stability-verified, exact-SHAP served, with every
selection decision pre-gated and recorded. Open challengers on the registry:
importance-weighted adaptation for drift regimes (E8) and the hazard model for
horizon-specific PDs (E16).

**Honesty boundary (unchanged):** US SBA small business is the closest public
real-outcome proxy to Indian MSME — this is methodology evidence at scale, not
an IDBI calibration. Resolved-only labelling right-censors slow late-vintage
outcomes (mitigated by E16). The v2 model scores loan-structure risk; the
served MSME decision keeps GST/UPI/EPFO conduct pillars separate. Retraining
on dated IDBI sandbox outcomes remains required before any pilot claim.
