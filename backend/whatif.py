"""Single-lever what-if re-scoring on the seeded demo cases.

An underwriter's first question after a verdict is "what would it take?".
This answers it honestly: take a seeded case, override exactly one
whitelisted signal, run the identical scoring pipeline, and show both
decisions side by side. One lever, not a payload editor -- arbitrary
multi-field scoring stays behind the authenticated POST routes, and the
override is validated by the same bounded MSMEProfile schema as any other
input, so the simulator cannot reach states the API itself would reject.
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
}


def _decision_view(result: dict) -> dict:
    return {
        "score": result["score"],
        "grade": result["grade"],
        "decision": result["alternate_data_decision"],
        "policy_route": result["policy"]["route"],
        "eligible_limit": result["eligible_limit"],
        "pd_estimate": result.get("pd_estimate"),
    }


def run_whatif(profile: MSMEProfile, field: str, value: float) -> dict:
    """Re-score `profile` with one whitelisted field overridden.

    Both runs are views (record_audit=False): a hypothetical is not a
    lending decision and must never append audit events.
    """
    if field not in WHATIF_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"field must be one of: {', '.join(sorted(WHATIF_FIELDS))}",
        )
    baseline = score_profile(profile, record_audit=False)
    payload = profile.model_dump()
    original_value = payload[field]
    payload[field] = value
    try:
        mutated = MSMEProfile.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(
            status_code=422,
            detail=f"override rejected by the input schema: {field}: {first['msg']}",
        ) from exc
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
        "note": (
            "Hypothetical view on seeded demo data; identical pipeline and "
            "bounds as the real scoring routes, no audit record is written."
        ),
    }
