# MSME Risk Model — Domination Roadmap

How SaakhScore's credit model goes from "honest proxy" to the strongest,
most-defensible MSME risk engine in the field, without ever faking IDBI data.

## 1. The problem we are fixing

The Round-1 PD model reduced credit risk to **three concepts (discipline,
leverage, liquidity) bridged from a Taiwan consumer credit-card dataset**. It
was reproducible and honest, but two structural weaknesses capped it:

1. **Wrong domain** — consumer credit cards, not small business.
2. **Thin + conduct-only** — three features, and the two most alternate-data
   signals in the pitch (GST momentum, UPI footprint) never entered the model.

Meanwhile the strongest competitors report higher AUC — but almost universally
on **synthetic labels** or a **single cross-sectional holdout**. Nobody in the
visible field validates on **real small-business default outcomes**, and nobody
validates **out of distribution**.

That is the seam we attack.

## 2. What is already shipped (this iteration)

A second, independent model — `sba_sme_pd_v1`, served at
`GET /model/sme-benchmark` — trains the **exact production methodology**
(monotone-constrained XGBoost, Platt calibration, native exact TreeSHAP,
logistic challenger) on **real U.S. SBA 7(a) small-business charge-offs**, and
validates it **out of distribution**:

| | Holdout (943 real loans) | Out-of-distribution (1,159 real loans) |
|---|---:|---:|
| ROC-AUC | **0.907** | **0.940** |
| KS | 0.712 | 0.795 |
| Brier | 0.116 | 0.148 |
| PSI (shift magnitude) | — | 0.63 |
| TreeSHAP reconstruction error | 2.15e-06 | — |

Nine leakage-free origination features, each with an economically-signed
monotone constraint; post-outcome leakage (`ChgOffPrinGr`) and the causal-study
`Selected` flag excluded. Honesty caveats (curated/balanced sample, term-
dominated loan-structure benchmark, proxy domain) are committed alongside the
metrics.

**Why this already changes the ranking:** it is the only evidence in the field
built on *real small-business defaults* and the only one validated *out of
distribution*. It converts our biggest disclosed weakness (no real-outcome, no
OOT) into a headline strength — truthfully.

## 3. Target architecture — the two-tower decision

The honest insight from building the SBA model: **loan-structure signals
(term, size, employees, collateral) and alternate-data conduct signals
(GST/UPI/AA/EPFO) are different feature families.** Forcing them through one
lossy 3-concept bridge is exactly what made the old model thin. The dominant
design keeps them as two explicit, separately-validated towers and fuses them
transparently:

```
Conduct tower  ── GST punctuality, GST-vs-bank divergence, UPI velocity,
   (alternate      counterparty breadth/concentration, cheque conduct,
    data)          cash-buffer days, inflow volatility
                        │
                        ├── calibrated PD_conduct  + exact SHAP
                        │
Structure tower ─ business age, employees, sector risk, requested tenor,
   (fundamentals)   loan-to-inflow, obligations/DSCR, collateral
                        │
                        └── calibrated PD_structure + exact SHAP
                        ▼
        transparent fusion (stacked calibrated logistic over the two PDs)
                        ▼
     PD  →  score/grade  →  policy (review/decline)  →  economic limit
```

Every tower stays independently auditable and independently validated. Fusion is
a calibrated logistic over the two PDs, so the contribution of each tower is
itself explainable. No LLM ever touches the decision path.

## 4. Phased plan

### Phase A — Now → shortlist (public, no IDBI data)
- **A1 (done):** real SBA benchmarks — v1 case-sample + OOD, superseded by the
  **v2 champion** on 418k loan-level records with true temporal OOT and
  recession stress (`/model/sme-benchmark`, `docs/research/BENCHMARK_REPORT.md`).
- **A2 (done):** momentum and digital-footprint now enter the risk path as a
  **capped, favorable-only, fully disclosed expert prior** on the trained PD
  (`conduct_prior` in every `ml` block); coefficients become fittable the
  moment dated sandbox outcomes arrive. Weak signals never inflate PD.
- **A3 (done):** **GST-vs-bank divergence** is computed from the sandbox feeds
  (and demoed on the public cohort), guarded at +/-25%, routed to review, and
  promoted to the underwriter's top next-best-action in both directions.
- **A4 (done):** the limit is now **EMI-capacity based** (existing-debt service
  estimate, policy rate/tenor annuity) with the grade multiple as a cap and a
  full `limit_basis` breakdown per decision; UI copy says "Indicative limit".
- **A5 (done):** bilingual (English + Hindi) reason codes, improvement actions,
  and next-best-action strings.

### Phase B — Sandbox (22–31 July, if shortlisted; real IDBI feeds)
- **B1:** run `/sandbox/recalibration/report` on real feature distributions.
- **B2:** run `/sandbox/pilot-readiness` to build **dated, chronological
  development / calibration / true-OOT cohorts** with 12-month outcome maturity.
- **B3:** retrain both towers on consented sandbox outcomes; the SBA model
  becomes the *transfer prior* / sanity anchor, not the served model.
- **B4:** **reject-inference** on declined applications so the model is not only
  fit on approved survivors (a gap most competitors ignore).
- **B5:** **segment models / monotone priors** by sector and vintage where volume
  supports it; fall back to the pooled model otherwise.

### Phase C — Pilot hardening
- **C1:** flip the promotion gates from label checks to real capability probes
  (durable append-only audit backend actually reachable; consent artefact actually
  verified), then let `SAAKHSCORE_MODE=pilot` pass honestly.
- **C2:** production monitoring: live PSI/AUC/KS drift, calibration drift, reason-
  code stability, and disparate-impact tracking with alert thresholds.
- **C3:** champion/challenger shadow scoring before any model swap.

## 5. Validation doctrine (what makes it defensible)

1. **Real outcomes first.** Every published metric is on a real default label
   (SBA now; IDBI outcomes later) — never a synthetic score regressed on itself.
2. **Out-of-time / out-of-distribution, always disclosed.** We already show OOD on
   real SBA; sandbox brings true dated OOT. A random holdout is never relabelled
   as OOT.
3. **Monotone constraints** so every feature's direction is a stated, testable
   economic assumption an underwriter can challenge.
4. **Exact TreeSHAP**, reconstruction-error-tested to < 1e-5, on every decision.
5. **Reject inference + calibration + fairness slices** as first-class evidence,
   not afterthoughts.
6. **Honesty caveats committed with the metrics**, so a strong AUC is never read
   as more than the sample supports.

## 6. Why this is ahead of the field (factual, not marketing)

| Axis | Common in the field | SaakhScore target |
|---|---|---|
| Label | synthetic, or one cross-sectional holdout | **real** SBA charge-offs now; real IDBI outcomes in sandbox |
| Generalisation | in-sample holdout only | **out-of-distribution** validated now; true dated OOT in sandbox |
| Feature families | one blended score | **two explicit towers** (conduct + structure), each audited |
| Explainability | SHAP on a slide | exact TreeSHAP, reconstruction-tested, on every response |
| Limit | score × constant | debt-service / EMI / expected-loss economics |
| Governance | described | machine-checked gates, pseudonymised hash-chained audit |
| Honesty | selective | caveats committed next to every metric |

We benchmark against competitors only from their **public** artifacts, and copy
no code, data, or branding — the edge is our own real-outcome evidence and the
two-tower design, not anyone else's implementation.

## 7. Reproduce

```bash
python backend/model_training/train_pd_model.py      # consumer-credit conduct proxy
python backend/model_training/train_sme_pd_model.py  # real SBA small-business + OOD benchmark
python -m pytest backend -q                           # full suite
```
