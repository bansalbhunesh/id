# Route → API → UI Feature Matrix — Phase 2 (branch `frontend-audit-rebuild`)

Built from a full read of `frontend/app.js` (831 lines), `frontend/index.html`,
`backend/main.py` route table, and live payload inspection of every endpoint.
Verdicts: **EXPOSED** (works, visible) · **HIDDEN** (stable backend, no UI) ·
**PARTIAL** (fetched, materially under-rendered) · **COPY-ONLY** (described in
prose, no surface) · **N/A** (ops/auth surface, correctly out of the public UI).

## A. Endpoint coverage

| Endpoint | Backend | Frontend today | Verdict |
|---|---|---|---|
| `GET /msmes`, `GET /msmes/{id}/score` | Full decision packet | Case list, stage card, decision/evidence drawers | **EXPOSED** (fields under-rendered — see B) |
| `GET /portfolio` | Impact + cases + pilot targets | Impact ribbon, case list | **EXPOSED** |
| `GET /governance` | Audit, controls, fairness rates, deployment | Governance drawer | **EXPOSED** |
| `GET /deployment/readiness` | Fail-closed gates | Gates journal in Governance | **EXPOSED** |
| `GET /submission/proof` | Rubric, truth boundary, runbook, API catalog | Proof drawer | **EXPOSED** |
| `GET /model/evaluation` | Holdout metrics, **bootstrap CIs, champion-vs-challenger candidates, per-group fairness (AUC/Brier/FPR by gender & age), policy threshold, artifacts** | Only 7 holdout numbers + PSI + one design note | **PARTIAL** — CIs, candidate comparison, fairness slices, threshold objective all unrendered |
| **`GET /model/sme-benchmark`** | **Flagship v2 champion: OOT 0.9623/KS 0.82, stress 0.9255, CIs, DeLong-tested baselines, selective-monotonicity rationale, integrity hashes, v1 baseline** | **Never fetched. Not one pixel.** | **HIDDEN — the single largest gap.** The deck and README lead with evidence the product never shows. |
| `GET /model/status` | Champion metadata | One status word in the header | **PARTIAL** (acceptable) |
| `GET /health` | Release version + commit + mode | Status dot only; release/commit unshown | **PARTIAL** (minor — add to footer) |
| `GET /sandbox/outcome-contract` | Dated-label schema, maturity rule, split policy | One journal row in Sources | **PARTIAL** (acceptable) |
| `POST /sandbox/score` | Underwriter-authenticated AA/GST/UPI/EPFO scoring | Mentioned in Sources copy only | **COPY-ONLY → build**: an interactive underwriter console is feasible with the documented demo key; real request, real 401 states, renders the same packet renderers |
| `POST /score` | Underwriter custom scoring | None | **COPY-ONLY** (served by the same console) |
| `POST /sandbox/recalibration/report`, `POST /sandbox/pilot-readiness`, `POST /validation/report` | Authenticated write/report paths | Prose mentions | **N/A for public UI** (correct; console copy links them) |
| `GET /audit-log` | Auditor-gated trail | Count via governance | **N/A** (role-gated by design) |
| `GET /validation/demo` | Fixture contract | None | **N/A** (developer surface) |
| `GET /health/live`, `/health/ready` | Probes | None | **N/A** (ops) |
| `GET /pilot-metrics` | Pilot targets | Duplicated via `/portfolio` + `/governance` | **N/A** (already surfaced) |

## B. Score-packet fields fetched but never (or barely) rendered

| Field | Payload reality (verified live) | UI today | Action |
|---|---|---|---|
| `reasons_vernacular[].hi/en` | Full Hindi + English reason codes per pillar | **Never rendered** | EN/हिंदी toggle in decision packet |
| `next_best_action.action_hi` | Hindi next step | Never rendered | Same toggle |
| `limit_basis.*` | Complete EMI sizing ledger: affordable EMI ₹112,010, capacity limit ₹34,21,356, grade cap ₹27,00,000, binding constraint, policy inputs (11% / 36m / 25% share), concentration multiplier, honesty note | One 6-word caption ("Sized by grade policy cap") | Full "How this limit was sized" ledger — this is the anti-"score × constant" story |
| `traditional.reason` | e.g. "No credit bureau history on file (NTC/NTB)." | Never rendered (decision word only) | Show under the traditional stamp |
| `next_best_action.urgency` | rendered ✓ | — | keep |

## C. Duplicate / dead / placeholder UI

- `#decisionStamp` inside the drawer repeats grade/score/limit/model already on
  the stage card — same data twice, one modal apart (consolidate in rebuild).
- Hard-coded fallback improvement copy in `renderDecisionTab` when
  `improvement_plan` is absent (acceptable fallback; keep but mark as generic).
- "Retry connection" reloads the whole page (coarse; acceptable).
- `#drawerToggle` is `display:none` at mobile widths — dead control on phones.
- No unreachable routes found; no mocked/fake data found anywhere (all rendered
  numbers trace to live endpoints — verified in Phase 1).

## D. Genuinely unsupported (do NOT build)

- Client-side auth/login flows, per-underwriter identity, audit-log browsing —
  the backend intentionally scopes these to bearer keys / auditor role; a public
  UI would require inventing identity the backend doesn't have.
- Any IDBI/sandbox real-data views — backend truthfully has no such data;
  pilot-gate panels must keep saying so.

## E. Phase 3 build list (stable backend → missing production UI)

1. **Model-evidence panel for `/model/sme-benchmark`** — v2 OOT/holdout/stress
   with CIs and n's, DeLong-tested baseline table, selective-monotonicity
   rationale, artifact-integrity status, v1 baseline, honest US-proxy caveat.
2. **Deepen `/model/evaluation` rendering** — bootstrap CIs beside each metric,
   candidate (champion vs logistic) comparison, per-group fairness table
   (gender/age: AUC, Brier, FPR, capture), threshold objective line.
3. **Bilingual reasons** — EN/हिंदी toggle for reason codes + next best action.
4. **Limit-basis ledger** — the full EMI-capacity sizing math under the limit.
5. **Traditional-rejection reason** — one line under the rejected stamp.
6. **Underwriter console** — real `POST /sandbox/score` with key field
   (prefilled demo key label, documented in DEMO_SCRIPT), editable example
   payload, loading/401/422/success states, response rendered through the
   existing packet renderers. No mocks: errors render as errors.
7. **Footer release line** — version + commit from `/health`.
