# Real small-business default data — provenance

These two files are a cleaned, feature-reduced sample of the **U.S. Small
Business Administration (SBA) 7(a) loan program** loan-level records — real
small-business loans with a real charge-off (default) outcome label.

| File | Rows | Default rate | Role |
|---|---:|---:|---|
| `sba_real.csv` | 943 | 53.0% | Development / calibration / holdout (real SBA loans) |
| `sba_real_shift.csv` | 1,159 | 16.0% | **Out-of-distribution generalization test** (a differently-distributed real SBA sample) |

**Why this dataset.** No public dataset of real Indian MSME GST/UPI/EPFO
alternate-data with a repayment outcome exists — that gap is exactly what the
IDBI sandbox provides after shortlisting. The SBA 7(a) programme is the closest
**real small-business** default source in the public domain, and it is a strict
domain upgrade over consumer-credit proxies (it is small-business lending, not
individual credit cards). We use it to validate the *modelling methodology*
(monotone constraints, calibration, exact TreeSHAP, and out-of-distribution
robustness) on **real small-business default outcomes**.

**Label / leakage.** The target is `label` (1 = charged off / default). The
column `ChgOffPrinGr` (charged-off principal) is post-outcome leakage — it is
non-zero only after a default and matches the label 99.2% of the time — and is
**excluded** from all model inputs, as is the causal-study treatment indicator
`Selected`.

**Source.** Underlying data: U.S. SBA FOIA 7(a) loan records (public domain,
`data.sba.gov`), popularised by Li, Mickel & Taylor, *"Should This Loan be
Approved or Denied?"* (Journal of Statistics Education, 2018). The specific
cleaned/covariate-shifted split used here is redistributed from the public
`ngocbh/COPA` research repository. This is public small-business data only; it
contains no IDBI, MSME, Account Aggregator, GST, UPI, or EPFO data.

**Honesty boundary.** This is a real small-business proxy, not Indian MSME
outcomes. It demonstrates that the pipeline learns genuine default signal and
generalises under distribution shift; it is **not** a production calibration
for IDBI's book. Retraining on dated IDBI sandbox outcomes remains required.
