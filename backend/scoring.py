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
    top_counterparty_share_pct: float = Field(default=0.0, ge=0, le=100)  # 0 = not supplied
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


CONCENTRATION_WATCH_THRESHOLD_PCT = 40  # shared with the "Counterparty concentration" guardrail
CONCENTRATION_LIMIT_HAIRCUT = 0.85  # 15% reduction: exposure to one counterparty's own payment risk


def concentration_multiplier(p: MSMEProfile) -> float:
    """A single counterparty accounting for 40%+ of digital inflow value is a
    direct exposure to that counterparty's own payment behaviour, not just a
    disclosure point -- the eligible limit is sized down accordingly rather
    than purely off the grade."""
    if p.top_counterparty_share_pct >= CONCENTRATION_WATCH_THRESHOLD_PCT:
        return CONCENTRATION_LIMIT_HAIRCUT
    return 1.0


def eligible_limit(total: int, p: MSMEProfile) -> float:
    grade_multiplier = {"A": 6, "B": 4, "C": 2.5, "D": 1, "E": 0}[grade_for(total)]
    return round(p.avg_monthly_inflow * grade_multiplier * concentration_multiplier(p), 2)


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
            "control": "Counterparty concentration",
            "status": "Watch" if p.top_counterparty_share_pct >= CONCENTRATION_WATCH_THRESHOLD_PCT else "Pass",
            "detail": (
                f"{p.top_counterparty_share_pct:.0f}% of digital inflow value depends on a single "
                "counterparty; a payment disruption from that buyer would directly hit this "
                f"borrower's cash flow, so the eligible limit is reduced {(1 - CONCENTRATION_LIMIT_HAIRCUT):.0%} "
                "below the grade-only amount."
                if p.top_counterparty_share_pct >= CONCENTRATION_WATCH_THRESHOLD_PCT
                else f"No single counterparty exceeds {CONCENTRATION_WATCH_THRESHOLD_PCT}% of digital inflow "
                f"value ({p.top_counterparty_share_pct:.0f}% max); no limit reduction applied."
                if p.top_counterparty_share_pct > 0
                else "Counterparty concentration not supplied for this application; no limit reduction applied."
            ),
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
        {
            "control": "Data sufficiency",
            "status": "Watch" if policy["missing_data_sources"] else "Pass",
            "detail": (
                f"Source(s) not connected: {', '.join(policy['missing_data_sources'])}. Affected pillars "
                "reflect a missing signal, not confirmed risk, and cannot drive an auto-decision."
                if policy["missing_data_sources"]
                else "Every pillar is backed by a connected source."
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


def apply_decision_policy(
    grade: str,
    pd_estimate: float | None,
    pd_threshold: float | None,
    *,
    missing_data_sources: frozenset[str] = frozenset(),
) -> dict:
    """Separate descriptive score, risk estimate and lending policy.

    The public proxy PD may route a nominally bankable file to human review,
    but it is never allowed to auto-decline an MSME across domains. Grades D/E
    remain rule-policy declines; grade C is always reviewed.

    A pillar computed from a source the caller never connected (as opposed to
    a source that was connected and genuinely reported a weak signal) is a
    missing input, not an observed risk. Silently scoring that pillar at its
    worst-case floor and then auto-approving or auto-declining on it would
    penalise absence as if it were confirmed risk, so any missing pillar
    source always routes to review regardless of what the score/PD say.
    """
    estimate = float(pd_estimate) if pd_estimate is not None else 0.0
    threshold = float(pd_threshold) if pd_threshold is not None else 1.0
    pd_triggered = pd_estimate is not None and estimate >= threshold

    if missing_data_sources:
        decision, route = "Review", "insufficient_data_review"
        reason = (
            f"Source(s) not connected for this application: {', '.join(sorted(missing_data_sources))}. "
            "The affected pillar(s) reflect a missing signal, not confirmed risk, so this cannot be "
            "auto-approved or auto-declined; connect the source or have an underwriter verify it manually."
        )
    elif grade in ("D", "E"):
        decision, route = "Rejected", "policy_decline"
        reason = f"Grade {grade} is outside the bankable scorecard range."
    elif grade == "C":
        decision, route = "Review", "mandatory_human_review"
        reason = "Grade C is bankable only with conditions and mandatory underwriter review."
    elif pd_triggered:
        decision, route = "Review", "model_disagreement_review"
        reason = (
            "The scorecard is bankable but the cross-domain proxy PD crossed its calibrated "
            "review threshold; an underwriter must resolve the disagreement."
        )
    else:
        decision, route = "Approved", "fast_track_eligible"
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
        "missing_data_sources": sorted(missing_data_sources),
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


# Descriptive labels only -- our own category names for the kind of signals
# banks commonly monitor under SMA/NPA early-warning frameworks (cheque/bill
# returns, GST filing lapses, turnover decline, leverage build-up). This is
# not a reproduction of any specific RBI circular text and carries no
# regulatory certification; it exists so an underwriter sees a recognisable
# monitoring theme alongside the pillar score, not just internal jargon.
EWS_TRIGGER_CATEGORIES = {
    "liquidity": "Cash-Flow Stability",
    "discipline": "Cheque Discipline & GST Filing",
    "momentum": "Turnover Momentum",
    "leverage": "Leverage / Debt-Servicing",
    "digital_footprint": "Digital Transaction Footprint",
}


def ews_style_signals(pillars: dict[str, int]) -> list[dict]:
    signals = []
    for pillar, value in pillars.items():
        if value >= 16:
            status = "Clear"
        elif value <= 8:
            status = "Flagged"
        else:
            status = "Monitor"
        signals.append({
            "status": status,
            "control": EWS_TRIGGER_CATEGORIES[pillar],
            "detail": f"{pillar.replace('_', ' ').title()} pillar: {value}/20.",
        })
    return signals


_NEXT_ACTION_BY_PILLAR = {
    "discipline": "Request the latest 3-month bank statement and confirm cheque-bounce reasons directly with the borrower.",
    "liquidity": "Request updated cash-flow projections and confirm the seasonal inflow pattern.",
    "leverage": "Request the current liability schedule and verify outstanding debt against inflow.",
    "momentum": "Request the latest GST returns to confirm the turnover trend is continuing.",
    "digital_footprint": "Confirm counterparty concentration is not a single-buyer dependency risk.",
}


def next_best_action(pillars: dict[str, int], policy: dict, traditional: dict) -> dict:
    """Deterministic, rule-based recommendation for the reviewing underwriter.

    Derived entirely from already-computed pillar and policy signals -- not a
    generative or LLM suggestion, so it is reproducible and auditable the same
    way the rest of the decision path is.
    """
    weakest_pillar = min(pillars, key=pillars.get)
    weakest_label = weakest_pillar.replace("_", " ")

    if policy.get("route") == "insufficient_data_review":
        return {
            "action": (
                f"Connect or manually verify: {', '.join(policy['missing_data_sources'])}. "
                "Do not approve or decline until the missing source is confirmed."
            ),
            "urgency": "high",
        }

    if policy["decision"] == "Rejected":
        return {"action": "Decline per policy; no further underwriter action required.", "urgency": "none"}

    if policy["decision"] == "Review" and policy.get("route") == "model_disagreement_review":
        return {
            "action": (
                f"Resolve the scorecard/model disagreement: re-verify the {weakest_label} "
                "inputs against source documents before sign-off."
            ),
            "urgency": "high",
        }

    if policy["decision"] == "Review":
        return {"action": _NEXT_ACTION_BY_PILLAR[weakest_pillar], "urgency": "medium"}

    if traditional["decision"] == "Rejected":
        return {
            "action": "Document the bureau-rejection reversal rationale in the credit file for the audit trail.",
            "urgency": "low",
        }

    return {
        "action": f"Approve per policy; monitor {weakest_label} at the next quarterly review.",
        "urgency": "low",
    }


def score_profile(
    p: MSMEProfile,
    record_audit: bool = True,
    *,
    missing_data_sources: frozenset[str] = frozenset(),
) -> dict:
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
        missing_data_sources=missing_data_sources,
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
        "ews_signals": ews_style_signals(pillars),
        "next_best_action": next_best_action(pillars, policy, traditional),
    }

    from agent_memo import generate_memo
    import audit_log

    result["ml"] = model_explanation
    result["pd_estimate"] = result["ml"].get("pd_estimate")
    result["memo"] = generate_memo(result)
    if record_audit:
        audit_log.record(result)
    return result
