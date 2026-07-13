"""What-if re-scoring on the seeded demo cases: single lever, multi-lever
sensitivity, and a fixed adverse stress battery.

An underwriter's first question after a verdict is "what would it take?".
This answers it honestly: take a seeded case, override whitelisted signals,
run the identical scoring pipeline, and show both decisions side by side.
Bounded levers, not a payload editor -- arbitrary multi-field scoring stays
behind the authenticated POST routes, and every override is validated by the
same bounded MSMEProfile schema as any other input, so the simulator cannot
reach states the API itself would reject. Every run here is a *view*
(record_audit=False): hypotheticals are not lending decisions and must never
append audit events.
"""
from fastapi import HTTPException
from pydantic import ValidationError

from scoring import MSMEProfile, score_profile

# Levers an underwriter can plausibly coach a borrower on (or stress),
# with the register labels the frontend already uses.
WHATIF_FIELDS = {
    "gst_filing_streak_months": "GST filing streak (months)",
    "inflow_volatility": "Inflow volatility (coefficient of variation)",
    "cheque_bounce_rate": "Cheque bounce rate (0-1)",
    "upi_txn_count_monthly": "Monthly UPI transactions",
    "outstanding_debt_to_inflow": "Outstanding debt to inflow ratio",
    "top_counterparty_share_pct": "Top counterparty share of inflow (%)",
    "gst_bank_divergence_pct": "GST-vs-bank turnover divergence (%)",
    "gst_turnover_growth_pct": "GST turnover growth, trailing 6mo (%)",
}

MAX_LEVERS = 4

# Clamp range per lever field, mirroring the MSMEProfile schema constraints.
# Stress shocks are clamped here BEFORE validation so a shocked value can
# never leave the legal input space (e.g. bounce rate 0.95 + 0.10 -> 1.0).
FIELD_BOUNDS = {
    "gst_filing_streak_months": (0, 120),
    "inflow_volatility": (0, 100),
    "cheque_bounce_rate": (0, 1),
    "upi_txn_count_monthly": (0, 10_000_000),
    "outstanding_debt_to_inflow": (0, 1_000_000),
    "top_counterparty_share_pct": (0, 100),
    "gst_bank_divergence_pct": (-100, 10_000),
    "gst_turnover_growth_pct": (-100, 100_000),
}
INT_FIELDS = {"gst_filing_streak_months", "upi_txn_count_monthly"}

# Fixed adverse scenarios. Shocks are relative ("mul") or absolute ("add")
# against the case's own current value, then clamped to FIELD_BOUNDS. The
# concentration shock is skipped when the signal is not supplied (0 means
# "not supplied" in the schema): inventing a counterparty share would turn
# an unknown into information and could *improve* the routing.
STRESS_SCENARIOS = {
    "demand_shock": {
        "label": "Demand shock",
        "narrative": (
            "Order book thins: cash-flow volatility rises half again, UPI "
            "velocity drops 30%, trailing GST growth loses 15 points."
        ),
        "shocks": [
            ("inflow_volatility", "mul", 1.5),
            ("upi_txn_count_monthly", "mul", 0.7),
            ("gst_turnover_growth_pct", "add", -15.0),
        ],
    },
    "conduct_slip": {
        "label": "Conduct slip",
        "narrative": (
            "Discipline slips: the cheque bounce rate rises 10 points and "
            "the GST filing streak halves."
        ),
        "shocks": [
            ("cheque_bounce_rate", "add", 0.10),
            ("gst_filing_streak_months", "mul", 0.5),
        ],
    },
    "leverage_creep": {
        "label": "Leverage creep",
        "narrative": (
            "The balance sheet stretches: debt-to-inflow rises 0.25 and the "
            "top buyer takes 15 more points of revenue share (skipped when "
            "concentration is not supplied)."
        ),
        "shocks": [
            ("outstanding_debt_to_inflow", "add", 0.25),
            ("top_counterparty_share_pct", "add", 15.0),
        ],
    },
}

_VIEW_NOTE = (
    "Hypothetical view on seeded demo data; identical pipeline and "
    "bounds as the real scoring routes, no audit record is written."
)


def _decision_view(result: dict) -> dict:
    return {
        "score": result["score"],
        "grade": result["grade"],
        "decision": result["alternate_data_decision"],
        "policy_route": result["policy"]["route"],
        "eligible_limit": result["eligible_limit"],
        "pd_estimate": result.get("pd_estimate"),
    }


def _validated(payload: dict, context: str) -> MSMEProfile:
    try:
        return MSMEProfile.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(
            status_code=422,
            detail=f"override rejected by the input schema: {context}: {first['msg']}",
        ) from exc


def parse_levers(raw: str) -> list[tuple[str, float]]:
    """Parse "field:value,field:value" into validated (field, value) pairs."""
    pairs: list[tuple[str, float]] = []
    seen: set[str] = set()
    for chunk in [c for c in raw.split(",") if c.strip()]:
        field, sep, value_text = chunk.partition(":")
        field = field.strip()
        if not sep or not value_text.strip():
            raise HTTPException(
                status_code=422,
                detail=f"malformed lever '{chunk.strip()}'; expected field:value",
            )
        if field not in WHATIF_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=f"field must be one of: {', '.join(sorted(WHATIF_FIELDS))}",
            )
        if field in seen:
            raise HTTPException(status_code=422, detail=f"duplicate lever: {field}")
        try:
            value = float(value_text)
        except ValueError:
            raise HTTPException(
                status_code=422, detail=f"lever value for {field} is not a number"
            ) from None
        seen.add(field)
        pairs.append((field, value))
    if not pairs:
        raise HTTPException(status_code=422, detail="no levers supplied")
    if len(pairs) > MAX_LEVERS:
        raise HTTPException(
            status_code=422, detail=f"at most {MAX_LEVERS} levers per hypothetical"
        )
    return pairs


def run_whatif(profile: MSMEProfile, field: str, value: float) -> dict:
    """Re-score `profile` with one whitelisted field overridden."""
    if field not in WHATIF_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"field must be one of: {', '.join(sorted(WHATIF_FIELDS))}",
        )
    baseline = score_profile(profile, record_audit=False)
    payload = profile.model_dump()
    original_value = payload[field]
    payload[field] = value
    mutated = _validated(payload, field)
    hypothetical = score_profile(mutated, record_audit=False)
    return {
        "case": profile.name,
        "lever": {"field": field, "label": WHATIF_FIELDS[field],
                  "from": original_value, "to": payload[field]},
        "baseline": _decision_view(baseline),
        "hypothetical": _decision_view(hypothetical),
        "delta": {
            "score": hypothetical["score"] - baseline["score"],
            "eligible_limit": round(
                hypothetical["eligible_limit"] - baseline["eligible_limit"], 2),
            "decision_changed": (
                hypothetical["alternate_data_decision"]
                != baseline["alternate_data_decision"]),
        },
        "note": _VIEW_NOTE,
    }


def run_whatif_multi(profile: MSMEProfile, levers: list[tuple[str, float]]) -> dict:
    """Re-score `profile` with several whitelisted fields overridden at once.

    The combined hypothetical is one pipeline run over the jointly mutated
    profile -- interactions between levers are real, not summed single-lever
    deltas.
    """
    baseline = score_profile(profile, record_audit=False)
    payload = profile.model_dump()
    register = []
    for field, value in levers:
        register.append({
            "field": field, "label": WHATIF_FIELDS[field],
            "from": payload[field], "to": value,
        })
        payload[field] = value
    mutated = _validated(payload, ", ".join(f for f, _ in levers))
    hypothetical = score_profile(mutated, record_audit=False)
    return {
        "case": profile.name,
        "levers": register,
        "baseline": _decision_view(baseline),
        "hypothetical": _decision_view(hypothetical),
        "delta": {
            "score": hypothetical["score"] - baseline["score"],
            "eligible_limit": round(
                hypothetical["eligible_limit"] - baseline["eligible_limit"], 2),
            "decision_changed": (
                hypothetical["alternate_data_decision"]
                != baseline["alternate_data_decision"]),
            "grade_changed": hypothetical["grade"] != baseline["grade"],
        },
        "note": _VIEW_NOTE,
    }


def _shocked(current: float, op: str, magnitude: float, field: str) -> float | int:
    value = current * magnitude if op == "mul" else current + magnitude
    lo, hi = FIELD_BOUNDS[field]
    value = min(max(value, lo), hi)
    if field in INT_FIELDS:
        value = int(round(value))
    return value


def run_stress(profile: MSMEProfile) -> dict:
    """Run every fixed adverse scenario against one seeded case."""
    baseline_full = score_profile(profile, record_audit=False)
    baseline = _decision_view(baseline_full)
    scenarios = []
    for scenario_id, spec in STRESS_SCENARIOS.items():
        payload = profile.model_dump()
        applied = []
        for field, op, magnitude in spec["shocks"]:
            current = payload[field]
            if field == "top_counterparty_share_pct" and not current:
                continue  # unknown concentration stays unknown
            if current is None:
                continue  # optional signal not supplied for this case
            shocked = _shocked(current, op, magnitude, field)
            applied.append({
                "field": field, "label": WHATIF_FIELDS[field],
                "from": current, "to": shocked,
            })
            payload[field] = shocked
        stressed_full = score_profile(_validated(payload, scenario_id),
                                      record_audit=False)
        view = _decision_view(stressed_full)
        scenarios.append({
            "id": scenario_id,
            "label": spec["label"],
            "narrative": spec["narrative"],
            "applied": applied,
            "result": view,
            "delta": {
                "score": view["score"] - baseline["score"],
                "eligible_limit": round(
                    view["eligible_limit"] - baseline["eligible_limit"], 2),
                "decision_changed": view["decision"] != baseline["decision"],
                "grade_changed": view["grade"] != baseline["grade"],
            },
        })
    holds = [s["label"] for s in scenarios if not s["delta"]["decision_changed"]]
    breaks = [s["label"] for s in scenarios if s["delta"]["decision_changed"]]
    return {
        "case": profile.name,
        "baseline": baseline,
        "scenarios": scenarios,
        "verdict": {
            "scenarios_run": len(scenarios),
            "decision_holds_under": holds,
            "decision_breaks_under": breaks,
        },
        "note": _VIEW_NOTE,
    }
