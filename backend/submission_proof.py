"""Submission proof payload for judges and reviewers.

This module deliberately summarizes implemented backend capabilities. It does
not claim production calibration, private IDBI access, or live bank data.
"""
from __future__ import annotations

from typing import Any

from deployment_gate import build_deployment_readiness
from ml import model_evaluation
from operational import release_metadata
from portfolio import build_governance_summary, build_portfolio_snapshot
from sample_data import SAMPLE_PROFILES
from scoring import score_profile
from sme_benchmark import sme_benchmark_summary


API_CATALOG = [
    {
        "method": "GET",
        "path": "/health/ready",
        "layer": "Operational readiness",
        "proves": "Release identity, serving provider and committed artifact integrity are machine-readable for deployment probes.",
    },
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
        "path": "/sandbox/pilot-readiness",
        "layer": "Temporal data gate",
        "proves": "Dated sandbox outcomes are maturity-checked and split chronologically into development, calibration and true later-period OOT cohorts.",
    },
    {
        "method": "GET",
        "path": "/deployment/readiness",
        "layer": "Promotion control",
        "proves": "Pilot/production startup blockers are machine-readable and fail closed outside public-demo mode.",
    },
    {
        "method": "POST",
        "path": "/validation/report",
        "layer": "Model monitoring",
        "proves": "Out-of-time AUC, Gini, KS, PSI drift, and reason-code stability are computed from supplied records.",
    },
    {
        "method": "GET",
        "path": "/model/sme-benchmark",
        "layer": "Real-outcome benchmark",
        "proves": "The production methodology is validated on REAL SBA small-business charge-offs and out of distribution on a differently-distributed real sample -- real outcomes, not synthetic labels.",
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
    {
        "method": "GET",
        "path": "/rails/ocen/offer/{id}",
        "layer": "Lending rail output",
        "proves": "Every verdict reshapes into an OCEN 4.0-aligned, deterministically replayable loan-offer artifact with documented risk-based pricing -- or an honest review/reject status.",
    },
    {
        "method": "GET",
        "path": "/consent/contract",
        "layer": "Consent",
        "proves": "The purpose/scope/expiry/revocation rules the sandbox route enforces are machine-readable, and each names the request that triggers it.",
    },
    {
        "method": "GET",
        "path": "/msmes/{id}/whatif",
        "layer": "Underwriter tooling",
        "proves": "Single-lever hypotheticals re-run the identical bounded pipeline side-effect-free -- 'what would it take?' is answerable without a payload editor.",
    },
]


BACKEND_CAPABILITIES = [
    {
        "layer": "Scoring engine",
        "modules": ["scoring.py", "sample_data.py"],
        "implemented": "Five-pillar scorecard, risk band, EMI-capacity indicative limit, traditional-vs-alternate verdict, policy guardrails.",
    },
    {
        "layer": "Explainability",
        "modules": ["ml.py", "pd_model.py", "xgb_pd_model.py"],
        "implemented": "Calibrated XGBoost champion with native exact TreeSHAP, calibrated logistic fallback, and score/PD/policy separation.",
    },
    {
        "layer": "Sandbox ingestion",
        "modules": ["feed_ingestion.py", "recalibration.py", "pilot_readiness.py"],
        "implemented": "IDBI sandbox-style feed contracts, source profiling, a dated 12-month outcome contract, automatic chronological splits, maturity checks, and segment-volume gates.",
    },
    {
        "layer": "Lending rail output",
        "modules": ["rails.py", "whatif.py", "consent_surface.py"],
        "implemented": "OCEN 4.0-aligned offer artifacts with documented pricing policy, an honest per-rail integration register, a visible enforced consent contract, and single-lever what-if re-scoring.",
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
    {
        "layer": "Deployment promotion",
        "modules": ["deployment_gate.py", "operational.py", "auth.py", "main.py"],
        "implemented": "Public demo mode is explicit; requests are traced and bounded; pilot/production startup fails closed until private credentials, IDBI model scope, true OOT evidence, and durable audit storage pass.",
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
        "proof": "Runs as one non-root FastAPI service with static UI, readiness probe, two-job CI, Render Blueprint, and no mandatory paid API dependency in public mode.",
        "evidence": ["Dockerfile", "render.yaml", "GitHub Actions", "/health/ready"],
    },
    {
        "criterion": "Scalability",
        "proof": "Separates bounded ingestion, scoring, attribution, O(n log n) validation, audit, temporal readiness and promotion gates so Stage 2 can swap data/model/storage without rewriting the cockpit.",
        "evidence": ["/sandbox/score", "/sandbox/pilot-readiness", "/deployment/readiness"],
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
        "proof": "Surfaces domain-transfer limits, model-disagreement review, temporal/OOT gates, pseudonymised audit reconstruction, fairness monitoring, and fail-closed pilot promotion.",
        "evidence": ["MODEL_CARD.md", "/deployment/readiness", "/governance"],
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
        "udyampulse_advantage": "Governance exposes model evidence and a machine-enforced promotion gate; public-proxy artifacts cannot start in pilot mode.",
        "proof": "/deployment/readiness",
    },
    {
        "common_pattern": "Model evidence on synthetic labels or a single random holdout",
        "udyampulse_advantage": "A real small-business default benchmark trained on genuine SBA charge-offs and validated OUT OF DISTRIBUTION on a differently-distributed real sample -- real outcomes plus generalisation evidence, which a synthetic-label score or a re-scored random holdout cannot provide.",
        "proof": "/model/sme-benchmark",
    },
]


JUDGE_RUNBOOK = [
    {
        "step": "1. Check the service is live",
        "endpoint": "/health",
        "expected": "status is ok and the static cockpit is served by the same FastAPI deployable.",
    },
    {
        "step": "1b. Verify deployment readiness",
        "endpoint": "/health/ready",
        "expected": "release identity, active champion and committed artifact integrity are reported as ready for public-demo mode.",
    },
    {
        "step": "2. Verify the NTC reversal",
        "endpoint": "/msmes/ntc_hero/score",
        "expected": "traditional underwriting is Rejected while alternate-data underwriting is Approved with Grade A.",
    },
    {
        "step": "3. Inspect the bank decision pack",
        "endpoint": "/msmes/ntc_hero/score",
        "expected": "score, indicative limit, pillars, reason codes, Shapley attribution, memo, guardrails, and source map are present.",
    },
    {
        "step": "4. Validate model-risk controls",
        "endpoint": "/governance",
        "expected": "audit events, controls, validation metrics, pilot KPIs, fairness slices, and caveats are inspectable.",
    },
    {
        "step": "5. Confirm sandbox readiness without fake data claims",
        "endpoint": "/submission/proof",
        "expected": "truth boundary says private IDBI data is not claimed while sandbox ingestion, temporal validation and promotion gates are implemented.",
    },
    {
        "step": "6. Inspect fail-closed pilot promotion",
        "endpoint": "/deployment/readiness",
        "expected": "public demo remains available while pilot mode is explicitly blocked on private credentials, IDBI outcomes, true OOT evidence, and durable audit storage.",
    },
]


def build_submission_proof(audit_events: list[dict]) -> dict[str, Any]:
    portfolio = build_portfolio_snapshot()
    governance = build_governance_summary(audit_events)
    deployment = build_deployment_readiness()
    evaluation = model_evaluation()
    hero = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)

    return {
        "status": "submission_ready_backend_proof",
        "stage2_status": "temporal_and_deployment_gates_live",
        "release": release_metadata(),
        "truth_boundary": {
            "public_data": "synthetic_demo_cohort",
            "private_idbi_data": "not_claimed",
            "sandbox_access": "designed_for_post_shortlisting_api_access",
            "production_model": "public_proxy_xgboost_not_bank_calibrated; retraining_on_idbi_outcomes_required",
        },
        "pilot_promotion": "fail_closed_until_all_deployment_gates_pass",
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
                "Operational middleware assigns a request ID and enforces the declared-body ceiling",
                "Pydantic validates profile/feed constraints",
                "Scoring engine emits health card, verdict, limit, guardrails",
                "Calibrated PD champion adds exact logit-space TreeSHAP attribution",
                "Versioned policy separates score, PD estimate, and review route",
                "Memo layer creates deterministic underwriter memo",
                "Audit log records reconstructable decision event",
                "Governance APIs expose scalable validation, drift, fairness, and pilot KPIs",
                "Deployment gate blocks public-proxy promotion into pilot/production mode",
            ],
            "stage2_swap_points": [
                "Replace public synthetic cohort with consented IDBI sandbox feeds",
                "Run /sandbox/recalibration/report on real feature distributions and repayment labels",
                "Run /sandbox/pilot-readiness to create mature chronological development/calibration/OOT cohorts",
                "Retrain the existing champion/challenger pipeline on approved labelled sandbox outcomes",
                "Enable AWS Bedrock memo provider with deterministic fallback still active",
                "Swap in persistent audit storage for pilot operations",
            ],
        },
        "governance_controls": governance["controls"],
        "real_outcome_benchmark": sme_benchmark_summary(),
        "deployment_readiness": deployment,
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
