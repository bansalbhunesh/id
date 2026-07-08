"""Rule-based MSME financial health scoring engine.

Five pillars, each 0-20, summed to a 0-100 score with an A-E grade.
Deliberately simple and dependency-free for the first working version;
an ML model (XGBoost + SHAP) replaces the pillar weights in a later phase
without changing this module's public interface.
"""
from pydantic import BaseModel


class MSMEProfile(BaseModel):
    name: str
    avg_monthly_inflow: float
    inflow_volatility: float  # coefficient of variation, 0-1+
    cheque_bounce_rate: float  # 0-1
    gst_filing_streak_months: int
    gst_turnover_growth_pct: float  # trailing 6mo, can be negative
    upi_txn_count_monthly: int
    unique_counterparties: int
    outstanding_debt_to_inflow: float  # ratio
    has_bureau_history: bool = True  # False = New-to-Credit / New-to-Bank


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


def score_profile(p: MSMEProfile) -> dict:
    pillars = {
        "liquidity": score_liquidity(p),
        "discipline": score_discipline(p),
        "momentum": score_momentum(p),
        "leverage": score_leverage(p),
        "digital_footprint": score_digital_footprint(p),
    }
    total = sum(pillars.values())
    grade = grade_for(total)
    result = {
        "name": p.name,
        "score": total,
        "grade": grade,
        "pillars": pillars,
        "eligible_limit": eligible_limit(total, p),
        "reasons": reason_codes(pillars),
        "traditional": traditional_verdict(p),
        "alternate_data_decision": "Approved" if grade in ("A", "B", "C") else "Rejected",
        "improvement_plan": improvement_plan(pillars, p),
    }

    from ml import explain  # local imports: avoid circular imports at module load
    from agent_memo import generate_memo
    import audit_log

    result["ml"] = explain(p)
    result["memo"] = generate_memo(result)
    audit_log.record(result)
    return result
