# Competitive Research

This note records the public competitor scan used to shape UdyamPulse for IDBI Innovate 2026 PS3: MSME Financial Health Score. Last checked: 2026-07-09.

## Reviewed Repositories

| Repository | What it appears to cover | Gap UdyamPulse exploits |
| --- | --- | --- |
| [rohilkohli/msme-health-score](https://github.com/rohilkohli/msme-health-score) | React/FastAPI MSME health score platform with five dimensions, dashboard routes, and API surface. | Strong concept, but reads more like a broad platform skeleton than a single underwriter-ready bank decision pack. UdyamPulse focuses the demo on NTC rejected-to-approved reversal, audit reconstruction, and governance evidence. |
| [pixie0718/finhealth-ai](https://github.com/pixie0718/finhealth-ai) | Feature-rich FinHealth AI platform with alternate data, owner/lender workflows, audit log and SHAP claims in README. | Broad and ambitious, but heavier to validate quickly. UdyamPulse makes the live judge path tighter: one Render URL, one service, no frontend build dependency, deterministic scoring, exact reason codes, and committed PDF proof. |
| [Abhiroop-hgv/msme-health-card](https://github.com/Abhiroop-hgv/msme-health-card) | Lightweight React/Vite MSME health card prototype. | Useful visual prototype, but not enough bank/regulator depth. UdyamPulse adds API-backed score packs, policy guardrails, audit log, source map, fairness summary, and model card. |

## Contest Interpretation

The pasted H2S/IDBI submission plan and deck template sections were treated as the operating brief: Team Details, Brief, Opportunities, Features, Process Flow, Wireframes, Architecture, Technologies, Cost, Snapshots, Performance Report, Additional Details, and Links.

Public web search during this build did not surface a stable official Devpost, Unstop, or rules URL for the exact IDBI Innovate PS3 page, so the implementation avoids fragile contest-rule assumptions and anchors the submission to the problem statement, live prototype, model card, tests, and the required deck structure.

## Positioning Decision

UdyamPulse should not compete as "another credit score." It should compete as a banker-grade decision cockpit:

- Shows the exact rejected-by-bureau and approved-by-alternate-data contrast for a New-to-Credit MSME.
- Produces a health grade, eligible credit limit, reason codes, Shapley-style attribution, memo, improvement plan, source map, and policy guardrails in one screen.
- Ships audit and governance endpoints (`/audit-log`, `/portfolio`, `/governance`) rather than only a UI mock.
- Includes a model card, deterministic fallback logic, 15 passing tests, GitHub Actions, Render deployment, and `render.yaml` Blueprint.
- Keeps the demo resilient: single FastAPI service, static frontend, Dockerfile, no separate frontend build pipeline, no paid API dependency for the Stage 1 prototype.

## Final Submission Advantage

The repo now carries both product proof and submission proof:

- Live product: [https://id-ysm9.onrender.com](https://id-ysm9.onrender.com)
- Public repo: [https://github.com/bansalbhunesh/id](https://github.com/bansalbhunesh/id)
- Deck source: `docs/deck/index.html`
- Deck screenshots: `docs/deck/assets/`
- Model governance: `MODEL_CARD.md`
- Plain-text pitch: `docs/PITCH_OUTLINE.md`
