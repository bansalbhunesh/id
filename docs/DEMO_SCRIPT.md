# 3-Minute Demo Script

Voiceover script + exact click path. Also usable as the shot list for a
screen recording or GIF. Live URL: https://id-ysm9.onrender.com

## 0:00-0:15 — Hook
*Shot: landing view, Shree Ganesh Textiles active.*

"This is UdyamPulse, built for IDBI Innovate PS3. It solves the thin-file MSME
problem: a viable New-to-Credit business gets rejected by bureau-first
underwriting even when its real cash-flow signals are healthy."

## 0:15-0:40 — Portfolio impact
*Shot: top impact strip.*

"Five public cases. Alternate data rescues 2 New-to-Credit firms and unlocks
Rs 30,23,000 of viable credit a bureau-only process would miss — and every
number on this screen is served by the same API a judge can curl."

## 0:40-1:15 — The reversal (money shot)
*Shot: decision stamp — Traditional: Rejected vs UdyamPulse: Approved.*

"The core case: Shree Ganesh Textiles, no bureau file, so the traditional
screen rejects it outright. Consented GST, UPI, bank-statement and EPFO-style
signals tell the truth: grade A, 86 out of 100, approved. The Rs 27,00,000
figure is an *indicative* limit — sized from spare EMI capacity at documented
policy inputs, with the grade multiple only as a cap. The full sizing
breakdown ships in the response."

## 1:15-1:45 — Explainability, in layers
*Shot: open the decision drawer; pillar ledger + reason codes + attribution.*

"No black box. The five-pillar card is descriptive. A separately calibrated
monotonic XGBoost estimates proxy PD with native exact TreeSHAP — the
attribution reconstructs the score to machine precision. Strong GST momentum
and UPI footprint earn a capped, fully disclosed *favorable-only* prior on
that PD: observed positive conduct can help a borrower, but thin digital
visibility never hurts one. And every reason code ships in English and Hindi
— this is an inclusion track."

## 1:45-2:15 — The other direction: catching the looks-fine case
*Shot: switch to City Corner Retail; point at the reconciliation guardrail.*

"Inclusion isn't just approving more — it's not being fooled. This retailer
declares 38% more turnover than its bank account actually sees. The
GST-vs-bank reconciliation guardrail flags it for review in both directions,
and it becomes the underwriter's top next action. Approve the invisible-but-
healthy, catch the looks-fine-but-failing."

## 2:15-2:45 — Evidence a bank can audit
*Shot: Governance tab, then Proof tab.*

"Governance is live data, not a slide: hash-chained pseudonymised audit,
fairness slices, fail-closed pilot gates. And the model evidence is real:
beyond the consumer-proxy holdout, the v2 benchmark is validated across
418,000 real SBA small-business loans, including a genuinely later-in-time
window — AUC 0.96 out-of-time, 0.93 through a recession stress cohort — with
the whole experiment registry committed. Real outcomes, real time axis,
honestly labelled as a proxy domain."

## 2:45-3:00 — Close
*Shot: Proof tab runbook / README badges.*

"UdyamPulse deploys today as one non-root FastAPI service, 115 automated
tests, container-smoked CI. Pilot mode refuses to start until IDBI data, true
OOT evidence, private credentials and durable audit storage exist — the
system is honest about what it is, and ready for what it becomes with sandbox
access. Thank you."

---

### Backend verification companion (for a technical judge)

```bash
curl https://id-ysm9.onrender.com/submission/proof      # capability + rubric map
curl https://id-ysm9.onrender.com/msmes/ntc_hero/score  # full decision packet
curl https://id-ysm9.onrender.com/model/sme-benchmark   # v2 real-outcome evidence
curl https://id-ysm9.onrender.com/deployment/readiness  # fail-closed gates
```

Demo-scoped credentials for the authenticated write routes:
`Authorization: Bearer udyampulse-demo-underwriter-key` (scores) and
`udyampulse-demo-auditor-key` (audit log). Real deployments override both via
`UDYAMPULSE_API_KEYS`.
