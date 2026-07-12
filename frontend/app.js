const API_BASE = window.location.protocol === "file:" ? "http://localhost:8000" : "";
const VALID_TABS = ["decision", "evidence", "governance", "proof", "sources"];
const API_TIMEOUT_MS = 60000;
const state = {
  health: null,
  msmes: [],
  portfolio: null,
  governance: null,
  validation: null,
  model: null,
  deployment: null,
  outcomeContract: null,
  submissionProof: null,
  activeId: "ntc_hero",
  activeScore: null,
  activeTab: "decision",
  drawerOpen: false,
  lastFocus: null,
};

const els = {
  apiStatus: document.getElementById("apiStatus"),
  modelStatus: document.getElementById("modelStatus"),
  cohortStatus: document.getElementById("cohortStatus"),
  msme: document.getElementById("msme"),
  caseList: document.getElementById("caseList"),
  caseSummary: document.getElementById("caseSummary"),
  decisionStamp: document.getElementById("decisionStamp"),
  portfolioMetrics: document.getElementById("portfolioMetrics"),
  tabs: document.getElementById("tabs"),
  tabContent: document.getElementById("tabContent"),
  drawer: document.getElementById("reviewDrawer"),
  drawerTitle: document.getElementById("drawerTitle"),
  drawerToggle: document.getElementById("drawerToggle"),
  drawerClose: document.getElementById("drawerClose"),
  drawerScrim: document.getElementById("drawerScrim"),
  inertWhenDrawer: [...document.querySelectorAll("[data-inert-when-drawer]")],
};

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const drawerTitles = {
  decision: "Decision packet",
  evidence: "Evidence packet",
  governance: "Governance packet",
  proof: "Judge proof",
  sources: "Source register",
};

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatCurrency(value) {
  return currency.format(Number(value || 0));
}

function titleize(value) {
  return String(value ?? "-")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function code(value) {
  return `<code>${esc(value)}</code>`;
}

function riskMark(label) {
  return `<span class="risk-mark">${esc(label || "Review risk")}</span>`;
}

function statusClass(value) {
  const text = String(value || "").toLowerCase();
  if (/(reject|decline|missing|fail|offline|high|thin)/.test(text)) return "entry-red";
  if (/(approved|pass|live|connected|ready|low|stable)/.test(text)) return "approved";
  return "";
}

async function api(path, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new Error(`${path} timed out`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function setDrawerOpen(open, restoreFocus = true) {
  if (open && !state.drawerOpen && !els.drawer.contains(document.activeElement)) {
    state.lastFocus = document.activeElement;
  }
  state.drawerOpen = open;
  document.body.classList.toggle("drawer-open", open);
  els.drawer.setAttribute("aria-hidden", String(!open));
  els.drawer.inert = !open;
  els.inertWhenDrawer.forEach((element) => { element.inert = open; });
  if (open) {
    window.requestAnimationFrame(() => els.drawerTitle.focus({ preventScroll: true }));
  } else if (restoreFocus && state.lastFocus instanceof HTMLElement) {
    state.lastFocus.focus({ preventScroll: true });
  }
}

function focusableInDrawer() {
  return [...els.drawer.querySelectorAll("button:not([disabled]), a[href], select:not([disabled]), [tabindex]:not([tabindex='-1'])")]
    .filter((element) => !element.inert && element.getClientRects().length > 0);
}

function trapDrawerFocus(event) {
  if (!state.drawerOpen || event.key !== "Tab") return;
  const focusable = focusableInDrawer();
  if (!focusable.length) {
    event.preventDefault();
    els.drawerTitle.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!focusable.includes(document.activeElement)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function setApiStatus(ok, label) {
  els.apiStatus.textContent = label;
  els.apiStatus.dataset.state = ok ? "live" : "offline";
}

function readUrlState() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  return {
    caseId: params.get("case"),
    view: VALID_TABS.includes(view) ? view : null,
  };
}

function writeUrlState({ replace = false, includeView = state.drawerOpen } = {}) {
  if (window.location.protocol === "file:") return;
  const url = new URL(window.location.href);
  url.searchParams.set("case", state.activeId);
  if (includeView) url.searchParams.set("view", state.activeTab);
  else url.searchParams.delete("view");
  window.history[replace ? "replaceState" : "pushState"](
    { caseId: state.activeId, view: includeView ? state.activeTab : null },
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
      <p class="stage-lede">${esc(score.name)} is ${esc(score.alternate_data_decision.toLowerCase())} for ${formatCurrency(score.eligible_limit)} after consented cash-flow, GST, UPI, EPFO-style, and bureau signals are reviewed. Detailed reasons, fairness checks, proof, and sandbox boundaries live in the sliding review packet.</p>
      <div class="stage-actions">
        <button class="primary-action" type="button" data-open-tab="decision">Open decision packet</button>
        <button class="quiet-action" type="button" data-open-tab="sources">View source map</button>
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
      </div>
    </aside>
    ${renderSourceGlance(score)}
  `;

  els.caseSummary.querySelectorAll("[data-open-tab]").forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.openTab, true));
  });
}

function renderDecisionStamp(score) {
  const validation = holdoutMetrics();
  const governance = state.governance;
  if (!score) {
    els.decisionStamp.innerHTML = `<div class="skeleton">Decision summary unavailable.</div>`;
    return;
  }
  els.decisionStamp.innerHTML = `
    <span class="stamp-letter">${esc(score.grade)}</span>
    <div class="stamp-ledger">
      <div><span>Score</span><strong>${esc(score.score)}/100</strong></div>
      <div><span>Risk</span><strong>${esc(score.risk_band)}</strong></div>
      <div><span>Limit</span><strong>${formatCurrency(score.eligible_limit)}</strong></div>
      <div><span>Model</span><strong>${esc(setModelStatusText())}</strong></div>
      <div><span>Audit</span><strong>${esc(governance?.audit?.events_recorded ?? "-")} events</strong></div>
      <div><span>Holdout AUC</span><strong>${esc(validation?.auc ?? "-")}</strong></div>
    </div>
  `;
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

function itemTitle(item) {
  return item.control || item.code || item.stage || item.source || item.layer || item.step || item.title || item.criterion || item.common_pattern || "Review item";
}

function itemDetail(item) {
  return item.detail || item.evidence || item.signal || item.proves || item.expected || item.implemented || item.udyampulse_advantage || item.proof || "";
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
      <h3 class="section-title">Reason-code journal</h3>
      <div class="reason-list">${renderReasons(score.reasons)}</div>
    </section>
    <section class="detail-section">
      <h3 class="section-title">Underwriter next step</h3>
      <article class="reason-row">
        <span class="journal-state ${statusClass(nextAction.urgency)}">${esc(nextAction.urgency)} urgency</span>
        <strong>${esc(nextAction.action)}</strong>
      </article>
    </section>
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
  `;
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
    governance: () => renderGovernanceTab(),
    proof: () => renderProofTab(),
    sources: () => renderSourcesTab(score),
  };
  els.drawerTitle.textContent = drawerTitles[state.activeTab] || "Review packet";
  els.tabContent.setAttribute("aria-labelledby", `tab-${state.activeTab}`);
  els.tabContent.innerHTML = views[state.activeTab]?.() || views.decision();
  applyMeterWidths(els.tabContent);
  els.tabContent.scrollTop = 0;
}

function setTab(tab, openDrawer = true, { updateHistory = true } = {}) {
  if (!VALID_TABS.includes(tab)) tab = "decision";
  state.activeTab = tab;
  els.tabs.querySelectorAll("[data-tab]").forEach((button) => {
    const selected = button.dataset.tab === tab;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  renderTabContent();
  if (openDrawer) setDrawerOpen(true);
  if (updateHistory) writeUrlState({ includeView: openDrawer });
}

function closeDrawer({ updateHistory = true, restoreFocus = true } = {}) {
  setDrawerOpen(false, restoreFocus);
  if (updateHistory) writeUrlState({ replace: true, includeView: false });
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
  setTab(tabs[next].dataset.tab, true);
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
  els.decisionStamp.innerHTML = `<div class="skeleton">Refreshing decision summary...</div>`;
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
    renderDecisionStamp(score);
    renderTabContent();
    setApiStatus(true, "Live API");
    updateStatusLine();
    if (updateHistory) writeUrlState({ replace: true });
  } catch (error) {
    if (loadToken !== activeLoadToken) return; // a newer load owns the screen now
    setApiStatus(false, "Offline");
    els.caseSummary.innerHTML = errorState("Borrower decision unavailable", error.message);
    els.decisionStamp.innerHTML = `<div class="empty-state">Decision summary unavailable while the API is offline.</div>`;
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
    if (button) setTab(button.dataset.tab, true);
  });
  els.tabs.addEventListener("keydown", handleTabKeydown);
  els.drawerToggle.addEventListener("click", () => {
    setDrawerOpen(true);
    writeUrlState({ includeView: true });
  });
  els.drawerClose.addEventListener("click", () => closeDrawer());
  els.drawerScrim.addEventListener("click", () => closeDrawer());
  els.drawer.addEventListener("keydown", trapDrawerFocus);
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-retry]")) window.location.reload();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.drawerOpen) closeDrawer();
  });
  window.addEventListener("popstate", async () => {
    const urlState = readUrlState();
    const caseId = state.msmes.some((item) => item.id === urlState.caseId)
      ? urlState.caseId
      : state.msmes[0]?.id;
    if (caseId && caseId !== state.activeId) await loadCase(caseId, { updateHistory: false });
    if (urlState.view) {
      setTab(urlState.view, true, { updateHistory: false });
    } else {
      setTab("decision", false, { updateHistory: false });
      closeDrawer({ updateHistory: false, restoreFocus: false });
    }
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
    ]);
    const [governance, validation, model, deployment, outcomeContract, submissionProof] = optional.map(settledValue);

    state.health = health;
    state.msmes = msmes;
    state.portfolio = portfolio;
    state.governance = governance;
    state.validation = validation;
    state.model = model;
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
    if (urlState.view) setTab(urlState.view, true, { updateHistory: false });
    else setTab("decision", false, { updateHistory: false });
  } catch (error) {
    setApiStatus(false, "Offline");
    els.caseSummary.innerHTML = errorState("Startup check failed", error.message);
    els.decisionStamp.innerHTML = `<div class="empty-state">Model and audit status could not be fetched.</div>`;
    els.tabContent.innerHTML = `<div class="empty-state">The review shell loaded, but API evidence could not be fetched.</div>`;
  }
}

init();
