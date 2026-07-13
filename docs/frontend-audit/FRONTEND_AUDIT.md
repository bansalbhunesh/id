# Frontend Baseline Audit — Phase 1 (branch `frontend-audit-rebuild`)

Method: real Playwright (Python, Chromium 149) against the app served locally
(`uvicorn main:app --port 8123` from `backend/`). Three viewports — desktop
1440x900, tablet 834x1112, mobile 390x844. Every nav tab, every borrower case,
the review drawer, deep links, keyboard traversal, console + network capture,
and an axe-core 4.10 scan (wcag2a / wcag2aa / wcag21aa) per surface.
Raw machine findings: [`before/findings.json`](before/findings.json).
Baseline screenshots: [`before/`](before/). Full 33-shot set is reproducible
with the commands at the bottom.

## Findings

### F1 — The entire product lives inside a 560px modal (high, information architecture)

Every one of the five nav "tabs" (Decision, Evidence, Governance, Proof,
Sources) opens the same right-hand modal drawer over an unchanging main stage
(`setTab(tab, openDrawer=true)` — `app.js`). Measured drawer content:
Evidence 1,772 chars, Governance 3,279, **Proof 6,716** — the deepest
judge-facing evidence in the product renders into ~560px while ~880px of
desktop stage shows a static summary card. Consequences, all machine-verified:

- While the drawer is open the scrim covers the nav, so a **mouse user cannot
  switch tabs without closing the drawer first** (Playwright click on
  `#tab-evidence` times out: "`#drawerScrim` intercepts pointer events");
  arrow keys *do* switch tabs while open — inconsistent input paths.
- The flagship capabilities judges must find (benchmark evidence, governance
  gates, proof catalog) are all one modal deep with no visual preview.
- On mobile the dedicated "Review packet" launcher is `display:none`, leaving
  the tabs as the only entry into all detail content.

### F2 — External font dependency with intermittent CSP noise (medium, robustness)

Typography (Source Sans 3, Libre Baskerville, Azeret Mono) loads from
fonts.googleapis.com/fonts.gstatic.com. During the full audit run, Chromium
logged `connect-src 'self'` CSP violations for the css2 stylesheet on **all
three viewports** (recorded in findings.json) though fonts did load in
follow-up probes — an intermittent speculative-fetch failure that spams the
console judges may have open. If the CDN is slow/unreachable the design
silently collapses to system fonts. Separately, the first live visit after
idle shows **Render's free-tier cold-start interstitial** (observed during
the audit: Render-branded waking page with Roobert/Neue Montreal fonts).
Fix direction: self-host WOFF2 subsets (same-origin satisfies the existing
CSP), and keep the service warm during judging windows.

### F3 — Backend capabilities invisible in the UI (high, feature exposure — expanded in Phase 2 matrix)

Confirmed against live payloads: bilingual Hindi reason codes
(`reasons_vernacular[].hi`, `next_best_action.action_hi`) are served for every
case and rendered nowhere; the EMI `limit_basis` breakdown and the
`/model/sme-benchmark` v2 evidence depth need the Phase 2 matrix (see
`FEATURE_MATRIX.md`).

### F4 — Strong technical baseline worth preserving (positive)

- **axe-core: 0 violations** (wcag2a/aa/21aa) on landing, governance view and
  open drawer, at all three viewports.
- No horizontal overflow at any viewport (scrollWidth checks pass).
- Deep links work: `/?case=stressed_retailer&view=evidence` restores case,
  tab selection and drawer state.
- `prefers-reduced-motion` CSS exists; focus outlines are visible (3px solid);
  the drawer traps focus correctly and Escape closes it.
- Console is clean apart from the font CSP noise; zero failed same-origin
  requests; all five cases render correct decision states.
- The GST-vs-bank divergence row is present and findable for City Corner
  Retail on the Evidence view at every viewport.

## Reproduce

```bash
cd backend && ../.venv/Scripts/python -m uvicorn main:app --port 8123   # serve
pip install playwright && playwright install chromium                  # once
python <audit script>   # writes screenshots + findings.json (script content
                        # preserved as e2e tests under e2e/ from Phase 5 on)
```
