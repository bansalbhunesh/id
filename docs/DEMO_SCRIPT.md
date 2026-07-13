# 3-Minute Video Script

Voiceover + exact screen path for the demo video. Speak calmly (~140 words/min);
confidence is quiet. `[SHOW]` = what is on screen. Live URL:
https://id-ysm9.onrender.com

**Prep — keep five tabs ready to switch instantly:**

1. Live app — https://id-ysm9.onrender.com (Shree Ganesh Textiles is the default
   case; the review packet is permanently open beside the stage)
2. Terminal with this typed, ready to press Enter: `curl https://id-ysm9.onrender.com/submission/proof`
3. GitHub repo README — green tests badge visible
4. GitHub — `backend/model_training/experiments/` folder
5. Browser — https://id-ysm9.onrender.com/deployment/readiness

## 0:00–0:15 — Cold open: two facts and a promise

*[SHOW: live app, Shree Ganesh Textiles. No introduction — just start.]*

"Two facts. This textile shop in Surat makes money **every single day**.
And no bank will lend it a **single rupee**.
In the next three minutes, we're going to fix that — **live** —
and prove every number we say."

## 0:15–0:35 — Name the villain: the loop

*[SHOW: the "Traditional: Rejected" stamp. Hold on it.]*

"Here's why the bank says no. To get a loan, you need credit history.
To get credit history… you need a loan.
Millions of Indian MSMEs are trapped in this loop —
invisible to banks, no matter how healthy they are.
Nobody breaks the loop. So we did."

## 0:35–1:05 — Break it, live

*[SHOW: the reversal — Rejected → Approved — then the score card, slowly.]*

*[Optionally flash the **Sources** tab here — the consented GST/UPI/AA/EPFO
source map — then return to Decision.]*

"UdyamPulse reads the proof this business creates every day —
GST bills, UPI payments, bank inflows — with the owner's permission —
and turns it into a **Financial Health Card**.
Same shop. New answer: **86 out of 100. Grade A. Approved.**
A limit of **27 lakh rupees**, sized from the EMI it can actually repay.
The old process took **seven days**. This took **three minutes**."

## 1:05–1:25 — The dare

*[SHOW: zoom on the browser URL bar: id-ysm9.onrender.com]*

"Now — don't trust a video. Videos can fake anything.
**Pause right here.** Open this address on your phone.
Everything you just saw is running there, right now, for anyone.
Go ahead. We'll wait."

*(beat — one full second of silence)*

"That's proof one: **it's live.**"

## 1:25–1:45 — It explains itself, in your language

*[SHOW: the review packet beside the stage — five-pillar ledger and reason
codes. On "in English and in Hindi", click the **हिन्दी** toggle in the
Reason-code journal: the reasons switch to Devanagari on screen. Click back
to English.]*

"And it's not a black box.
Every decision comes with reasons — what's strong, what's weak,
what to improve — in **English and in Hindi**.
The banker gets evidence. The owner gets a roadmap."

## 1:45–2:00 — It catches liars too

*[SHOW: pick "City Corner Retail" from the borrower strip, click the
**Evidence** tab in the packet — under "Policy guardrails", the row
"GST-vs-bank turnover reconciliation" reads **Review** — "GST-declared
turnover runs +38% versus bank-observed inflow". Point the cursor at it.]*

"It works in both directions.
This shop claims high sales on paper — its bank account disagrees.
UdyamPulse catches the gap and flags it for review.
Approve the invisible-but-honest. Catch the impressive-but-fake."

## 2:00–2:35 — The proof gauntlet

*[SHOW: Tab 2 — press Enter; the JSON fills the screen.]*

"Proof two: **ask our backend, not our slides.**
One command, and the running system returns every claim in this video."

*[SHOW: Tab 3 — GitHub README, zoom on the green tests badge.]*

"Proof three: **the code is public.**
**127 automated backend tests** run on every change — the green tick is
machine-checked, not self-declared. (150 in all, with the UI suites.)"

*[SHOW: the app's **Model** tab — OOT AUC 0.9623 with intervals on screen —
then Tab 4, the experiments folder on GitHub, scroll slowly.]*

"Proof four: **real data.**
Validated against **more than 4 lakh real small-business loans** —
including recession years — the evidence is in the product, and every
experiment is committed for inspection."

## 2:35–2:55 — The twist: it refuses to lie

*[SHOW: Tab 5 — deployment-readiness JSON, the blocking gates.]*

"And proof five is the one no other team will show you:
**our system telling *us* no.**
We don't have IDBI's data yet. So UdyamPulse **refuses to start**
in pilot mode until real data and every safety check exists.
We built it so it cannot exaggerate.
Not to you. Not for us. **Not even to win.**"

*(pause — this is the emotional peak)*

## 2:55–3:10 — Close

*[SHOW: back to the approved card. Hold it.]*

"Millions of good businesses aren't risky.
They're just **invisible**.
UdyamPulse makes them visible.
**A credit score for those who never got one.**
It's live. Judge it yourself — it's waiting for you."

---

## Delivery notes

- The dare is the heart of the video: say "Pause right here" like you mean it,
  then actually hold a full second of silence. The silence says *nothing to hide*.
- No spoken introduction — the team name is on the deck and the repo.
- Switch tabs exactly on the word "Proof" — say it, then show it.
- Pause after "Not even to win"; slow down on the final line, then stop.
- ≈ 470 spoken words → about 3:10 at a calm pace. If trimming is needed, cut
  the liar case (1:45–2:00) first; never cut the dare or the twist.
- Say "twenty-seven lakh rupees". Say "**validated against** 4 lakh loans" —
  never "trained on" (the training split is 197,716 loans; the programme
  universe is 418,947).

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
