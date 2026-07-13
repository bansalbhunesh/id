const {
  esc, formatCurrency, titleize, statusClass, fmtCi,
  itemTitle, itemDetail, reasonText, nextActionText: nextActionTextFor,
  limitBasisBinding,
} = window.UdyamLib;

const API_BASE = window.location.protocol === "file:" ? "http://localhost:8000" : "";
const VALID_TABS = ["decision", "evidence", "model", "governance", "proof", "sources"];
const API_TIMEOUT_MS = 60000;
const state = {
  health: null,
  msmes: [],
  portfolio: null,
  governance: null,
  validation: null,
  model: null,
  benchmark: null,
  deployment: null,
  outcomeContract: null,
  submissionProof: null,
  activeId: "ntc_hero",
  activeScore: null,
  activeTab: "decision",
  lang: "en",
};

const els = {
  apiStatus: document.getElementById("apiStatus"),
  modelStatus: document.getElementById("modelStatus"),
  cohortStatus: document.getElementById("cohortStatus"),
  msme: document.getElementById("msme"),
  caseList: document.getElementById("caseList"),
  caseSummary: document.getElementById("caseSummary"),
  portfolioMetrics: document.getElementById("portfolioMetrics"),
  tabs: document.getElementById("tabs"),
  tabContent: document.getElementById("tabContent"),
  packet: document.getElementById("reviewPacket"),
  packetTitle: document.getElementById("packetTitle"),
};

const packetTitles = {
  decision: "Decision packet",
  evidence: "Evidence packet",
  model: "Model evidence",
  governance: "Governance packet",
  proof: "Judge proof",
  sources: "Source register",
};

function code(value) {
  return `<code>${esc(value)}</code>`;
}

function riskMark(label) {
  return `<span class="risk-mark">${esc(label || "Review risk")}</span>`;
}

async function api(path, { method = "GET", headers = {}, body, timeoutMs = API_TIMEOUT_MS, raw = false } = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: { Accept: "application/json", ...headers },
      body,
      signal: controller.signal,
    });
    if (raw) return response;
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new Error(`${path} timed out`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function scrollPacketIntoView() {
  // On single-column layouts the packet sits below the stage; a stage CTA
  // should bring it into view. On the two-rail desktop layout it is already
  // visible, so this is a no-op there.
  if (!window.matchMedia("(max-width: 1179px)").matches) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  els.packet.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
}

function setApiStatus(ok, label) {
  els.apiStatus.textContent = label;
  els.apiStatus.dataset.state = ok ? "live" : "offline";
  const release = state.health?.release;
  if (release) els.apiStatus.title = `v${release.version} · ${release.commit} · ${release.mode}`;
}

function readUrlState() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  return {
    caseId: params.get("case"),
    view: VALID_TABS.includes(view) ? view : null,
  };
}

function writeUrlState({ replace = false } = {}) {
  if (window.location.protocol === "file:") return;
  const url = new URL(window.location.href);
  url.searchParams.set("case", state.activeId);
  if (state.activeTab !== "decision") url.searchParams.set("view", state.activeTab);
  else url.searchParams.delete("view");
  window.history[replace ? "replaceState" : "pushState"](
    { caseId: state.activeId, view: state.activeTab },
    "",
    url,
  );
}

function errorState(title, detail) {
  return `<div class="error-state"><div>
    <strong>${esc(title)}</strong>
    <p>${esc(detail)}</p>
    <button class="quiet-action" type="button" data-retry>Retry connection</button>
  </div></div>`;
}

function setModelStatusText() {
  const runtime = state.model || state.governance?.model?.runtime || {};
  return (runtime.active_provider || "fallback").replaceAll("_", " ");
}

function holdoutMetrics() {
  return state.validation?.splits?.holdout || state.validation?.metrics || null;
}

function updateStatusLine() {
  els.modelStatus.textContent = `${setModelStatusText()} model`;
  els.cohortStatus.textContent = state.portfolio?.cohort_label || "public synthetic";
}

function miniLedger(items) {
  return `<table class="ledger-table"><tbody>${items.map(([label, value]) => `
    <tr><td>${esc(label)}</td><td class="number">${esc(value)}</td></tr>
  `).join("")}</tbody></table>`;
}

function renderPortfolioMetrics() {
  const summary = state.portfolio?.summary;
  if (!summary) {
    els.portfolioMetrics.innerHTML = `<div class="empty-state">Portfolio impact unavailable.</div>`;
    return;
  }
  const pilot = state.portfolio?.pilot_metrics;
  const items = [
    ["NTC rescues", summary.ntc_rescued, "thin-file borrowers approved with alternate data"],
    ["Credit unlocked", formatCurrency(summary.credit_unlocked), "public demo cohort"],
    ["Approval lift (target)", pilot ? `+${pilot.ntc_ntb_approval_lift_pct.value}%` : `+${summary.alternate_data_approvals - summary.traditional_approvals}`, "pilot target, not a measured benchmark"],
    ["Decision time (target)", pilot ? `${pilot.decision_time_reduction_pct.value}% saved` : `${summary.decision_time_minutes} min`, `assumed vs ${summary.manual_baseline_days} day manual baseline, not timed`],
  ];
  els.portfolioMetrics.innerHTML = items.map(([label, value, detail]) => `
    <article class="impact-item">
      <span>${esc(label)}</span>
      <strong>${esc(value)}</strong>
      <p class="fine-print">${esc(detail)}</p>
    </article>
  `).join("");
}

function renderCases() {
  els.msme.innerHTML = state.msmes.map((item) => `
    <option value="${esc(item.id)}">${esc(item.name)}</option>
  `).join("");
  els.msme.value = state.activeId;

  const cases = state.portfolio?.cases || [];
  if (!cases.length) {
    els.caseList.innerHTML = `<div class="empty-state">No borrower files are available.</div>`;
    return;
  }
  els.caseList.innerHTML = cases.map((item) => `
    <button class="case-button" type="button" data-case="${esc(item.id)}" aria-pressed="${item.id === state.activeId}">
      <strong>${esc(item.name)}</strong>
      <span>${esc(item.sector)} / ${esc(item.district)}</span>
      <span class="mono">${esc(item.grade)} grade / ${formatCurrency(item.eligible_limit)}</span>
    </button>
  `).join("");
}

function sourceByName(score, name) {
  return (score.data_sources || []).find((source) => source.source === name)?.signal || "Source signal ready";
}

function renderSourceGlance(score) {
  const sources = [
    ["AA cash flow", sourceByName(score, "Account Aggregator")],
    ["GST discipline", sourceByName(score, "GST")],
    ["UPI velocity", sourceByName(score, "UPI")],
    ["EPFO footprint", sourceByName(score, "EPFO")],
  ];
  return `<div class="source-glance">${sources.map(([label, value]) => `
    <div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>
  `).join("")}</div>`;
}

function renderCaseSummary(score) {
  if (!score) {
    els.caseSummary.innerHTML = `<div class="skeleton">Select a borrower file.</div>`;
    return;
  }
  const profile = score.profile || {};
  const fileId = state.activeId.replace(/_/g, "-");
  const traditionalClass = score.traditional.decision === "Approved" ? "approved" : "rejected";
  const alternateClass = score.alternate_data_decision.toLowerCase();
  const ntcLabel = profile.has_bureau_history ? "Bureau history present" : "New-to-Credit / New-to-Bank";
  const title = score.traditional.decision === "Rejected" && score.alternate_data_decision === "Approved"
    ? "Bureau rejection reversed."
    : score.alternate_data_decision === "Review"
      ? "Evidence moved to review."
      : score.alternate_data_decision === "Rejected"
        ? "Risk evidence confirms decline."
        : "Governed credit decision ready.";

  els.caseSummary.innerHTML = `
    <div class="stage-copy">
      <div class="stage-file">
        <span class="mono">UP-${esc(fileId)}</span>
        <span>${esc(profile.sector || "MSME")} / ${esc(profile.district || "India")}</span>
        <span>${esc(ntcLabel)}</span>
      </div>
      <h2 class="stage-title">${esc(title)}</h2>
      <p class="stage-lede">${esc(score.name)} is ${esc(score.alternate_data_decision.toLowerCase())} for ${formatCurrency(score.eligible_limit)} after consented cash-flow, GST, UPI, EPFO-style, and bureau signals are reviewed. Reasons, model evidence, fairness checks, and proof sit in the review packet alongside.</p>
      <div class="stage-actions">
        <button class="primary-action" type="button" data-open-tab="decision">Read decision packet</button>
        <button class="quiet-action" type="button" data-open-tab="model">See model evidence</button>
      </div>
    </div>
    <aside class="verdict-stage" aria-label="Decision stage">
      <div class="stamp-note">
        ${riskMark(score.risk_band)}
        <div class="stamp-score">
          <span class="stamp-letter">${esc(score.grade)}</span>
          <strong>${esc(score.score)}/100</strong>
        </div>
        <div>
          <p class="muted">Indicative limit</p>
          <div class="limit-number">${formatCurrency(score.eligible_limit)}</div>
          <p class="muted">${esc(score.limit_basis?.binding_constraint === "debt_service_capacity" ? "Sized by spare EMI capacity" : "Sized by grade policy cap")}</p>
        </div>
        <div class="decision-line">
          <div><span>Traditional bureau screen</span><strong class="decision-word ${traditionalClass}">${esc(score.traditional.decision)}</strong></div>
          <div><span>UdyamPulse alternate-data review</span><strong class="decision-word ${alternateClass}">${esc(score.alternate_data_decision)}</strong></div>
          <div><span>Runtime</span><strong class="mono">${esc(setModelStatusText())}</strong></div>
        </div>
        ${score.traditional?.reason ? `<p class="fine-print">${esc(score.traditional.reason)}</p>` : ""}
      </div>
    </aside>
    ${renderSourceGlance(score)}
  `;

  els.caseSummary.querySelectorAll("[data-open-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      setTab(button.dataset.openTab);
      scrollPacketIntoView();
    });
  });
}

function renderPillars(score) {
  return Object.entries(score.pillars || {}).map(([key, value]) => {
    const width = Math.max(0, Math.min(100, Number(value) * 5));
    return `
      <div class="meter-row">
        <div class="meter-head"><span>${esc(titleize(key))}</span><strong>${esc(value)}/20</strong></div>
        <div class="score-rule" aria-hidden="true"><span data-meter-value="${width}"></span></div>
      </div>
    `;
  }).join("");
}

function renderReasons(reasons = []) {
  return reasons.map((reason) => `
    <article class="reason-row">
      <strong>${esc(reason)}</strong>
    </article>
  `).join("") || `<div class="empty-state">No reason codes available.</div>`;
}

function langToggle() {
  return `
    <div class="seg-toggle" role="group" aria-label="Reason-code language">
      <button type="button" data-lang="en" aria-pressed="${state.lang === "en"}">English</button>
      <button type="button" data-lang="hi" aria-pressed="${state.lang === "hi"}" lang="hi">हिन्दी</button>
    </div>`;
}

function renderVernacularReasons(score) {
  const rows = score.reasons_vernacular;
  if (!Array.isArray(rows) || !rows.length) return renderReasons(score.reasons);
  return rows.map((row) => `
    <article class="reason-row" ${state.lang === "hi" ? 'lang="hi"' : ""}>
      <strong>${esc(reasonText(row, state.lang))}</strong>
    </article>
  `).join("");
}

function nextActionText(nextAction) {
  return nextActionTextFor(nextAction, state.lang);
}

function renderLimitBasis(score) {
  const basis = score.limit_basis;
  if (!basis) return "";
  const inputs = basis.policy_inputs || {};
  const binding = limitBasisBinding(basis);
  return `
    <section class="detail-section">
      <h3 class="section-title">How the limit was sized</h3>
      <p class="muted">EMI-capacity annuity at documented policy inputs; the grade multiple only caps it. Not a score-times-constant number.</p>
      ${miniLedger([
        ["Affordable new EMI", formatCurrency(basis.affordable_new_emi)],
        ["Existing monthly debt service (est.)", formatCurrency(basis.estimated_existing_monthly_service)],
        ["Debt-service capacity limit", formatCurrency(basis.debt_service_capacity_limit)],
        ["Grade policy cap", formatCurrency(basis.grade_policy_cap)],
        ["Concentration multiplier", basis.concentration_multiplier ?? "1.0"],
        ["Indicative limit", formatCurrency(basis.indicative_limit ?? score.eligible_limit)],
        ["Policy rate / tenor", `${((inputs.annual_rate ?? 0) * 100).toFixed(1)}% / ${inputs.tenor_months ?? "-"} months`],
        ["EMI share of inflow", `${((inputs.emi_capacity_share_of_inflow ?? 0) * 100).toFixed(0)}%`],
      ])}
      <p class="muted"><strong>${esc(binding)}</strong></p>
      ${basis.note ? `<p class="truth-note">${esc(basis.note)}</p>` : ""}
    </section>`;
}

function renderJournal(items = [], emptyLabel = "No rows available.") {
  return items.map((item) => {
    const stateText = item.status || item.decision || item.method || item.endpoint || item.category || "Review";
    return `
      <article class="journal-row">
        <span class="journal-state ${statusClass(stateText)}">${esc(stateText)}</span>
        <strong>${esc(itemTitle(item))}</strong>
        <p class="muted">${esc(itemDetail(item))}</p>
      </article>
    `;
  }).join("") || `<div class="empty-state">${esc(emptyLabel)}</div>`;
}

function renderFairnessRows(rows = []) {
  return `<table class="ledger-table"><tbody>${rows.map((row) => `
    <tr><td>${esc(row.group)} (${esc(row.count)})</td><td class="number">${esc(row.alternate_approval_rate)}%</td></tr>
  `).join("") || `<tr><td>No rows</td><td class="number">-</td></tr>`}</tbody></table>`;
}

function renderDecisionTab(score) {
  const improvement = score.improvement_plan;
  const improvementText = improvement
    ? `${improvement.action} Potential grade: ${improvement.potential_grade}; limit uplift: ${formatCurrency(improvement.limit_increase)}.`
    : "Maintain GST filing continuity, low bounce rate, and broad digital counterparties to preserve the current fast-track grade.";
  const nextAction = score.next_best_action;
  return `
    <section class="detail-section">
      <h3 class="section-title">Five-pillar health ledger</h3>
      <div class="meter-list">${renderPillars(score)}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">EWS-style monitoring signals</h3>
      <p class="muted">Same five pillars, framed in the monitoring categories a credit officer tracks under bank early-warning practice -- our own descriptive labels, not regulatory text.</p>
      <div class="journal-list">${renderJournal(score.ews_signals, "No monitoring signals available.")}</div>
    </section>
    <section class="detail-section">
      <div class="section-head">
        <h3 class="section-title">Reason-code journal</h3>
        ${langToggle()}
      </div>
      <p class="muted">Borrower-facing reasons ship in English and Hindi from the same API response -- this is an inclusion track.</p>
      <div class="reason-list">${renderVernacularReasons(score)}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Underwriter next step</h3>
      <article class="reason-row" ${state.lang === "hi" ? 'lang="hi"' : ""}>
        <span class="journal-state ${statusClass(nextAction.urgency)}">${esc(nextAction.urgency)} urgency</span>
        <strong>${esc(nextActionText(nextAction))}</strong>
      </article>
    </section>
    ${renderLimitBasis(score)}
    <section class="detail-section">
      <h3 class="section-title">Underwriter memo</h3>
      <p>${esc(score.memo)}</p>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Borrower improvement note</h3>
      <p>${esc(improvementText)}</p>
    </section>
  `;
}

function renderEvidenceTab(score) {
  const pd = score.pd_estimate;
  const pdLine = typeof pd === "number"
    ? `<p class="muted">Proxy PD <strong>${(pd * 100).toFixed(1)}%</strong> via <code>${esc(score.ml?.provider)}</code>; review threshold ${((score.ml?.pd_review_threshold ?? 0) * 100).toFixed(1)}%.</p>
       <p class="truth-note">Public consumer-credit proxy, not IDBI/MSME calibration. It may route a scorecard/model disagreement to human review, but it cannot auto-decline.</p>`
    : "";
  return `
    <section class="detail-section">
      <h3 class="section-title">Model attribution</h3>
      <p class="muted">Baseline score ${esc(score.ml?.baseline_score)} with exact Shapley-equivalent contributions from the active PD model.</p>
      ${pdLine}
      <div class="reason-list spaced">${renderReasons(score.ml?.top_reasons || [])}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Decision path</h3>
      <div class="journal-list">${renderJournal(score.decision_path, "No decision path rows available.")}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Policy guardrails</h3>
      ${miniLedger([
        ["Policy version", score.policy?.version || "-"],
        ["Decision route", score.policy?.route || "-"],
        ["Policy decision", score.policy?.decision || score.alternate_data_decision],
      ])}
      <div class="journal-list">${renderJournal(score.policy_guardrails, "No guardrail rows available.")}</div>
    </section>
  `;
}

function renderBenchmarkSplits(champion) {
  const splits = champion?.splits || {};
  const cis = champion?.confidence_intervals || {};
  const dataset = champion?.dataset || {};
  const rows = [
    ["holdout", "Holdout (FY2010-16)", cis.holdout_auc],
    ["oot", "True out-of-time (FY2017-19)", cis.oot_auc],
    ["stress", "Recession stress (FY2005-07)", null],
  ];
  return `<table class="ledger-table"><tbody>
    <tr><td><strong>Split</strong></td><td class="number"><strong>AUC</strong></td><td class="number"><strong>KS</strong></td><td class="number"><strong>n</strong></td></tr>
    ${rows.map(([key, label, ci]) => {
      const split = splits[key];
      if (!split) return "";
      const ciText = fmtCi(ci).trim();
      return `<tr>
        <td>${esc(label)}</td>
        <td class="number">${esc(split.auc)}${ciText ? `<span class="ci">${esc(ciText)}</span>` : ""}</td>
        <td class="number">${esc(split.ks ?? "-")}</td>
        <td class="number">${esc((split.n ?? dataset[`${key}_rows`] ?? "-").toLocaleString?.("en-IN") ?? split.n)}</td>
      </tr>`;
    }).join("")}
  </tbody></table>`;
}

function renderBaselineComparison(champion) {
  const baselines = champion?.baseline_comparison_oot;
  if (!baselines) return "";
  const rows = Object.entries(baselines).map(([name, entry]) => {
    const z = entry?.delong_vs_v2?.z ?? entry?.delong?.z;
    return `<tr>
      <td>${esc(titleize(name))}</td>
      <td class="number">${esc(entry.auc ?? "-")}</td>
      <td class="number">${z != null ? `z = ${esc(z)}` : "-"}</td>
    </tr>`;
  }).join("");
  return `<table class="ledger-table"><tbody>
    <tr><td><strong>Baseline (identical protocol)</strong></td><td class="number"><strong>OOT AUC</strong></td><td class="number"><strong>DeLong vs v2</strong></td></tr>
    ${rows}
  </tbody></table>`;
}

function renderFairnessGroups(evaluation) {
  const dims = evaluation?.fairness?.dimensions;
  if (!dims) return `<div class="empty-state">No fairness slices in the evaluation artifact.</div>`;
  return Object.entries(dims).map(([dim, detail]) => `
    <h3 class="section-title spaced">${esc(titleize(dim))} (max AUC gap ${esc(detail.max_auc_gap ?? "-")})</h3>
    <table class="ledger-table"><tbody>
      <tr><td><strong>Group</strong></td><td class="number"><strong>AUC</strong></td><td class="number"><strong>Brier</strong></td><td class="number"><strong>FPR</strong></td><td class="number"><strong>n</strong></td></tr>
      ${(detail.groups || []).map((group) => `
        <tr>
          <td>${esc(titleize(group.group))}</td>
          <td class="number">${esc(group.auc)}</td>
          <td class="number">${esc(group.brier_score)}</td>
          <td class="number">${esc(group.false_positive_rate)}</td>
          <td class="number">${esc(group.n)}</td>
        </tr>`).join("")}
    </tbody></table>
  `).join("");
}

function renderModelTab() {
  const bench = state.benchmark;
  const evaluation = state.validation;
  const champion = bench?.champion;
  const integrity = bench?.artifact_integrity;
  const candidates = evaluation?.model_selection?.candidates || {};
  const cis = evaluation?.holdout_confidence_intervals || {};
  const threshold = evaluation?.policy_threshold;
  const baselineV1 = bench?.baseline_v1;

  const benchSection = champion ? `
    <section class="detail-section">
      <h3 class="section-title">Real-outcome benchmark · ${esc(bench.champion_version || "sba_sme_pd_v2")}</h3>
      <p class="muted">${esc(champion.dataset?.name || "SBA 7(a) FOIA loan-level records")} at natural base rates. ${esc(champion.dataset?.protocol || "")}</p>
      ${renderBenchmarkSplits(champion)}
      <h3 class="section-title spaced">DeLong-tested baselines</h3>
      ${renderBaselineComparison(champion)}
      ${champion.selective_monotonicity_rationale ? `<p class="muted">${esc(champion.selective_monotonicity_rationale)}</p>` : ""}
      ${integrity ? `<p class="muted">Artifact integrity: <strong>${esc(integrity.status)}</strong> -- served model hashes match the committed evaluation.</p>` : ""}
      <p class="truth-note">Real charge-off outcomes on a real time axis -- still a US proxy domain, complementary to the conduct pillars, and explicitly not an IDBI production calibration.</p>
    </section>` : `
    <section class="detail-section">
      <h3 class="section-title">Real-outcome benchmark</h3>
      <div class="empty-state">Benchmark evidence is not loaded. <code>GET /model/sme-benchmark</code> serves it when available.</div>
    </section>`;

  const v1Section = baselineV1?.holdout ? `
    <section class="detail-section">
      <h3 class="section-title">v1 case-sample baseline (kept for like-for-like comparison)</h3>
      ${miniLedger([
        ["Holdout AUC", baselineV1.holdout.auc],
        ["Holdout KS", baselineV1.holdout.ks],
        ["PR-AUC", baselineV1.holdout.pr_auc],
      ])}
    </section>` : "";

  const proxySection = evaluation ? `
    <section class="detail-section">
      <h3 class="section-title">Consumer-proxy conduct model (bootstrap 95% intervals)</h3>
      ${miniLedger([
        ["ROC-AUC", `${holdoutMetrics()?.auc ?? "-"}${fmtCi(cis.auc)}`],
        ["KS", `${holdoutMetrics()?.ks ?? "-"}${fmtCi(cis.ks)}`],
        ["PR-AUC", `${holdoutMetrics()?.pr_auc ?? "-"}${fmtCi(cis.pr_auc)}`],
        ["Brier", `${holdoutMetrics()?.brier_score ?? "-"}${fmtCi(cis.brier_score)}`],
        ["Calibration error (ECE)", holdoutMetrics()?.expected_calibration_error ?? "-"],
        ["Untouched holdout rows", holdoutMetrics()?.n?.toLocaleString?.("en-IN") ?? "-"],
      ])}
      ${threshold ? `<p class="muted">Review threshold ${esc(threshold.pd_review_threshold)} selected on the ${esc(threshold.selected_on)}: ${esc(threshold.objective)}</p>` : ""}
      <h3 class="section-title spaced">Champion vs challenger (same splits)</h3>
      <table class="ledger-table"><tbody>
        <tr><td><strong>Candidate</strong></td><td class="number"><strong>Holdout AUC</strong></td><td class="number"><strong>KS</strong></td></tr>
        ${Object.entries(candidates).map(([name, cand]) => `
          <tr><td>${esc(name)}</td><td class="number">${esc(cand.holdout?.auc ?? "-")}</td><td class="number">${esc(cand.holdout?.ks ?? "-")}</td></tr>
        `).join("")}
      </tbody></table>
      <h3 class="section-title spaced">Outcome-linked fairness slices (untouched holdout)</h3>
      <p class="muted">${esc(evaluation.fairness?.note || "Protected attributes are monitoring-only, never model inputs.")}</p>
      ${renderFairnessGroups(evaluation)}
    </section>` : `
    <section class="detail-section">
      <h3 class="section-title">Consumer-proxy conduct model</h3>
      <div class="empty-state">Evaluation artifact is not loaded.</div>
    </section>`;

  return benchSection + v1Section + proxySection;
}

function renderGovernanceTab() {
  const governance = state.governance;
  const validation = holdoutMetrics();
  const validationDesign = state.validation?.validation_design;
  const pilot = governance?.pilot_metrics || state.portfolio?.pilot_metrics;
  const fairness = governance?.fairness || {};
  const runtime = governance?.model?.runtime || {};
  const deployment = state.deployment || governance?.deployment || {};
  if (!governance) return `<div class="empty-state">Governance data is not loaded yet.</div>`;

  return `
    <section class="detail-section">
      <h3 class="section-title">Model and audit</h3>
      ${miniLedger([
        ["Audit events", governance.audit.events_recorded],
        ["Model version", governance.model.version],
        ["Active model", runtime.active_provider || "linear"],
      ])}
    </section>
    <section class="detail-section">
      <h3 class="section-title">Public proxy holdout</h3>
      ${validation ? miniLedger([
        ["AUC", validation.auc],
        ["Gini", validation.gini],
        ["KS", validation.ks],
        ["PR-AUC", validation.pr_auc],
        ["Brier", validation.brier_score],
        ["Calibration error", validation.expected_calibration_error],
        ["PSI stability", state.validation?.drift?.psi_development_vs_holdout ?? "-"],
      ]) : `<div class="empty-state">No validation report.</div>`}
      ${validationDesign ? `<p class="truth-note">${esc(validationDesign)}</p>` : ""}
    </section>
    <section class="detail-section">
      <h3 class="section-title">Pilot promotion gate</h3>
      ${miniLedger([
        ["Runtime mode", titleize(deployment.mode)],
        ["Current status", titleize(deployment.status)],
        ["Pilot ready", deployment.pilot_ready ? "Yes" : "No - blocked safely"],
        ["Blocking gates", deployment.blockers?.length ?? "-"],
      ])}
      <p class="truth-note">The public demo stays available. Pilot and production startup fail closed until every bank-data, OOT, identity, HMAC, and durable-audit gate passes.</p>
      <div class="journal-list">${renderJournal(deployment.gates, "No deployment gates available.")}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Pilot KPI targets</h3>
      ${pilot ? miniLedger([
        ["NTC/NTB lift", `+${pilot.ntc_ntb_approval_lift_pct.value}%`],
        ["Decision time", `${pilot.decision_time_reduction_pct.value}% saved`],
        ["Approved sectors", pilot.portfolio_diversification.approved_sector_count],
        ["Approved districts", pilot.portfolio_diversification.approved_district_count],
      ]) : `<div class="empty-state">No pilot KPI rows.</div>`}
    </section>
    <section class="detail-section">
      <h3 class="section-title">Live controls</h3>
      <div class="journal-list">${renderJournal(governance.controls, "No control rows available.")}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Fairness gap checks</h3>
      <p class="muted">${esc(fairness.note || "Public cohort check only; production pilot requires outcome-linked monitoring.")}</p>
      <h3 class="section-title spaced">Bureau history</h3>
      ${renderFairnessRows(fairness.by_bureau_history)}
      <h3 class="section-title spaced">Sector</h3>
      ${renderFairnessRows(fairness.by_sector)}
      <h3 class="section-title spaced">Geography</h3>
      ${renderFairnessRows(fairness.by_geography)}
    </section>
  `;
}

function evidenceCodes(items = []) {
  return items.map((item) => code(item)).join(" ");
}

function renderProofTab() {
  const proof = state.submissionProof;
  if (!proof) return `<div class="empty-state">Submission proof is not loaded yet.</div>`;
  const hero = proof.hero_reversal || {};
  const truth = proof.truth_boundary || {};
  const rubric = proof.rubric_scorecard || [];
  const gaps = proof.competitor_gap_map || [];
  const runbook = proof.judge_runbook || [];
  const capabilities = proof.backend_capabilities || [];
  const apis = proof.api_catalog || [];

  return `
    <section class="detail-section">
      <h3 class="section-title">Judge proof</h3>
      ${miniLedger([
        ["Proof API", proof.status || "Live"],
        ["Release", state.health?.release ? `v${state.health.release.version} · ${state.health.release.commit}` : "-"],
        ["Hero case", hero.case || "-"],
        ["Traditional", hero.traditional_decision || "-"],
        ["UdyamPulse", hero.alternate_data_decision || "-"],
        ["Grade", `${hero.grade || "-"} / ${hero.score ?? "-"} score`],
      ])}
    </section>
    <section class="detail-section">
      <h3 class="section-title">Truth boundary</h3>
      ${miniLedger([
        ["Public data", truth.public_data ? "Synthetic demo cohort" : "-"],
        ["Private IDBI data", truth.private_idbi_data === "not_claimed" ? "Not claimed" : titleize(truth.private_idbi_data)],
        ["Sandbox access", truth.sandbox_access ? "Post-shortlisting" : "-"],
        ["Production model", truth.production_model ? "Public proxy blocked from pilot" : "-"],
      ])}
    </section>
    <section class="detail-section">
      <h3 class="section-title">Rubric scorecard</h3>
      <div class="journal-list">
        ${rubric.map((item) => `
          <article class="journal-row">
            <span class="journal-state">${esc(item.criterion || "Rubric")}</span>
            <strong>${esc(item.proof)}</strong>
            <p class="muted">${evidenceCodes(item.evidence)}</p>
          </article>
        `).join("")}
      </div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Competitor gap map</h3>
      <div class="journal-list">${renderJournal(gaps, "No competitor gap rows.")}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Judge runbook</h3>
      <div class="journal-list">${renderJournal(runbook, "No runbook rows.")}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Backend capability and API catalog</h3>
      <div class="journal-list">${renderJournal(capabilities, "No capability rows.")}</div>
      <div class="journal-list spaced">${apis.map((item) => `
        <article class="journal-row">
          <span class="journal-state">${esc(item.method)} ${esc(item.path)}</span>
          <strong>${esc(item.layer)}</strong>
          <p class="muted">${esc(item.proves)}</p>
        </article>
      `).join("")}</div>
    </section>
  `;
}

function renderSourcesTab(score) {
  const contract = state.outcomeContract || {};
  const split = contract.split_policy || {};
  return `
    <section class="detail-section">
      <h3 class="section-title">Data source register</h3>
      <div class="journal-list">${renderJournal(score.data_sources, "No source rows available.")}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Sandbox readiness</h3>
      <div class="journal-list">
        <article class="journal-row">
          <span class="journal-state">Current cohort</span>
          <strong>Public synthetic data</strong>
          <p class="muted">The repository does not include private IDBI sandbox credentials, customer data, or repayment labels.</p>
        </article>
        <article class="journal-row">
          <span class="journal-state">Feed contract</span>
          <strong>AA/GST/UPI/EPFO payload path</strong>
          <p class="muted">${code("POST /sandbox/score")} accepts sandbox-style payloads and maps them into this same score packet.</p>
        </article>
        <article class="journal-row">
          <span class="journal-state">${esc(contract.contract_version || "Outcome contract")}</span>
          <strong>Dated 12-month labels - ${esc(split.method || "chronological OOT split")}</strong>
          <p class="muted">No random shuffle: ${esc(split.random_shuffle === false ? "enforced" : "pending")}. ${code("GET /sandbox/outcome-contract")} defines the schema; ${code("POST /sandbox/pilot-readiness")} checks maturity, temporal splits, source coverage, NTC volume, and fairness support without persisting records.</p>
        </article>
        <article class="journal-row">
          <span class="journal-state">Stage 2 boundary</span>
          <strong>IDBI-calibrated retraining and Bedrock</strong>
          <p class="muted">Retrain the shipped XGBoost/logistic pipeline on dated IDBI MSME outcomes, validate a true out-of-time window, and enable Bedrock memos only with approved credentials.</p>
        </article>
      </div>
    </section>
    ${renderConsole()}
  `;
}

const CONSOLE_EXAMPLE = {
  consent: {
    consent_id: "consent-demo-001",
    purpose: "msme_underwriting",
    scope: ["account_aggregator", "gst", "upi", "epfo", "bureau"],
    granted_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    expires_at: new Date(Date.now() + 90 * 86400000).toISOString(),
  },
  profile: { name: "Asha Precision Works", sector: "Manufacturing", district: "Pune", gender: "Female", vintage_months: 42 },
  account_aggregator: { monthly_inflows: [480000, 510000, 535000, 560000, 590000, 625000], cheque_bounces: 1, cheque_presentations: 42, outstanding_debt: 180000 },
  gst: { filing_streak_months: 18, trailing_6m_turnover: [460000, 480000, 505000, 530000, 570000, 615000] },
  upi: { monthly_transaction_count: 310, unique_counterparties: 54 },
  epfo: { employees: 14 },
  bureau: { has_bureau_history: false },
};

function renderConsole() {
  return `
    <section class="detail-section">
      <h3 class="section-title">Live underwriter console</h3>
      <p class="muted">Send a real sandbox-style payload to ${code("POST /sandbox/score")} on this running backend. The demo-scoped underwriter key is documented in the repository (docs/DEMO_SCRIPT.md); real deployments override it. Errors render as errors -- nothing here is mocked.</p>
      <form class="console-form" data-console novalidate>
        <label>Underwriter bearer key
          <input type="password" name="key" autocomplete="off" spellcheck="false" placeholder="udyampulse-demo-underwriter-key" />
        </label>
        <label>Sandbox payload (editable JSON)
          <textarea name="payload" rows="12" spellcheck="false">${esc(JSON.stringify(CONSOLE_EXAMPLE, null, 2))}</textarea>
        </label>
        <button class="primary-action" type="submit">Score this payload</button>
      </form>
      <div class="console-result" data-console-result aria-live="polite"></div>
    </section>`;
}

function consoleResultCard(packet) {
  const alternateClass = (packet.alternate_data_decision || "").toLowerCase();
  return `
    <div class="stamp-note console-stamp">
      ${riskMark(packet.risk_band)}
      <div class="stamp-score">
        <span class="stamp-letter">${esc(packet.grade)}</span>
        <strong>${esc(packet.score)}/100</strong>
      </div>
      <div class="decision-line">
        <div><span>Decision</span><strong class="decision-word ${esc(alternateClass)}">${esc(packet.alternate_data_decision)}</strong></div>
        <div><span>Indicative limit</span><strong>${formatCurrency(packet.eligible_limit)}</strong></div>
      </div>
      <div class="reason-list">${renderReasons((packet.reasons || []).slice(0, 4))}</div>
      <details><summary>Full response JSON</summary><pre class="console-json">${esc(JSON.stringify(packet, null, 2))}</pre></details>
    </div>`;
}

async function submitConsole(form) {
  const result = form.parentElement.querySelector("[data-console-result]");
  const button = form.querySelector("button[type='submit']");
  const key = form.elements.key.value.trim();
  if (!key) {
    result.innerHTML = `<div class="error-state"><div><strong>Bearer key required</strong><p>Paste the demo underwriter key documented in docs/DEMO_SCRIPT.md. The endpoint returns 401 without it -- by design.</p></div></div>`;
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(form.elements.payload.value);
  } catch (error) {
    result.innerHTML = `<div class="error-state"><div><strong>Payload is not valid JSON</strong><p>${esc(error.message)}</p></div></div>`;
    return;
  }
  button.disabled = true;
  button.textContent = "Scoring...";
  result.innerHTML = `<div class="skeleton">Scoring the payload against the live policy engine...</div>`;
  try {
    const response = await api("/sandbox/score", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify(parsed),
      raw: true,
    });
    const bodyJson = await response.json().catch(() => ({}));
    if (response.status === 401 || response.status === 403) {
      result.innerHTML = `<div class="error-state"><div><strong>${response.status} -- not authorised</strong><p>${esc(bodyJson.detail || "The backend rejected the key.")}</p></div></div>`;
    } else if (response.status === 422) {
      const details = Array.isArray(bodyJson.detail)
        ? bodyJson.detail.map((item) => `${(item.loc || []).join(".")}: ${item.msg}`).slice(0, 6)
        : [String(bodyJson.detail || "Validation failed")];
      result.innerHTML = `<div class="error-state"><div><strong>422 -- payload rejected by validation</strong>${details.map((d) => `<p>${esc(d)}</p>`).join("")}</div></div>`;
    } else if (!response.ok) {
      result.innerHTML = `<div class="error-state"><div><strong>${response.status} -- request failed</strong><p>${esc(bodyJson.detail || "Unexpected backend response.")}</p></div></div>`;
    } else {
      result.innerHTML = consoleResultCard(bodyJson);
    }
  } catch (error) {
    result.innerHTML = `<div class="error-state"><div><strong>Request failed</strong><p>${esc(error.message)}</p></div></div>`;
  } finally {
    button.disabled = false;
    button.textContent = "Score this payload";
  }
}

function applyMeterWidths(container) {
  // The page's CSP has no style-src 'unsafe-inline', so a literal
  // style="--value: n%" attribute is silently dropped by the browser.
  // Setting the custom property through the CSSOM instead isn't subject
  // to that restriction.
  container.querySelectorAll("[data-meter-value]").forEach((el) => {
    el.style.setProperty("--value", `${el.dataset.meterValue}%`);
  });
}

function renderTabContent() {
  const score = state.activeScore;
  if (!score) {
    els.tabContent.innerHTML = `<div class="skeleton">Select a borrower file to render the review packet.</div>`;
    return;
  }
  const views = {
    decision: () => renderDecisionTab(score),
    evidence: () => renderEvidenceTab(score),
    model: () => renderModelTab(),
    governance: () => renderGovernanceTab(),
    proof: () => renderProofTab(),
    sources: () => renderSourcesTab(score),
  };
  els.packetTitle.textContent = packetTitles[state.activeTab] || "Review packet";
  els.tabContent.setAttribute("aria-labelledby", `tab-${state.activeTab}`);
  els.tabContent.innerHTML = views[state.activeTab]?.() || views.decision();
  applyMeterWidths(els.tabContent);
  els.tabContent.scrollTop = 0;
}

function setTab(tab, { updateHistory = true } = {}) {
  if (!VALID_TABS.includes(tab)) tab = "decision";
  state.activeTab = tab;
  els.tabs.querySelectorAll("[data-tab]").forEach((button) => {
    const selected = button.dataset.tab === tab;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  renderTabContent();
  if (updateHistory) writeUrlState();
}

function handleTabKeydown(event) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const tabs = [...els.tabs.querySelectorAll("[role='tab']")];
  const current = tabs.indexOf(document.activeElement);
  if (current < 0) return;
  event.preventDefault();
  let next = current;
  if (event.key === "Home") next = 0;
  if (event.key === "End") next = tabs.length - 1;
  if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
  if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
  tabs[next].focus();
  setTab(tabs[next].dataset.tab);
}

async function refreshGovernance() {
  state.governance = await api("/governance");
  state.deployment = state.governance?.deployment || state.deployment;
}

let activeLoadToken = 0;

async function loadCase(id, { updateHistory = true } = {}) {
  if (!state.msmes.some((item) => item.id === id)) id = state.msmes[0]?.id || "ntc_hero";
  // Sequence guard: if the underwriter switches borrowers quickly, an earlier
  // in-flight request can resolve after a later one. Stamp each load and only
  // render if this is still the newest request, so case A's decision can never
  // be painted under case B's identity.
  const loadToken = ++activeLoadToken;
  state.activeId = id;
  els.msme.value = id;
  renderCases();
  els.caseSummary.innerHTML = `<div class="skeleton">Scoring selected MSME...</div>`;
  els.tabContent.innerHTML = `<div class="skeleton">Preparing review packet...</div>`;
  try {
    const score = await api(`/msmes/${encodeURIComponent(id)}/score`);
    if (loadToken !== activeLoadToken) return; // superseded by a newer selection
    state.activeScore = score;
    try {
      await refreshGovernance();
    } catch (_error) {
      state.governance = state.governance || null;
    }
    if (loadToken !== activeLoadToken) return; // superseded while awaiting governance
    renderCaseSummary(score);
    renderTabContent();
    setApiStatus(true, "Live API");
    updateStatusLine();
    if (updateHistory) writeUrlState({ replace: true });
  } catch (error) {
    if (loadToken !== activeLoadToken) return; // a newer load owns the screen now
    setApiStatus(false, "Offline");
    els.caseSummary.innerHTML = errorState("Borrower decision unavailable", error.message);
    els.tabContent.innerHTML = `<div class="empty-state">Review evidence is unavailable while the API is offline.</div>`;
  }
}

function bindEvents() {
  els.msme.addEventListener("change", (event) => loadCase(event.target.value));
  els.caseList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-case]");
    if (button) loadCase(button.dataset.case);
  });
  els.tabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-tab]");
    if (button) setTab(button.dataset.tab);
  });
  els.tabs.addEventListener("keydown", handleTabKeydown);
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-retry]")) window.location.reload();
    const langButton = event.target.closest("[data-lang]");
    if (langButton && langButton.dataset.lang !== state.lang) {
      state.lang = langButton.dataset.lang;
      renderTabContent();
    }
  });
  els.tabContent.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-console]");
    if (form) {
      event.preventDefault();
      submitConsole(form);
    }
  });
  window.addEventListener("popstate", async () => {
    const urlState = readUrlState();
    const caseId = state.msmes.some((item) => item.id === urlState.caseId)
      ? urlState.caseId
      : state.msmes[0]?.id;
    if (caseId && caseId !== state.activeId) await loadCase(caseId, { updateHistory: false });
    setTab(urlState.view || "decision", { updateHistory: false });
  });
}

function settledValue(result) {
  return result.status === "fulfilled" ? result.value : null;
}

async function init() {
  bindEvents();
  try {
    const [health, msmes, portfolio] = await Promise.all([
      api("/health"),
      api("/msmes"),
      api("/portfolio"),
    ]);
    const optional = await Promise.allSettled([
      api("/governance"),
      api("/model/evaluation"),
      api("/model/status"),
      api("/deployment/readiness"),
      api("/sandbox/outcome-contract"),
      api("/submission/proof"),
      api("/model/sme-benchmark"),
    ]);
    const [governance, validation, model, deployment, outcomeContract, submissionProof, benchmark] = optional.map(settledValue);

    state.health = health;
    state.msmes = msmes;
    state.portfolio = portfolio;
    state.governance = governance;
    state.validation = validation;
    state.model = model;
    state.benchmark = benchmark;
    state.deployment = deployment || governance?.deployment || null;
    state.outcomeContract = outcomeContract;
    state.submissionProof = submissionProof;

    const urlState = readUrlState();
    state.activeId = state.msmes.some((item) => item.id === urlState.caseId)
      ? urlState.caseId
      : state.msmes[0]?.id || "ntc_hero";
    state.activeTab = urlState.view || "decision";

    setApiStatus(health.status === "ok", health.status === "ok" ? "Live API" : "Check API");
    updateStatusLine();
    const unavailable = optional.filter((result) => result.status === "rejected").length;
    if (unavailable) els.cohortStatus.title = `${unavailable} optional evidence feed(s) unavailable`;
    renderPortfolioMetrics();
    renderCases();
    await loadCase(state.activeId, { updateHistory: false });
    setTab(urlState.view || "decision", { updateHistory: false });
  } catch (error) {
    setApiStatus(false, "Offline");
    els.caseSummary.innerHTML = errorState("Startup check failed", error.message);
    els.tabContent.innerHTML = `<div class="empty-state">The review shell loaded, but API evidence could not be fetched.</div>`;
  }
}

init();
