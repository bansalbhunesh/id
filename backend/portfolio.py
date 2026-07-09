"""Portfolio and governance summaries for the UdyamPulse demo."""
from collections import defaultdict

from pilot_metrics import build_pilot_metrics
from sample_data import SAMPLE_PROFILES
from scoring import score_profile


def _approval_rate(results: list[dict], decision_key: str) -> float:
    if not results:
        return 0.0
    approved = sum(1 for item in results if item[decision_key] == "Approved")
    return round(approved / len(results) * 100, 1)


def _grouped_approval(results: list[dict], field: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in results:
        groups[item["profile"][field]].append(item)

    return [
        {
            "group": group,
            "count": len(items),
            "average_score": round(sum(item["score"] for item in items) / len(items), 1),
            "alternate_approval_rate": _approval_rate(items, "alternate_data_decision"),
        }
        for group, items in sorted(groups.items())
    ]


def _vintage_bucket(months: int) -> str:
    if months < 24:
        return "<24 months"
    if months < 60:
        return "24-59 months"
    return "60+ months"


def _grouped_approval_by_value(results: list[dict], label: str, values: list[str]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item, value in zip(results, values):
        groups[value].append(item)

    return [
        {
            "group": group,
            "count": len(items),
            "average_score": round(sum(item["score"] for item in items) / len(items), 1),
            "alternate_approval_rate": _approval_rate(items, "alternate_data_decision"),
            "dimension": label,
        }
        for group, items in sorted(groups.items())
    ]


def build_portfolio_snapshot() -> dict:
    scored = [
        {"id": msme_id, **score_profile(profile, record_audit=False)}
        for msme_id, profile in SAMPLE_PROFILES.items()
    ]
    rescued = [
        item
        for item in scored
        if item["traditional"]["decision"] == "Rejected"
        and item["alternate_data_decision"] == "Approved"
    ]
    ntc_cases = [item for item in scored if not item["profile"]["has_bureau_history"]]
    alternate_approvals = [
        item for item in scored if item["alternate_data_decision"] == "Approved"
    ]
    traditional_approvals = [
        item for item in scored if item["traditional"]["decision"] == "Approved"
    ]

    snapshot = {
        "cohort_label": "Synthetic Stage-1 demo cohort with Stage-2 sandbox contracts",
        "summary": {
            "cases": len(scored),
            "traditional_approvals": len(traditional_approvals),
            "alternate_data_approvals": len(alternate_approvals),
            "ntc_cases": len(ntc_cases),
            "ntc_rescued": len([item for item in rescued if not item["profile"]["has_bureau_history"]]),
            "credit_unlocked": round(sum(item["eligible_limit"] for item in rescued), 2),
            "average_score": round(sum(item["score"] for item in scored) / len(scored), 1),
            "decision_time_minutes": 3,
            "manual_baseline_days": 7,
        },
        "cases": [
            {
                "id": item["id"],
                "name": item["name"],
                "sector": item["profile"]["sector"],
                "district": item["profile"]["district"],
                "gender": item["profile"]["gender"],
                "vintage_bucket": _vintage_bucket(item["profile"]["vintage_months"]),
                "score": item["score"],
                "grade": item["grade"],
                "risk_band": item["risk_band"],
                "eligible_limit": item["eligible_limit"],
                "traditional_decision": item["traditional"]["decision"],
                "alternate_data_decision": item["alternate_data_decision"],
                "focus_pillar": (
                    item["improvement_plan"]["focus_pillar"]
                    if item["improvement_plan"]
                    else "maintain"
                ),
            }
            for item in scored
        ],
        "fairness": {
            "note": "Demo-cohort check only; Stage 2 should run out-of-time validation and disparate-impact monitoring on IDBI sandbox data.",
            "by_sector": _grouped_approval(scored, "sector"),
            "by_geography": _grouped_approval(scored, "district"),
            "by_vintage": _grouped_approval_by_value(
                scored,
                "vintage",
                [_vintage_bucket(item["profile"]["vintage_months"]) for item in scored],
            ),
            "by_gender": _grouped_approval(scored, "gender"),
            "by_bureau_history": [
                {
                    "group": "Bureau history present",
                    "count": len([item for item in scored if item["profile"]["has_bureau_history"]]),
                    "alternate_approval_rate": _approval_rate(
                        [item for item in scored if item["profile"]["has_bureau_history"]],
                        "alternate_data_decision",
                    ),
                },
                {
                    "group": "New-to-Credit/New-to-Bank",
                    "count": len(ntc_cases),
                    "alternate_approval_rate": _approval_rate(
                        ntc_cases, "alternate_data_decision"
                    ),
                },
            ],
        },
    }
    snapshot["pilot_metrics"] = build_pilot_metrics(snapshot)
    return snapshot


def build_governance_summary(audit_events: list[dict]) -> dict:
    portfolio = build_portfolio_snapshot()
    latest = audit_events[-1] if audit_events else None

    return {
        "model": {
            "name": "UdyamPulse alternate-data MSME scorecard",
            "version": "0.3.0-stage2-ready",
            "training_data": "Demo cohort remains synthetic for the public build; /sandbox/score accepts consented AA/GST/UPI/EPFO/Bureau payloads for IDBI sandbox recalibration.",
            "explainability": "Current model returns exact linear Shapley attribution plus reason codes; XGBoost/LightGBM SHAP is the production-scale upgrade path.",
        },
        "controls": [
            {
                "control": "Explainable decision",
                "evidence": "Every score returns ranked reason codes and feature-level Shapley contributions.",
                "status": "Live",
            },
            {
                "control": "Audit reconstruction",
                "evidence": "Every scoring call appends borrower, score, grade, verdict, and reasons to /audit-log.",
                "status": "Live",
            },
            {
                "control": "Human override lane",
                "evidence": "Grade C and policy-watch files are routed as bankable-with-conditions instead of auto-approved.",
                "status": "Live",
            },
            {
                "control": "Fairness monitor",
                "evidence": "Demo cohort is grouped by sector, geography, vintage, gender, and bureau-history status; Stage 2 validates disparate impact on sandbox outcomes.",
                "status": "Prototype",
            },
            {
                "control": "Out-of-time validation",
                "evidence": "Validation API reports AUC, Gini, KS, PSI drift, and reason-code stability before pilot rollout.",
                "status": "Stage 2 ready",
            },
        ],
        "audit": {
            "events_recorded": len(audit_events),
            "latest_decision": latest,
        },
        "fairness": portfolio["fairness"],
        "pilot_metrics": portfolio["pilot_metrics"],
        "deployment": {
            "surface": "Single FastAPI service serving API plus static frontend",
            "fallback": "Template memo generation keeps the demo stable without live LLM credentials.",
            "stage2_swap": "AWS Bedrock memo and IDBI sandbox data can replace the current seams without changing the UI contract.",
        },
    }
