# UdyamPulse — Content for the Official IDBI Innovate Deck

This maps directly onto **"Prototype Submission Deck _ IDBI Innovate.pdf"** — the official 15-slide template downloaded from the H2S portal (in `D:\Downloads`). Paste this content straight into that file; don't rebuild the template from scratch.

## Slide 1 — Team Details
- **Team name:** Looper
- **Team leader name:** Bhunesh Bansal
- **Problem Statement:** Problem Statement 3 — Financial Health Score

## Slide 2 — Brief about the idea
UdyamPulse is an AI-powered MSME Financial Health Card. It turns consented alternate data — GST filings, UPI transaction trails, Account Aggregator bank statements, EPFO records — into an explainable 0–100 health score, an A–E grade, an eligible credit limit, and a plain-language improvement plan. It's built specifically for New-to-Credit (NTC) and New-to-Bank (NTB) MSMEs: businesses with no bureau history that traditional underwriting rejects outright, even when their actual cash flows are healthy.

## Slide 3 — Opportunities
- **How different is it from existing ideas?** Most alternate-data scoring tools (Perfios, FinBox, HyperVerge) return a score. UdyamPulse returns a score a bank can *defend to a regulator* and a borrower can *act on* — every decision carries exact Shapley (SHAP-equivalent) reason codes, an audit trail, and a concrete improvement plan, not just a number.
- **How does it solve the problem?** It runs two independent, cross-checkable scoring methods side by side (a transparent rule engine + a trained ML model) and shows, explicitly, what a bureau-only process would have decided vs. what alternate data reveals — the rejected→approved contrast is the whole pitch in one screen.
- **USP:** Explainability and auditability are default behavior, not an afterthought. RBI's draft Guidance on Model Risk Management (Jun 2024) requires AI-assisted credit decisions to be "consistent, unbiased, explainable and verifiable" — yet of 127 AI-using regulated entities surveyed, only 15 use SHAP/LIME-style explainability and only 18 keep audit logs. UdyamPulse ships both by default.

## Slide 4 — List of features
- 5-pillar financial health score (Liquidity, Discipline, Momentum, Leverage, Digital Footprint) → 0–100 score, A–E grade
- Trained ML risk model with exact Shapley feature attribution (per-decision reason codes)
- Side-by-side traditional (bureau-only) vs. alternate-data verdict
- Eligible credit limit calculation
- Borrower-facing improvement plan (weakest pillar → concrete action → projected grade/limit uplift)
- AI-generated underwriter memo (plain-language summary for credit officers)
- Append-only audit log of every scoring decision (`GET /audit-log`)
- Model card documenting training data, limitations, and intended use

## Slide 5 — Process flow diagram
Flow: **Consented data intake** (AA bank statements + GST + UPI + EPFO) → **Feature engine** (5 pillars) → **Dual scoring** (rule engine + ML/Shapley model) → **Verdict comparison** (traditional vs. alternate-data) → **Underwriter memo + improvement plan generation** → **Audit log** → **Dashboard / health-card display**.
(Redraw this as a simple left-to-right box diagram — the README's ASCII version in the GitHub repo is the reference.)

## Slide 6 — Wireframes / mock diagrams (optional)
Use screenshots of the running app: the health card view (grade, score, eligible limit, traditional-vs-alternate verdict boxes) and the AI risk model / memo / improvement plan section below it.

## Slide 7 — Architecture diagram
Single-service architecture: FastAPI backend (Python) serving both the REST API and the static frontend, with a rule-based scorer, a linear ML model (Shapley attribution), an agent-memo generator, and an audit log module, all behind one process — deployable as a single Docker container or Vercel function. See `README.md`'s architecture section for the full box diagram.

## Slide 8 — Technologies used
Python, FastAPI, Pydantic, pytest (backend + API); vanilla HTML/CSS/JS (frontend, no build step); a dependency-free linear regression model with closed-form Shapley attribution (OLS via Gauss-Jordan elimination — no numpy/scikit-learn/shap required); Docker; Vercel (`@vercel/python`) for deployment; GitHub Actions for CI. Stage 2 targets: AWS Bedrock (agentic memo generation), XGBoost/LightGBM + `shap` (production-scale model), IDBI sandbox AA/GST/UPI/EPFO APIs.

## Slide 9 — Estimated implementation cost (optional)
Prototype cost: effectively zero (open-source stack, free-tier hosting). Stage 2 production estimate: AWS compute + Bedrock inference costs scale with transaction volume; exact figures depend on IDBI's sandbox data volume and are best scoped jointly during the mentorship phase.

## Slide 10 — Snapshots of the prototype
Capture fresh screenshots from the running app (`uvicorn main:app` locally, or the live Vercel URL):
1. Top of the health card for the NTC hero (Shree Ganesh Textiles) — shows grade A, ₹27,00,000 eligible limit, and the **Traditional: Rejected / UdyamPulse: Approved** side-by-side verdict boxes.
2. Scrolled down — the "AI risk model" Shapley reasons and the underwriter memo.
3. The borderline persona (Sunrise Auto Parts) — the "Improvement plan" section showing the concrete grade/limit uplift.

*Note: if using a screen-capture tool with a visible extension sidebar or toolbar in frame, crop it out before pasting into the deck.*

## Slide 11 — Prototype performance report / benchmarking
- 11 automated tests passing (pytest), covering scoring logic, ML weight recovery, the Shapley-sum invariant, the traditional-vs-alternate verdict, the improvement plan, and audit logging — enforced by CI on every push.
- ML model validated against known linear relationships (exact coefficient recovery) before being trusted on synthetic MSME data.
- Roadmap for real-data validation: report **KS statistic, AUC, and Gini coefficient** (the correct metrics for imbalanced credit risk — not raw accuracy) once trained on IDBI sandbox data.

## Slide 12 — Additional details / future development
Stage 2 roadmap (post-shortlist):
1. Swap synthetic data for IDBI sandbox AA/GST/UPI/EPFO feeds; recalibrate on real distributions.
2. Upgrade to a gradient-boosted model (XGBoost/LightGBM) with the `shap` library at production data volume.
3. Add fairness/disparate-impact auditing across sector and geography.
4. Add monitoring: score drift, population stability index (PSI).
5. Wire the underwriter memo to AWS Bedrock for richer, more nuanced narratives.
6. Pilot metrics: approval-rate lift on NTC/NTB, decision-time reduction, early-NPA guardrail — quantified against IDBI's book.

## Slide 13 — Links
- **GitHub Public Repository:** https://github.com/bansalbhunesh/id (already public, verified)
- **Demo Video Link (3 minutes):** record after the live deploy is up — walk through the NTC hero rejected→approved flow, the AI risk model reasons, the memo, and the improvement plan on the borderline persona.
- **Final Product Link:** pending — connect the Vercel dashboard to this repo (Add New Project → import `bansalbhunesh/id` → Framework: Other → Deploy); `vercel.json` is already configured.

---

**Before finalizing:** the official template's slide 13 explicitly asks for a **3-minute** demo video — plan the walkthrough script to that length, not shorter.
