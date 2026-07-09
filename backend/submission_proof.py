"""Submission proof payload for judges and reviewers.

This module deliberately summarizes implemented backend capabilities. It does
not claim production calibration, private IDBI access, or live bank data.
"""
from __future__ import annotations

from typing import Any

from portfolio import build_governance_summary, build_portfolio_snapshot
from sample_data import SAMPLE_PROFILES
from scoring import score_profile
from validation import ValidationRecord, build_validation_report


def _demo_validation() -> dict[str, Any]:
    development = [
        ValidationRecord(score=82, defaulted=False, period="2026-Q1", reasons=["Strong GST filing"]),
        ValidationRecord(score=74, defaulted=False, period="2026-Q1", reasons=["Strong UPI velocity"]),
        ValidationRecord(score=66, defaulted=False, period="2026-Q1", reasons=["Strong counterparty breadth"]),
        ValidationRecord(score=54, defaulted=True, period="2026-Q1", reasons=["Watch: high leverage"]),
        ValidationRecord(score=43, defaulted=True, period="2026-Q1", reasons=["Watch: cheque bounce rate"]),
        ValidationRecord(score=35, defaulted=True, period="2026-Q1", reasons=["Watch: volatile cash flow"]),
    ]
    out_of_time = [
        ValidationRecord(score=81, defaulted=False, period="2026-Q2", reasons=["Strong GST filing"]),
        ValidationRecord(score=73, defaulted=False, period="2026-Q2", reasons=["Strong UPI velocity"]),
        ValidationRecord(score=65, defaulted=False, period="2026-Q2", reasons=["Strong counterparty breadth"]),
        ValidationRecord(score=52, defaulted=True, period="2026-Q2", reasons=["Watch: high leverage"]),
        ValidationRecord(score=44, defaulted=True, period="2026-Q2", reasons=["Watch: cheque bounce rate"]),
        ValidationRecord(score=36, defaulted=True, period="2026-Q2", reasons=["Watch: volatile cash flow"]),
    ]
    return build_validation_report(development, out_of_time)


API_CATALOG = [
    {
        "method": "GET",
        "path": "/msmes/{id}/score",
        "layer": "Decision pack",
        "proves": "Every borrower returns score, grade, limit, reason codes, Shapley attribution, memo, decision path, and guardrails.",
    },
    {
        "method": "POST",
        "path": "/score",
        "layer": "Custom scoring",
        "proves": "The scorecard is not hard-coded to the public cohort; validators reject impossible underwriting values.",
    },
    {
        "method": "POST",
        "path": "/sandbox/score",
        "layer": "Sandbox ingestion",
        "proves": "AA/GST/UPI/EPFO/Bureau-style payloads normalize into the same scoring contract.",
    },
    {
        "method": "POST",
        "path": "/sandbox/recalibration/report",
        "layer": "Recalibration",
        "proves": "Sandbox distributions, source coverage, outcome labels, and GBM/SHAP readiness are profiled before pilot rollout.",
    },
    {
        "method": "POST",
        "path": "/validation/report",
        "layer": "Model monitoring",
        "proves": "Out-of-time AUC, Gini, KS, PSI drift, and reason-code stability are computed from supplied records.",
    },
    {
        "method": "GET",
        "path": "/governance",
        "layer": "Controls",
        "proves": "Model status, audit count, controls, fairness slices, pilot KPIs, and deployment limits are inspectable.",
    },
    {
        "method": "GET",
        "path": "/audit-log",
        "layer": "Audit",
        "proves": "Scoring calls append reconstructable decision events.",
    },
]


BACKEND_CAPABILITIES = [
    {
        "layer": "Scoring engine",
        "modules": ["scoring.py", "sample_data.py"],
        "implemented": "Five-pillar scorecard, risk band, eligible limit, traditional-vs-alternate verdict, policy guardrails.",
    },
    {
        "layer": "Explainability",
        "modules": ["linear_model.py", "ml.py"],
        "implemented": "Dependency-free linear PD-proxy with exact Shapley-equivalent feature contributions and optional GBM runtime gate.",
    },
    {
        "layer": "Sandbox ingestion",
        "modules": ["feed_ingestion.py", "recalibration.py"],
        "implemented": "IDBI sandbox-style AA/GST/UPI/EPFO/Bureau contracts, source readiness, distribution profiling, label readiness checks.",
    },
    {
        "layer": "Model governance",
        "modules": ["portfolio.py", "pilot_metrics.py", "validation.py"],
        "implemented": "Fairness slices, pilot KPIs, out-of-time validation, PSI drift, reason-code stability, governance summary.",
    },
    {
        "layer": "Audit and memo",
        "modules": ["audit_log.py", "agent_memo.py"],
        "implemented": "Reconstructable score events and deterministic underwriter memo with optional Bedrock provider fallback.",
    },
]


RUBRIC_SCORECARD = [
    {
        "criterion": "Innovation",
        "proof": "Moves beyond a generic score by showing bureau rejection reversal, alternate-data approval, explainability, memo, borrower plan, and audit trail together.",
        "evidence": ["/msmes/ntc_hero/score", "/submission/proof"],
    },
    {
        "criterion": "Feasibility",
        "proof": "Runs as one FastAPI service with static UI, Dockerfile, Render Blueprint, automated tests, and no mandatory paid API dependency in public mode.",
        "evidence": ["Dockerfile", "render.yaml", "GitHub Actions", "/health"],
    },
    {
        "criterion": "Scalability",
        "proof": "Separates validation, ingestion, scoring, attribution, audit, recalibration, and governance so Stage 2 can swap data/model/storage without rewriting the cockpit.",
        "evidence": ["/sandbox/score", "/sandbox/recalibration/report", "/model/status"],
    },
    {
        "criterion": "Business impact",
        "proof": "Quantifies NTC rescues, credit unlocked, approval lift, decision-time reduction, early-NPA guardrail, and portfolio diversification in the public cohort.",
        "evidence": ["/portfolio", "/pilot-metrics"],
    },
    {
        "criterion": "Technical implementation",
        "proof": "Implements Pydantic validation, score contracts, exact linear Shapley attribution, validation metrics, fairness slices, and API-level proof instead of static UI claims.",
        "evidence": ["/score", "/validation/report", "/governance"],
    },
    {
        "criterion": "Governance readiness",
        "proof": "Surfaces model limitations, human review lane, audit reconstruction, fairness monitoring, PSI drift, reason-code stability, and deterministic memo fallback.",
        "evidence": ["MODEL_CARD.md", "/audit-log", "/governance"],
    },
]


COMPETITOR_GAP_MAP = [
    {
        "common_pattern": "Score-card-only demo",
        "udyampulse_advantage": "Full bank decision pack: verdict comparison, limit, pillars, reasons, Shapley attribution, memo, guardrails, and improvement plan.",
        "proof": "/msmes/ntc_hero/score",
    },
    {
        "common_pattern": "Frontend-first prototype",
        "udyampulse_advantage": "Backend-verifiable API catalog and submission proof endpoint expose the same evidence shown in the cockpit.",
        "proof": "/submission/proof",
    },
    {
        "common_pattern": "Alternate-data claims without sandbox path",
        "udyampulse_advantage": "Sandbox-style AA/GST/UPI/EPFO/Bureau ingestion and recalibration contracts are implemented now, while private access is not falsely claimed.",
        "proof": "/sandbox/score",
    },
    {
        "common_pattern": "Explainability as a slide",
        "udyampulse_advantage": "Every score packet returns exact linear Shapley-equivalent contributions plus human-readable reason codes.",
        "proof": "/msmes/{id}/score",
    },
    {
        "common_pattern": "Missing model-risk story",
        "udyampulse_advantage": "Governance endpoint exposes audit, validation, drift, reason stability, fairness slices, pilot KPIs, and deployment caveats.",
        "proof": "/governance",
    },
]


JUDGE_RUNBOOK = [
    {
        "step": "1. Check the service is live",
        "endpoint": "/health",
        "expected": "status is ok and the static cockpit is served by the same FastAPI deployable.",
    },
    {
        "step": "2. Verify the NTC reversal",
        "endpoint": "/msmes/ntc_hero/score",
        "expected": "traditional underwriting is Rejected while alternate-data underwriting is Approved with Grade A.",
    },
    {
        "step": "3. Inspect the bank decision pack",
        "endpoint": "/msmes/ntc_hero/score",
        "expected": "score, eligible limit, pillars, reason codes, Shapley attribution, memo, guardrails, and source map are present.",
    },
    {
        "step": "4. Validate model-risk controls",
        "endpoint": "/governance",
        "expected": "audit events, controls, validation metrics, pilot KPIs, fairness slices, and caveats are inspectable.",
    },
    {
        "step": "5. Confirm sandbox readiness without fake data claims",
        "endpoint": "/submission/proof",
        "expected": "truth boundary says private IDBI data is not claimed while sandbox ingestion and recalibration swap points are implemented.",
    },
]


def build_submission_proof(audit_events: list[dict]) -> dict[str, Any]:
    portfolio = build_portfolio_snapshot()
    governance = build_governance_summary(audit_events)
    validation = _demo_validation()
    hero = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)

    return {
        "status": "submission_ready_backend_proof",
        "truth_boundary": {
            "public_data": "synthetic_demo_cohort",
            "private_idbi_data": "not_claimed",
            "sandbox_access": "designed_for_post_shortlisting_api_access",
            "production_model": "optional_stage2_gbm_shap_requires_labelled_outcomes",
        },
        "hero_reversal": {
            "case": hero["name"],
            "traditional_decision": hero["traditional"]["decision"],
            "alternate_data_decision": hero["alternate_data_decision"],
            "score": hero["score"],
            "grade": hero["grade"],
            "eligible_limit": hero["eligible_limit"],
            "top_reasons": hero["reasons"][:4],
            "top_model_attribution": hero["ml"]["top_reasons"][:4],
        },
        "portfolio_impact": portfolio["summary"],
        "backend_capabilities": BACKEND_CAPABILITIES,
        "rubric_scorecard": RUBRIC_SCORECARD,
        "competitor_gap_map": COMPETITOR_GAP_MAP,
        "judge_runbook": JUDGE_RUNBOOK,
        "api_catalog": API_CATALOG,
        "architecture": {
            "runtime": "single_fastapi_process_serves_api_and_static_cockpit",
            "request_flow": [
                "Borrower or sandbox payload enters FastAPI",
                "Pydantic validates profile/feed constraints",
                "Scoring engine emits health card, verdict, limit, guardrails",
                "ML layer adds exact Shapley attribution",
                "Memo layer creates deterministic underwriter memo",
                "Audit log records reconstructable decision event",
                "Governance APIs expose validation, drift, fairness, and pilot KPIs",
            ],
            "stage2_swap_points": [
                "Replace public synthetic cohort with consented IDBI sandbox feeds",
                "Run /sandbox/recalibration/report on real feature distributions and repayment labels",
                "Enable XGBoost/LightGBM + SHAP only after approved labelled volume exists",
                "Enable AWS Bedrock memo provider with deterministic fallback still active",
                "Swap in persistent audit storage for pilot operations",
            ],
        },
        "governance_controls": governance["controls"],
        "validation_metrics": validation["metrics"],
        "validation_status": validation["status"],
    }
