"""Submission proof payload for judges and reviewers.

This module deliberately summarizes implemented backend capabilities. It does
not claim production calibration, private IDBI access, or live bank data.
"""
from __future__ import annotations

from typing import Any

from ml import model_evaluation
from portfolio import build_governance_summary, build_portfolio_snapshot
from sample_data import SAMPLE_PROFILES
from scoring import score_profile


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
        "proves": "Underwriter-authenticated custom scoring proves the scorecard is not hard-coded to the public cohort.",
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
        "modules": ["ml.py", "pd_model.py", "xgb_pd_model.py"],
        "implemented": "Calibrated XGBoost champion with native exact TreeSHAP, calibrated logistic fallback, and score/PD/policy separation.",
    },
    {
        "layer": "Sandbox ingestion",
        "modules": ["feed_ingestion.py", "recalibration.py"],
        "implemented": "IDBI sandbox-style AA/GST/UPI/EPFO/Bureau contracts, source readiness, distribution profiling, label readiness checks.",
    },
    {
        "layer": "Model governance",
        "modules": ["portfolio.py", "pilot_metrics.py", "validation.py"],
        "implemented": "Proxy holdout fairness slices, pilot-target labelling, bootstrap intervals, PSI stability, reason-code controls, governance summary.",
    },
    {
        "layer": "Audit and memo",
        "modules": ["audit_log.py", "agent_memo.py"],
        "implemented": "Pseudonymised restart-safe hash-chain events and deterministic underwriter memo with optional Bedrock provider fallback.",
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
        "proof": "Implements Pydantic validation, score/PD/policy contracts, calibrated XGBoost TreeSHAP, holdout metrics, fairness slices, scoped auth, and API-level proof.",
        "evidence": ["/score", "/validation/report", "/governance"],
    },
    {
        "criterion": "Governance readiness",
        "proof": "Surfaces domain-transfer limits, model-disagreement review, pseudonymised audit reconstruction, fairness monitoring, PSI, confidence intervals, and deterministic memo fallback.",
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
        "udyampulse_advantage": "Every score packet returns exact calibrated TreeSHAP/logistic contributions plus human-readable reason codes.",
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
    evaluation = model_evaluation()
    hero = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)

    return {
        "status": "submission_ready_backend_proof",
        "truth_boundary": {
            "public_data": "synthetic_demo_cohort",
            "private_idbi_data": "not_claimed",
            "sandbox_access": "designed_for_post_shortlisting_api_access",
            "production_model": "public_proxy_xgboost_not_bank_calibrated; retraining_on_idbi_outcomes_required",
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
                "Calibrated PD champion adds exact logit-space TreeSHAP attribution",
                "Versioned policy separates score, PD estimate, and review route",
                "Memo layer creates deterministic underwriter memo",
                "Audit log records reconstructable decision event",
                "Governance APIs expose validation, drift, fairness, and pilot KPIs",
            ],
            "stage2_swap_points": [
                "Replace public synthetic cohort with consented IDBI sandbox feeds",
                "Run /sandbox/recalibration/report on real feature distributions and repayment labels",
                "Retrain the existing champion/challenger pipeline on approved labelled sandbox outcomes",
                "Enable AWS Bedrock memo provider with deterministic fallback still active",
                "Swap in persistent audit storage for pilot operations",
            ],
        },
        "governance_controls": governance["controls"],
        "validation_metrics": (
            {
                "evidence_type": "held_out_model_evaluation",
                "auc": evaluation["splits"]["holdout"]["auc"],
                "gini": evaluation["splits"]["holdout"]["gini"],
                "ks": evaluation["splits"]["holdout"]["ks"],
                "pr_auc": evaluation["splits"]["holdout"]["pr_auc"],
                "brier_score": evaluation["splits"]["holdout"]["brier_score"],
                "expected_calibration_error": evaluation["splits"]["holdout"]["expected_calibration_error"],
                "n": evaluation["splits"]["holdout"]["n"],
                "dataset": evaluation["dataset"]["name"],
                "note": "Untouched random holdout metrics from a public proxy dataset, not OOT and not IDBI/MSME performance.",
            }
            if evaluation is not None
            else {
                "evidence_type": "unavailable",
                "note": "No trained PD artifact found. Run backend/model_training/train_pd_model.py.",
            }
        ),
        "validation_status": "ready" if evaluation is not None else "insufficient_sample",
    }
