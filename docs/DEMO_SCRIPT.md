# 3-Minute Demo Script

Use this for a voiceover recording or live judging walkthrough.

## 0:00-0:20 - Hook

"This is UdyamPulse, built for IDBI Innovate PS3. It solves the thin-file MSME problem: a viable New-to-Credit business can be rejected by traditional bureau-first underwriting even when its real cash-flow signals are healthy."

Open: https://id-ysm9.onrender.com

## 0:20-0:50 - Portfolio Impact

Point to the top impact strip:

"The public cohort has 5 MSME cases. In this synthetic portfolio, alternate data rescues 2 New-to-Credit firms and unlocks Rs 30,80,000 in viable credit that a bureau-only process would miss. The decision time target drops from a 7-day manual baseline to around 3 minutes."

## 0:50-1:30 - The Money-Shot Case

Select Shree Ganesh Textiles if it is not already active.

"This is the core reversal. Shree Ganesh Textiles has no bureau history, so the traditional bureau-only path rejects it immediately. UdyamPulse uses consented-style signals from GST, UPI, Account Aggregator-like bank statements, EPFO, and profile data. The alternate-data verdict approves the case with grade A, score 86 out of 100, and Rs 27,00,000 eligible working-capital limit."

## 1:30-2:05 - Explainability

Scroll within the decision pack.

"The decision is not a black-box score. The five-pillar card is descriptive; a separately calibrated monotonic XGBoost champion estimates proxy PD with native exact TreeSHAP; policy v2 then decides approve, review, or reject. The logistic challenger stays available as a deterministic fallback."

## 2:05-2:35 - Governance

Point to the right rail.

"For a bank, governance matters as much as prediction. UdyamPulse exposes calibrated XGBoost/TreeSHAP evidence, an untouched proxy holdout with confidence intervals, model-disagreement review, pseudonymised audit reconstruction, pilot targets, fairness slices, and source-level evidence. True dated out-of-time validation is explicitly pending IDBI sandbox outcomes."

## 2:35-2:55 - Borrower Actionability

Point to the memo and improvement plan.

"The borrower also gets an improvement plan, not just a rejection or approval. For weaker files, the system can show the action needed to improve the grade and potential limit."

## 2:55-3:00 - Close

"UdyamPulse is deployable today as a single FastAPI service on Render, tested with 61 automated tests. The next-phase outcome contract and temporal gates are live, while pilot mode safely refuses the public proxy until IDBI data, true OOT evidence, private credentials, and durable audit storage are present."
