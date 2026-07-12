# Research Notes — successor to `sba_sme_pd_v1` (experiment branch)

Date: 2026-07-12. Scope: everything legally usable that could improve the SME
default model — competitor methodology autopsy (public artifacts only, no code
copied), literature anchors, data acquisition, and the experiment design that
follows from them. This file records *why* the experiments in
`backend/model_training/experiments/` exist.

---

## 1. Competitor methodology autopsy (public repos, verified by direct inspection)

We reproduce useful *techniques* with our own implementations and design
experiments that go beyond them. No competitor code, data, or branding is used.

### Shroff (Track 3 front-runner)
**What they do:** ~45 engineered features; four segment LightGBM sub-models
(cash-flow / growth / stability / compliance) + logistic meta-combiner;
isotonic calibration; 300–900 score; committed `metrics.json`.

**Verified weaknesses (from their own committed artifacts):**
- `metrics.json` reports `baseline_logreg` AUC **0.8671** vs `combined`
  ensemble **0.8560** on the same holdout — **their headline 4-model ensemble
  loses to their own plain logistic baseline.** The complexity is negative-value
  on their own evidence, and the README leads with the ensemble number anyway.
- Labels are synthetic (`"trained_on": "synthetic-v1"`); prevalence 10.24%,
  n_holdout = 1,600. No real outcomes, no out-of-time or out-of-distribution test.

**What we take (our own implementation) and exceed:** the sub-score/meta idea is
worth testing — but gated: we only accept added complexity if it beats the
simple baseline **with statistical significance (DeLong)**, the exact gate
Shroff's own artifact fails.

### Sedahoo / msme-health-card
**What they do:** LightGBM; *fuzzy-parcelling reject inference* (Feelders 2000,
Hand & Henley 1997 — correctly described, iterated 3×); conformal intervals;
PSI audit.

**Verified weaknesses:** their "out-of-time" audit is a **row-index split
explicitly commented `"no real date col so we use row index as time proxy"`**
on a shuffled synthetic frame — i.e., not temporal at all. No backend tests.

**Take & exceed:** implement fuzzy-parcelling reject inference ourselves — but
on **real loans with a real simulated approval policy**, and evaluate the
corrected model on the *full* population (they never do), with **genuinely
dated temporal splits** from `ApprovalDate`.

### PARAKH (IHRM-AI)
**What they do:** real statistical tooling — **DeLong AUC-difference test**
(midrank implementation, verified against sklearn), **source-ablation ladder
with bootstrap CIs**, stability and fairness test modules.

**Verified weaknesses:** synthetic persona data; the trained artifacts/evidence
the README claims are not committed; local install was not reproducible in the
prior audit.

**Take & exceed:** DeLong significance testing and ablation ladders — computed
on **real charge-off outcomes** and committed as artifacts, not just test
scaffolding.

### SehatAI
**What they do:** deterministic engine; honest small-print; **band bad-rate
monotonicity** check; gains/lift tables; "Credit-Invisible Lift" operating
metric; challenger file.

**Verified weaknesses:** n = 1,000 synthetic rows (700 train / 300 test),
AUC 0.783; no temporal dimension; no security/test surface around the engine.

**Take & exceed:** operating-point metrics (approval-rate sweeps, bad-rate in
the approved book, band monotonicity) — reported on **real data at 100–500×
their sample size** with temporal OOT.

### Synthesis — the seam nobody occupies
Every visible competitor validates on synthetic labels and/or a single
cross-sectional random split. **No one shows: real outcomes + true dated
out-of-time + out-of-distribution stress + significance-gated model selection.**
That combination is the successor's design brief.

---

## 2. Literature anchors

- **Li, Mickel & Taylor (2018), JSE** — "Should This Loan be Approved or
  Denied?": establishes SBA 7(a) as a real, teachable default-modeling corpus;
  the widely-mirrored `sba.csv`/`sba_shift.csv` case split derives from it
  (our v1 training data). Known base rates: ~18% population charge-off vs ~53%
  in the balanced case sample.
- **Reject inference:** Feelders (2000); Hand & Henley (1997) — fuzzy
  parcelling / augmentation as standard corrections for approved-only training.
- **Calibration:** Platt scaling vs isotonic regression (PAVA); isotonic wins
  with enough calibration data, Platt safer on small samples — we test both.
- **DeLong, DeLong & Clarke-Pearson (1988):** nonparametric covariance of
  correlated AUCs — the correct test for "is model B really better than A on
  the same holdout".
- **Adversarial validation** (Kaggle practice, formalised in covariate-shift
  literature): train a classifier to separate train vs test rows; its AUC is a
  shift meter and its propensities give importance weights (Shimodaira 2000).
- Public ML papers on generic loan-default corpora report a wide 0.64–0.97 AUC
  band, frequently inflated by post-outcome fields; we therefore anchor to our
  **own leakage-audited baselines** rather than external headline numbers.

---

## 3. Data acquisition (all public-domain / legally clean)

| Source | Status | Rows | Why |
|---|---|---|---|
| SBA 7(a) case sample (`sba_real.csv` + shift) | committed (v1) | 943 + 1,159 | v1 baseline; like-for-like comparison |
| **SBA 7(a) FOIA loan-level, FY2000–FY2009** (as-of 2025-09-30) | downloaded | ~690k | recession-era originations → stress cohort |
| **SBA 7(a) FOIA loan-level, FY2010–FY2019** (as-of 2025-09-30) | downloaded | ~540k | modern originations → primary train/temporal-OOT |
| SBA 7(a) FOIA FY2020–present | downloaded | ~450k | immature outcomes; used only for census/shift meters, never for label training without maturity filtering |
| UCI credit-card default (30k) | already in repo pipeline | 30k | conduct-tower proxy (v1 pillar model, unchanged) |

Provenance: official U.S. SBA FOIA releases (public domain), retrieved from the
Internet Archive's January 2026 capture of `data.sba.gov` after the live portal
migration removed the loan-level pages. SHA-256 manifests + a fetch script are
committed; the raw files stay out of git (~600 MB).

**Schema highlights** (loan-level): `ApprovalDate/ApprovalFY` (true time axis),
`LoanStatus` (PIF/CHGOFF), `TerminMonths`, `GrossApproval`,
`SBAGuaranteedApproval`, `InitialInterestRate`, `NAICSCode`, `BusinessType`,
`BusinessAge`, `ProjectState`, `CollateralInd`, `RevolverStatus`,
`JobsSupported`, `FixedorVariableInterestRate`.

**Leakage register (excluded from all models):** `ChargeoffDate`,
`GrossChargeoffAmount`, `PaidinFullDate`, `LoanStatus`-derived anything,
`AsOfDate`. **Flagged/sensitivity-only:** `InitialInterestRate` encodes the
lender's contemporaneous risk view (not a borrower attribute) — we run with and
without it and report both; `SoldSecondMarketInd` may be post-origination —
excluded. **Maturity rule:** a loan only enters the labelled set if it is
charged off OR was approved ≥ `term + 12m` before the as-of date OR is paid in
full; immature rows are excluded from labels (right-censoring guard). Survival
experiments use time-to-chargeoff explicitly instead.

---

## 4. Experiment design (what runs, and why)

Registry-driven runner in `backend/model_training/experiments/`; every run
records config, seed, git rev, data hash, metrics, and failure reasons to
`registry.json`. Multi-metric scoreboard — AUC, KS, PR-AUC, Brier, ECE, lift,
**recall at 20/30/40% approval-rate operating points, bad-rate in the approved
book**, band monotonicity, temporal-OOT degradation, seed stability — because a
model that only wins headline AUC is not a win.

Planned families (E-numbers referenced by the registry):
- **E1 baselines:** v1 recipe re-run under the new protocol; plain logistic.
- **E2 features:** national-schema feature set; ablation ladder ± CIs; with/
  without `InitialInterestRate`.
- **E3 constraints:** monotone vs unconstrained XGBoost (DeLong-gated).
- **E4 capacity sweep:** depth/eta/rounds/min_child_weight (small seeded grid).
- **E5 calibration:** none vs Platt vs isotonic (PAVA, ours) on ECE/Brier.
- **E6 ensembles:** seed-bagged XGBoost; XGB+logistic stack — accepted only if
  DeLong-significant over the simpler option (the anti-Shroff gate).
- **E7 adversarial validation:** train-vs-OOT classifier AUC as shift meter;
  top shift drivers reported.
- **E8 domain adaptation:** importance weighting from E7 propensities.
- **E9 uncertainty:** bootstrap PD intervals; interval width vs error.
- **E10 reject inference:** simulate a realistic approval policy on FY2010–14,
  train approved-only vs fuzzy-parcelling, evaluate on the full population.
- **E11 temporal OOT:** train FY2010–2016 → test FY2017–2019 (mature only).
- **E12 stress:** score FY2005–2007 recession-vintage originations; report
  degradation vs the modern holdout.
- **E13 geographic OOD:** leave-region-out (state buckets).
- **E14 stability:** seed variance; ±5% input perturbation sensitivity.
- **E15 fairness proxies:** rural/urban and state-region monitoring
  (approval-rate, FPR, AUC gaps) — monitoring only, never model inputs.
- **E16 survival:** discrete-time hazard on time-to-chargeoff; lets immature
  loans contribute censored information instead of being discarded.

Selection rule for the successor: best **worst-case rank** across (holdout,
temporal-OOT, stress) on the multi-metric scoreboard, with complexity accepted
only under DeLong significance, calibration accepted on ECE, and the final
recipe re-run end-to-end from raw data for reproducibility.

---

## 5. Honesty boundary (unchanged)

US SBA lending is a *proxy domain* for Indian MSME. These experiments prove the
methodology on real small-business defaults at scale — they are not an IDBI
calibration. Research-sample results (balanced case sample) are always labelled
separately from population-rate results (national FOIA). The v1 benchmark stays
committed as the baseline for like-for-like comparison.
