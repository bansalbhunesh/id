// Unit tests for the pure presentation helpers.
// Run: node --test frontend/tests/lib.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const lib = require("../lib.js");

test("esc neutralises every HTML-active character", () => {
  assert.equal(
    lib.esc(`<img src=x onerror="alert('1')">&`),
    "&lt;img src=x onerror=&quot;alert(&#039;1&#039;)&quot;&gt;&amp;",
  );
  assert.equal(lib.esc(null), "");
  assert.equal(lib.esc(0), "0");
});

test("formatCurrency uses Indian digit grouping without paise", () => {
  assert.equal(lib.formatCurrency(2700000).replace(/ /g, ""), "₹27,00,000");
  assert.equal(lib.formatCurrency(3023000).replace(/ /g, ""), "₹30,23,000");
  assert.equal(lib.formatCurrency(null).replace(/ /g, ""), "₹0");
});

test("titleize converts snake_case field names to display labels", () => {
  assert.equal(lib.titleize("digital_footprint"), "Digital Footprint");
  assert.equal(lib.titleize(undefined), "-");
});

test("statusClass maps decision words to ledger entry colours", () => {
  assert.equal(lib.statusClass("Rejected"), "entry-red");
  assert.equal(lib.statusClass("fail"), "entry-red");
  assert.equal(lib.statusClass("Approved"), "approved");
  assert.equal(lib.statusClass("Pass"), "approved");
  assert.equal(lib.statusClass("Watch"), "");
  assert.equal(lib.statusClass(undefined), "");
});

test("fmtCi renders bootstrap intervals and tolerates absence", () => {
  assert.equal(lib.fmtCi({ lower_95: 0.9605, upper_95: 0.9638 }), " [0.9605 - 0.9638]");
  assert.equal(lib.fmtCi(null), "");
});

test("itemTitle/itemDetail follow the journal precedence order", () => {
  assert.equal(lib.itemTitle({ control: "Debt-load cap", code: "X" }), "Debt-load cap");
  assert.equal(lib.itemTitle({ common_pattern: "Score-card-only demo" }), "Score-card-only demo");
  assert.equal(lib.itemTitle({}), "Review item");
  assert.equal(lib.itemDetail({ detail: "d", proof: "p" }), "d");
  assert.equal(lib.itemDetail({}), "");
});

test("reasonText picks the requested language and falls back", () => {
  const row = { en: "Strong: Liquidity (16/20)", hi: "मज़बूत: तरलता (16/20)" };
  assert.equal(lib.reasonText(row, "en"), row.en);
  assert.equal(lib.reasonText(row, "hi"), row.hi);
  assert.equal(lib.reasonText({ en: "only-en" }, "hi"), "only-en");
  assert.equal(lib.reasonText(null, "hi"), "");
});

test("nextActionText picks language with English fallback", () => {
  const nba = { action: "Document the reversal.", action_hi: "आधार दर्ज करें।" };
  assert.equal(lib.nextActionText(nba, "hi"), nba.action_hi);
  assert.equal(lib.nextActionText(nba, "en"), nba.action);
  assert.equal(lib.nextActionText(null, "en"), "");
});

test("limitBasisBinding names the active constraint honestly", () => {
  assert.equal(
    lib.limitBasisBinding({ binding_constraint: "grade_policy_cap" }),
    "The grade policy cap is the binding constraint.",
  );
  assert.equal(
    lib.limitBasisBinding({ binding_constraint: "debt_service_capacity" }),
    "Spare EMI capacity is the binding constraint.",
  );
  assert.equal(lib.limitBasisBinding(null), "");
});
