"""Portfolio and governance summaries for the UdyamPulse demo."""
from collections import defaultdict

from operational import APP_VERSION
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


def _fairness_monitor(dimension: str, rows: list[dict]) -> dict:
    if not rows:
        return {
            "dimension": dimension,
            "status": "Unavailable",
            "max_gap_pct": 0.0,
            "min_approval_rate": 0.0,
            "max_approval_rate": 0.0,
        }

    rates = [row["alternate_approval_rate"] for row in rows]
    gap = round(max(rates) - min(rates), 1)
    return {
        "dimension": dimension,
        "status": "Review" if gap > 20 else "Monitor",
        "max_gap_pct": gap,
        "min_approval_rate": min(rates),
        "max_approval_rate": max(rates),
    }


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

    by_sector = _grouped_approval(scored, "sector")
    by_geography = _grouped_approval(scored, "district")
    by_vintage = _grouped_approval_by_value(
        scored,
        "vintage",
        [_vintage_bucket(item["profile"]["vintage_months"]) for item in scored],
    )
    by_gender = _grouped_approval(scored, "gender")
    by_bureau_history = [
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
    ]

    snapshot = {
        "cohort_label": "Public synthetic cohort with sandbox feed contracts",
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
            "note": "Public cohort check only; production pilot requires outcome-linked disparate-impact monitoring on IDBI sandbox data.",
            "monitors": [
                _fairness_monitor("Bureau history", by_bureau_history),
                _fairness_monitor("Sector", by_sector),
                _fairness_monitor("Geography", by_geography),
                _fairness_monitor("Vintage", by_vintage),
                _fairness_monitor("Gender", by_gender),
            ],
            "by_sector": by_sector,
            "by_geography": by_geography,
            "by_vintage": by_vintage,
            "by_gender": by_gender,
            "by_bureau_history": by_bureau_history,
        },
    }
    snapshot["pilot_metrics"] = build_pilot_metrics(snapshot)
    return snapshot


def _redact_latest_decision(entry: dict | None) -> dict | None:
    """GET /governance and /submission/proof are public (no login flow for
    the judge-facing demo), so the most recent borrower's name is redacted
    here. Full records (name included) are only available via the
    auditor-gated GET /audit-log."""
    if entry is None:
        return None
    redacted = dict(entry)
    redacted.pop("subject_ref", None)
    redacted["subject"] = "[pseudonym removed from public governance response]"
    return redacted


def build_governance_summary(audit_events: list[dict]) -> dict:
    portfolio = build_portfolio_snapshot()
    latest = _redact_latest_decision(audit_events[-1] if audit_events else None)
    from ml import model_status
    from audit_log import verify_chain
    from deployment_gate import build_deployment_readiness

    chain = verify_chain(audit_events, require_genesis=False)

    return {
        "model": {
            "name": "UdyamPulse scorecard + calibrated PD champion/challenger",
            "version": f"{APP_VERSION}-flagship",
            "training_data": "Public borrower cohort is synthetic. The PD benchmark is trained on a 30,000-row public consumer-credit proxy; neither is IDBI/MSME outcome data.",
            "explainability": "Calibrated XGBoost uses native exact TreeSHAP in logit space; calibrated logistic remains the deterministic fallback.",
            "runtime": model_status(),
        },
        "controls": [
            {
                "control": "Explainable decision",
                "evidence": "Every score returns ranked reason codes and feature-level Shapley contributions.",
                "status": "Live",
            },
            {
                "control": "Audit reconstruction",
                "evidence": "Every scoring call appends a pseudonymous subject reference, score, grade, verdict, and reasons to /audit-log, "
                f"hash-chained entry to entry (chain_valid={chain['valid']}, entries_checked={len(audit_events)}). "
                "Full records require the auditor role; this evidence is redaction-safe.",
                "status": "Live" if chain["valid"] else "Broken",
            },
            {
                "control": "Human override lane",
                "evidence": "Grade C and policy-watch files are routed as bankable-with-conditions instead of auto-approved.",
                "status": "Live",
            },
            {
                "control": "Fairness monitor",
                "evidence": "Public cohort is grouped by sector, geography, vintage, gender, and bureau-history status; production pilot validates disparate impact on sandbox outcomes.",
                "status": "Monitor",
            },
            {
                "control": "Holdout and future OOT validation",
                "evidence": "Public evidence reports untouched holdout AUC/Gini/KS/PR-AUC/Brier/ECE, bootstrap intervals and PSI. True dated OOT remains blocked on IDBI sandbox outcomes and is not faked.",
                "status": "Holdout live / OOT pending sandbox",
            },
            {
                "control": "Real small-business outcome benchmark",
                "evidence": "Beyond the proxy holdout, the exact methodology is validated on REAL SBA small-business charge-offs and out of distribution on a differently-distributed real sample (see /model/sme-benchmark) -- real outcomes plus generalisation evidence, not synthetic labels.",
                "status": "Live",
            },
            {
                "control": "Pilot promotion gate",
                "evidence": "Pilot and production startup fail closed until private identity/HMAC credentials, an IDBI-scoped model, true OOT evidence, and durable audit storage are present.",
                "status": "Enforced",
            },
        ],
        "audit": {
            "events_recorded": len(audit_events),
            "latest_decision": latest,
        },
        "fairness": portfolio["fairness"],
        "pilot_metrics": portfolio["pilot_metrics"],
        "deployment": {
            **build_deployment_readiness(),
            "surface": "Single FastAPI service serving API plus static frontend",
            "fallback": "Deterministic memo generation keeps underwriting stable without live LLM credentials.",
            "stage2_swap": "AWS Bedrock memos and IDBI sandbox data plug into the current API contracts without changing the cockpit.",
        },
    }
