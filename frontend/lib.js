/* Pure presentation helpers shared by app.js (browser) and the Node unit
   suite (frontend/tests/lib.test.mjs). No DOM access allowed in this file. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.UdyamLib = factory();
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const inr = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatCurrency(value) {
    return inr.format(Number(value || 0));
  }

  function titleize(value) {
    return String(value ?? "-")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function statusClass(value) {
    const text = String(value || "").toLowerCase();
    if (/(reject|decline|missing|fail|offline|high|thin)/.test(text)) return "entry-red";
    if (/(approved|pass|live|connected|ready|low|stable)/.test(text)) return "approved";
    return "";
  }

  function fmtCi(ci) {
    if (!ci) return "";
    return ` [${ci.lower_95} - ${ci.upper_95}]`;
  }

  function itemTitle(item) {
    return item.control || item.code || item.stage || item.source || item.layer
      || item.step || item.title || item.criterion || item.common_pattern || "Review item";
  }

  function itemDetail(item) {
    return item.detail || item.evidence || item.signal || item.proves || item.expected
      || item.implemented || item.udyampulse_advantage || item.proof || "";
  }

  function reasonText(row, lang) {
    if (!row) return "";
    return lang === "hi" ? (row.hi || row.en || "") : (row.en || row.hi || "");
  }

  function nextActionText(nextAction, lang) {
    if (!nextAction) return "";
    return lang === "hi" ? (nextAction.action_hi || nextAction.action) : nextAction.action;
  }

  function limitBasisBinding(basis) {
    if (!basis) return "";
    return basis.binding_constraint === "debt_service_capacity"
      ? "Spare EMI capacity is the binding constraint."
      : "The grade policy cap is the binding constraint.";
  }

  return {
    esc,
    formatCurrency,
    titleize,
    statusClass,
    fmtCi,
    itemTitle,
    itemDetail,
    reasonText,
    nextActionText,
    limitBasisBinding,
  };
});
