# UdyamPulse — Pitch Deck Outline

Build this directly into IDBI Innovate 2026's official PPT template (download it from the submission page) — don't restyle it; judges pattern-match to their own template. ~10 slides.

## 1. Title
UdyamPulse — team Looper. One line: "An explainable MSME Financial Health Card that turns consented alternate data into credit decisions traditional underwriting can't make."
Problem Statement 3: Financial Health Score.

## 2. The problem, quantified
- MSME credit gap: **₹25–30 lakh crore** (SIDBI); only **~14%** of MSME credit demand met through the formal financial ecosystem.
- Root cause: New-to-Credit (NTC) / New-to-Bank (NTB) enterprises have no bureau history — traditional underwriting declines them outright, even when their actual cash flows are healthy.
- Frame it as IDBI's problem: missed viable borrowers, limited portfolio diversification, slower financial inclusion progress (their own problem statement language).

## 3. The solution
UdyamPulse: consented alternate data (GST, UPI, Account Aggregator bank statements, EPFO) in → an explainable financial health score, an eligible credit line, and a plain-language improvement plan, out.
Hero visual: the health card UI screenshot.

## 4. How it works (architecture)
Use the diagram from `README.md`: ingest → 5-pillar rule engine + linear ML model with exact Shapley attribution → agentic underwriter memo → audit log → dashboard/health-card UI.
Say explicitly: two independent, cross-checkable scoring methods (transparent rules + a trained model), not a black box.

## 5. Live demo / prototype
2–3 screenshots of the running app (or the deployed link once live):
- Select the NTC hero business (Shree Ganesh Textiles)
- Show the side-by-side verdict: **Traditional: Rejected** (no bureau history) vs. **UdyamPulse: Approved**, grade A, ₹27L eligible limit
- Show the AI risk model's top Shapley reasons and the underwriter memo
This is the money-shot — spend real time on it live, don't just describe it.

## 6. The moat: explainability & auditability
- RBI's draft Guidance on Model Risk Management (Jun 2024) requires AI-assisted credit decisions to be "consistent, unbiased, explainable and verifiable."
- Of 127 AI-using regulated entities surveyed, only **15** use SHAP/LIME-style explainability and only **18** keep audit logs.
- UdyamPulse ships both by default: every score carries exact Shapley reason codes, and every decision is appended to an audit log (`GET /audit-log`) — see `MODEL_CARD.md`.

## 7. Impact / ROI for IDBI
- Approval rate lift on NTC/NTB segment (currently near-zero under bureau-only rules).
- Decision time: days (manual document review) → seconds.
- NPA guardrail: leverage/discipline pillars + PD-proxy model flag risk before disbursal, not after.
- Financial inclusion narrative: aligns with IDBI's PSU mandate and India's AA/GST/UPI digital-public-infrastructure push.

## 8. Feasibility
- Built entirely on live India-Stack rails: Account Aggregator (₹1.47 lakh crore disbursed Apr–Sep 2025, 780+ FIs, 269M+ consents), GST, UPI, EPFO — all production infrastructure today, not speculative.
- Prototype already running end-to-end (link + GitHub repo); sandbox-ready architecture for IDBI's real AA/GST/UPI/EPFO feeds post-shortlist.

## 9. Roadmap (Stage 2, post-shortlist)
1. Swap synthetic data for IDBI sandbox AA/GST/UPI/EPFO feeds; recalibrate on real distributions.
2. Harden the model: proper train/validate/out-of-time split; report **KS/AUC/Gini** (not raw accuracy — the right metrics for imbalanced credit risk).
3. Productionize on AWS: Bedrock for richer underwriter narratives, containerized ML service, RBAC on the dashboard.
4. Add monitoring: score drift, population stability index (PSI), a fairness dashboard.
5. Pilot metrics: approval-rate lift on NTC/NTB, decision-time reduction, early-NPA guardrail — quantified against IDBI's book.

## 10. Team + ask
Why Looper can execute (ship this fast, ship it clean — point at the GitHub repo, the CI badge, the test suite).
The ask: sandbox access + AWS credits + mentorship to take this from PoC to pilot.

---

**Judging spine to check every slide against** (four seats): would a *judge* call this clear, novel, and measurable? Would a *principal engineer* call it feasible, explainable, secure? Would a *product leader* see a real user and an adoption path? Would a *bank exec* see quantified ₹ impact, controlled risk, and regulatory readiness?
