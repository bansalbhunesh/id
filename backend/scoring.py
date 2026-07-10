"""Rule-based MSME financial health scoring engine.

Five pillars, each 0-20, summed to a 0-100 score with an A-E grade.
The descriptive score stays separate from the calibrated XGBoost PD model
and the versioned lending policy so each layer can be audited independently.
"""
from pydantic import BaseModel, Field


class MSMEProfile(BaseModel):
    name: str
    sector: str = "General Trade"
    district: str = "Mumbai"
    gender: str | None = None
    vintage_months: int = Field(default=24, ge=0, le=600)
    employees: int = Field(default=12, ge=0)
    avg_monthly_inflow: float = Field(ge=0)
    inflow_volatility: float = Field(ge=0)  # coefficient of variation, 0-1+
    cheque_bounce_rate: float = Field(ge=0, le=1)  # 0-1
    gst_filing_streak_months: int = Field(ge=0, le=120)
    gst_turnover_growth_pct: float  # trailing 6mo, can be negative
    upi_txn_count_monthly: int = Field(ge=0)
    unique_counterparties: int = Field(ge=0)
    outstanding_debt_to_inflow: float = Field(ge=0)  # ratio
    has_bureau_history: bool = True  # False = New-to-Credit / New-to-Bank
    consent_status: str = "Not applicable: public synthetic demo data, no real consent required"


PILLAR_MAX = 20


def score_liquidity(p: MSMEProfile) -> int:
    if p.avg_monthly_inflow <= 0:
        return 0
    volatility_penalty = min(p.inflow_volatility, 1.0) * PILLAR_MAX
    return round(PILLAR_MAX - volatility_penalty)


def score_discipline(p: MSMEProfile) -> int:
    bounce_penalty = min(p.cheque_bounce_rate, 1.0) * PILLAR_MAX
    filing_bonus = min(p.gst_filing_streak_months / 24, 1.0) * PILLAR_MAX
    return round(max(0, min(PILLAR_MAX, (PILLAR_MAX - bounce_penalty + filing_bonus) / 2)))


def score_momentum(p: MSMEProfile) -> int:
    growth = max(-50, min(50, p.gst_turnover_growth_pct))
    return round((growth + 50) / 100 * PILLAR_MAX)


def score_leverage(p: MSMEProfile) -> int:
    ratio = max(0, p.outstanding_debt_to_inflow)
    return round(max(0, PILLAR_MAX - min(ratio, 1.0) * PILLAR_MAX))


def score_digital_footprint(p: MSMEProfile) -> int:
    counterparty_score = min(p.unique_counterparties / 50, 1.0) * (PILLAR_MAX / 2)
    volume_score = min(p.upi_txn_count_monthly / 200, 1.0) * (PILLAR_MAX / 2)
    return round(counterparty_score + volume_score)


def grade_for(total: int) -> str:
    if total >= 80:
        return "A"
    if total >= 65:
        return "B"
    if total >= 50:
        return "C"
    if total >= 35:
        return "D"
    return "E"


def eligible_limit(total: int, p: MSMEProfile) -> float:
    multiplier = {"A": 6, "B": 4, "C": 2.5, "D": 1, "E": 0}[grade_for(total)]
    return round(p.avg_monthly_inflow * multiplier, 2)


def risk_band_for(grade: str) -> str:
    return {
        "A": "Low risk",
        "B": "Low-moderate risk",
        "C": "Bankable with conditions",
        "D": "High risk",
        "E": "Decline",
    }[grade]


def traditional_verdict(p: MSMEProfile) -> dict:
    """What a bureau-only underwriting process would decide.

    Traditional retail/MSME underwriting leans heavily on credit bureau
    history; a business with none is typically declined outright,
    regardless of how healthy its actual cash flows are.
    """
    if not p.has_bureau_history:
        return {
            "decision": "Rejected",
            "reason": "No credit bureau history on file (New-to-Credit/New-to-Bank).",
        }
    if p.outstanding_debt_to_inflow > 0.6:
        return {
            "decision": "Rejected",
            "reason": "Existing debt load exceeds traditional underwriting threshold.",
        }
    return {"decision": "Approved", "reason": "Bureau history present and within thresholds."}


def data_source_signals(p: MSMEProfile) -> list[dict]:
    return [
        {
            "source": "Account Aggregator",
            "signal": f"Monthly inflow Rs {p.avg_monthly_inflow:,.0f}; volatility {p.inflow_volatility:.0%}",
            "status": "Connected",
        },
        {
            "source": "GST",
            "signal": f"{p.gst_filing_streak_months} month filing streak; turnover growth {p.gst_turnover_growth_pct:+.0f}%",
            "status": "Connected",
        },
        {
            "source": "UPI",
            "signal": f"{p.upi_txn_count_monthly} monthly txns across {p.unique_counterparties} counterparties",
            "status": "Connected",
        },
        {
            "source": "EPFO",
            "signal": f"{p.employees} employee-linked payroll footprint",
            "status": "Synthetic",
        },
        {
            "source": "Bureau",
            "signal": "History present" if p.has_bureau_history else "No bureau file",
            "status": "Present" if p.has_bureau_history else "Thin-file",
        },
    ]


def policy_guardrails(
    p: MSMEProfile,
    pillars: dict[str, int],
    total: int,
    policy: dict,
) -> list[dict]:
    return [
        {
            "control": "Consent data boundary",
            "status": "Pass",
            "detail": p.consent_status,
        },
        {
            "control": "Debt-load cap",
            "status": "Pass" if p.outstanding_debt_to_inflow <= 0.6 else "Watch",
            "detail": f"Outstanding debt is {p.outstanding_debt_to_inflow:.0%} of monthly inflow.",
        },
        {
            "control": "Conduct signal",
            "status": "Pass" if p.cheque_bounce_rate <= 0.08 else "Watch",
            "detail": f"Cheque bounce rate is {p.cheque_bounce_rate:.0%}; discipline pillar {pillars['discipline']}/20.",
        },
        {
            "control": "Explainability invariant",
            "status": "Pass",
            "detail": "Every decision returns ranked rule reasons plus exact Shapley feature attribution.",
        },
        {
            "control": "Human review lane",
            "status": "Review" if policy["decision"] == "Review" else "Pass",
            "detail": policy["reason"],
        },
        {
            "control": "PD guardrail",
            "status": "Review" if policy["pd_guardrail_triggered"] else "Pass",
            "detail": (
                f"Proxy PD {policy['pd_estimate']:.1%}; human-review threshold "
                f"{policy['pd_review_threshold']:.1%}. The proxy can route to review but never auto-declines."
            ),
        },
    ]


def decision_path(
    p: MSMEProfile,
    total: int,
    grade: str,
    traditional: dict,
    policy: dict,
) -> list[dict]:
    return [
        {
            "stage": "Traditional bureau screen",
            "decision": traditional["decision"],
            "evidence": traditional["reason"],
        },
        {
            "stage": "Alternate-data health card",
            "decision": policy["decision"],
            "evidence": (
                f"Composite score {total}/100, grade {grade}, {risk_band_for(grade).lower()}; "
                f"proxy PD {policy['pd_estimate']:.1%}."
            ),
        },
        {
            "stage": "Credit-line recommendation",
            "decision": "Limit generated" if eligible_limit(total, p) > 0 else "No limit",
            "evidence": f"Eligible working-capital limit Rs {eligible_limit(total, p):,.0f}.",
        },
    ]


def apply_decision_policy(grade: str, pd_estimate: float | None, pd_threshold: float | None) -> dict:
    """Separate descriptive score, risk estimate and lending policy.

    The public proxy PD may route a nominally bankable file to human review,
    but it is never allowed to auto-decline an MSME across domains. Grades D/E
    remain rule-policy declines; grade C is always reviewed.
    """
    estimate = float(pd_estimate) if pd_estimate is not None else 0.0
    threshold = float(pd_threshold) if pd_threshold is not None else 1.0
    pd_triggered = pd_estimate is not None and estimate >= threshold
    if grade in ("D", "E"):
        decision = "Rejected"
        route = "policy_decline"
        reason = f"Grade {grade} is outside the bankable scorecard range."
    elif grade == "C":
        decision = "Review"
        route = "mandatory_human_review"
        reason = "Grade C is bankable only with conditions and mandatory underwriter review."
    elif pd_triggered:
        decision = "Review"
        route = "model_disagreement_review"
        reason = (
            "The scorecard is bankable but the cross-domain proxy PD crossed its calibrated "
            "review threshold; an underwriter must resolve the disagreement."
        )
    else:
        decision = "Approved"
        route = "fast_track_eligible"
        reason = "Grade A/B and proxy PD below the review threshold; eligible for fast-track approval."
    return {
        "version": "policy-v2-score-pd-separation",
        "decision": decision,
        "route": route,
        "reason": reason,
        "pd_estimate": estimate,
        "pd_review_threshold": threshold,
        "pd_guardrail_triggered": pd_triggered,
        "auto_decline_from_proxy_model": False,
    }


IMPROVEMENT_ACTIONS = {
    "liquidity": "Smooth out month-to-month cash inflow swings (e.g. staggered receivables) to lower volatility.",
    "discipline": "Reduce cheque bounces and keep GST filings continuous, month after month.",
    "momentum": "Grow GST-reported turnover consistently over the next few filing cycles.",
    "leverage": "Pay down outstanding debt relative to monthly inflow.",
    "digital_footprint": "Route more transactions through UPI and widen the base of counterparties paid/received from.",
}

IMPROVEMENT_STEP = 5  # assumed achievable pillar-point gain from acting on the suggestion


def improvement_plan(pillars: dict[str, int], p: MSMEProfile) -> dict | None:
    """What would move this business to the next grade, and by how much."""
    current_total = sum(pillars.values())
    current_grade = grade_for(current_total)
    if current_grade == "A":
        return None

    weakest_pillar = min(pillars, key=pillars.get)
    improved_value = min(PILLAR_MAX, pillars[weakest_pillar] + IMPROVEMENT_STEP)
    potential_total = current_total - pillars[weakest_pillar] + improved_value
    potential_grade = grade_for(potential_total)
    potential_limit = eligible_limit(potential_total, p)
    current_limit = eligible_limit(current_total, p)

    return {
        "focus_pillar": weakest_pillar,
        "action": IMPROVEMENT_ACTIONS[weakest_pillar],
        "potential_grade": potential_grade,
        "potential_eligible_limit": potential_limit,
        "limit_increase": round(potential_limit - current_limit, 2),
    }


def reason_codes(pillars: dict[str, int]) -> list[str]:
    reasons = []
    for name, value in pillars.items():
        label = name.replace("_", " ").title()
        if value >= 16:
            reasons.append(f"Strong: {label} ({value}/20)")
        elif value <= 8:
            reasons.append(f"Watch: {label} ({value}/20)")
    return reasons


def score_profile(p: MSMEProfile, record_audit: bool = True) -> dict:
    pillars = {
        "liquidity": score_liquidity(p),
        "discipline": score_discipline(p),
        "momentum": score_momentum(p),
        "leverage": score_leverage(p),
        "digital_footprint": score_digital_footprint(p),
    }
    total = sum(pillars.values())
    grade = grade_for(total)
    traditional = traditional_verdict(p)

    from ml import explain, pd_policy_threshold  # local import avoids circular import at module load

    model_explanation = explain(p, pillars)
    policy = apply_decision_policy(
        grade,
        model_explanation.get("pd_estimate"),
        pd_policy_threshold(),
    )
    alternate_data_decision = policy["decision"]
    result = {
        "name": p.name,
        "profile": {
            "sector": p.sector,
            "district": p.district,
            "gender": p.gender or "Unavailable",
            "vintage_months": p.vintage_months,
            "employees": p.employees,
            "has_bureau_history": p.has_bureau_history,
        },
        "score": total,
        "grade": grade,
        "risk_band": risk_band_for(grade),
        "pillars": pillars,
        "eligible_limit": eligible_limit(total, p),
        "reasons": reason_codes(pillars),
        "traditional": traditional,
        "alternate_data_decision": alternate_data_decision,
        "policy": policy,
        "improvement_plan": improvement_plan(pillars, p),
        "data_sources": data_source_signals(p),
        "policy_guardrails": policy_guardrails(p, pillars, total, policy),
        "decision_path": decision_path(p, total, grade, traditional, policy),
    }

    from agent_memo import generate_memo
    import audit_log

    result["ml"] = model_explanation
    result["pd_estimate"] = result["ml"].get("pd_estimate")
    result["memo"] = generate_memo(result)
    if record_audit:
        audit_log.record(result)
    return result
