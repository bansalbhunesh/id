# IDBI Innovate 2026 First-Round Rules Check

Research checked on 09 July 2026.

## Public Sources Used

- Official event page: [IDBI Innovate 2026 on Hack2skill](https://hack2skill.com/event/idbinnovate)
- IDBI Bank public post: [MSME Inclusion Track announcement](https://www.linkedin.com/posts/idbi-bank_idbibank-idbiinnovate2026-bankinghackathon-activity-7479451537912721410-oI3E)
- Hack2skill public post: [Prize, mentorship, eligibility, deadline summary](https://www.linkedin.com/posts/hack2skill_idbiinnovate-hackathon-startupindia-activity-7472640963304251392-ccFV)
- Public program summary: [IDBI Innovate 2026 overview](https://www2.fundsforngos.org/innovation/idbi-innovate-2026-national-innovation-challenge-for-banking-solutions-india/)

No stable official Devpost page for IDBI Innovate 2026 was found in the current search. A similarly named "API Innovate 2026" Devpost page exists but is unrelated, so it is excluded from this submission checklist.

## First-Round Fit

| Rule / expectation | Evidence from public rules | UdyamPulse fit |
|---|---|---|
| Submit through the IDBI Innovate / Hack2skill flow by 09 July 2026 | The public event material points to Hack2skill registration and a 09 July 2026 deadline. | README, deck, live app, repo, model card, and demo links are organized for first-round submission. |
| Track alignment | IDBI's public post calls for an MSME Inclusion Track Financial Health Card using alternate data for faster credit decisions and finance access for underserved MSMEs. | UdyamPulse is explicitly PS3 MSME Financial Health Score, with GST, UPI, AA-style inflow, EPFO, bureau-history, geography, sector, vintage, and gender-available slices. |
| Real banking problem with measurable impact | Public summaries emphasize real banking problems, measurable outcomes, scalability, feasibility, business impact, and technical implementation. | The app quantifies NTC/NTB approval lift, decision-time reduction, credit unlocked, early-NPA guardrail, and portfolio diversification. |
| AI/ML or data-driven implementation | Public requirements emphasize AI/ML/data-driven banking solutions and implementation readiness. | Transparent five-pillar score plus calibrated monotonic XGBoost champion, native exact TreeSHAP, calibrated logistic fallback, random-holdout AUC 0.7497 with bootstrap interval, fairness slices, and explicit no-OOT-yet disclosure. |
| Sandbox APIs and datasets | Public summaries say shortlisted teams get sandbox APIs, synthetic datasets, cloud resources, and mentorship after shortlisting. | The repo does not pretend to have early access. It exposes feed normalization, recalibration, a dated outcome contract, and temporal readiness analysis ready for the July 22-31 sandbox window. |
| Technical implementation readiness | Evaluation summaries mention feasibility, scalability, business impact, and technical implementation. | Non-root FastAPI service, static frontend, Render Blueprint, readiness probe, two-job GitHub Actions, 115 tests, live deployment, model artifacts, temporal gates, screenshots, and submission deck are included. |
| Governance and compliance seriousness | Banking solutions are expected to be deployable, scalable, and credible in a regulated context. | Governance is visible in-product: roles, scoped consent, pseudonymised audit chain, score/PD/policy separation, evidence intervals, temporal/OOT gates, and fail-closed pilot promotion. |

## Submission Positioning

Use this wording in the first-round submission:

"UdyamPulse is first-round ready with a live public cohort and proof-grade API contracts. Official IDBI sandbox APIs and datasets appear to be granted after shortlisting; the project therefore does not claim private bank-data access, but already implements the ingestion, validation, recalibration, monitoring, and governance interfaces needed to plug those feeds in during the shortlisted build phase."
