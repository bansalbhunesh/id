# Frontend Rebuild Report — branch `frontend-audit-rebuild`

Evidence-first reconstruction in six phases, each committed and pushed:
Playwright baseline audit (`c84f6e1`) → feature matrix (`8b10d99`) → hidden-
capability surfacing (`8ebc468`) → two-rail workspace + self-hosted type
(`fce5388`) → unit/e2e test suites (`8f17c3d`) → critique fixes + this report.

## Before / after

Baseline screenshots: [`before/`](before/) · Final: [`after/`](after/)

| Axis | Before (main) | After (this branch) |
|---|---|---|
| Information architecture | All five views open a 560px **modal drawer** over a static stage; scrim blocks mouse tab-switching while open; "Review packet" launcher hidden on mobile | Permanent two-rail workspace: decision stage + always-visible review packet with file-divider tabs; packet stacks below the stage on narrow screens; zero modals |
| Flagship evidence | `/model/sme-benchmark` **never fetched** — the v2 champion (OOT 0.9623) invisible in-product | Dedicated **Model** tab: OOT/holdout/stress with bootstrap CIs and n's, DeLong-tested baselines, monotonicity rationale, artifact-integrity status, v1 baseline, honesty caveat |
| Bilingual inclusion | `reasons_vernacular` served, never rendered | English/हिन्दी toggle on reason codes + next best action, rendered in a committed Devanagari face |
| Limit credibility | "Sized by grade policy cap" (6 words) | Full EMI-capacity ledger: affordable EMI, capacity limit vs grade cap, policy inputs, binding constraint, honesty note |
| Decision workflow | Read-only demo | Live underwriter console: real `POST /sandbox/score` with key field, editable payload, loading/401/422/success states — errors render as errors |
| Fonts / robustness | Google Fonts CDN; intermittent CSP `connect-src` console errors; design collapses to system fonts offline | Six committed WOFF2 subsets (356KB incl. Devanagari); **zero external requests**; CSP tightened to `style-src 'self'` / `font-src 'self'` |
| Duplicate UI | Drawer decision stamp repeated the stage verdict | Removed (single verdict card); drawer/scrim/focus-trap machinery deleted (net −118 lines in Phase 4) |
| Fairness evidence | Approval-rate proxies only | Outcome-linked per-group table (AUC/Brier/FPR/n by gender & age) + max-gap headline from the evaluation artifact |

## Verification (all machine-checked, reproducible below)

- **Backend suite: 115 passed** — unchanged contract, CSP change covered.
- **Frontend unit suite: 9 passed** (`node --test frontend/tests/lib.test.mjs`) — escaping, INR grouping, status mapping, CI formatting, bilingual fallbacks, constraint copy.
- **Playwright e2e: 12 passed** (`python -m pytest e2e -q`, ~50s) — boots its own uvicorn with an **isolated audit-log path**; asserts live-rendered content only: all six tabs by mouse, benchmark numbers, Hindi toggle, EMI ledger, +38% divergence row, console auth flow (missing key → 401 → real scored packet), deep links, keyboard arrows, mobile stacking, zero external requests, self-hosted fonts.
- **Accessibility: axe-core 0 violations** (wcag2a / wcag2aa / wcag21aa) at desktop and mobile, landing + governance + packet; visible 3px focus ring ≥3:1; `prefers-reduced-motion` honoured; semantic tablist/tabpanel; skip link.
- **Responsive**: no horizontal overflow at 1440 / 834 / 390 (asserted); packet reflows to a stacked section, not an amputated modal.
- **Design-system checks**: no side-stripe accents, no gradient text, no glassmorphism-as-decoration, tabular numerals on all figures, one orchestrated motion (verdict stamp press).

## Remaining genuine backend gaps (deliberately NOT faked in the UI)

- No per-underwriter identity/SSO — bearer-key roles only; a login UI would invent state the backend doesn't have.
- `/audit-log` browsing stays auditor-gated by design; the UI shows the hash-chained event count from `/governance`.
- No IDBI/sandbox real data anywhere — pilot gates keep saying so; the packet's truth boundary is unchanged.
- `POST /sandbox/recalibration/report` and `POST /validation/report` remain API-first surfaces (documented, linked, not rendered as forms — they return analyst artifacts, not judge moments).

## Incident worth knowing about

Running the e2e suite while a dev server appended to the same
`backend/audit_log.jsonl` corrupted the hash chain — and the audit system
**detected it and failed closed**, exactly as designed. Fix: the e2e fixture
now gives each spawned server its own `UDYAMPULSE_AUDIT_LOG_PATH`; the
corrupted runtime file was deleted and regenerates from genesis.

## Reproduce everything

```bash
# serve locally (from backend/)
python -m uvicorn main:app --port 8123

# backend suite
python -m pytest backend -q                       # 115 passed

# frontend unit suite (Node 20+)
node --test frontend/tests/lib.test.mjs           # 9 passed

# frontend e2e (Playwright; boots its own server)
pip install -r e2e/requirements.txt
playwright install chromium
python -m pytest e2e -q                           # 12 passed
```

Feature inventory and verdicts: [`FEATURE_MATRIX.md`](FEATURE_MATRIX.md).
Baseline findings and method: [`FRONTEND_AUDIT.md`](FRONTEND_AUDIT.md).
