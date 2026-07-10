"""Pilot KPI *targets* for the Stage 2 IDBI sandbox rollout.

Every number here is computed from the public synthetic cohort (currently
5-10 sample profiles) and a stated assumption (`decision_time_minutes`,
`manual_baseline_days` in portfolio.py), not from observed pilot volume or
measured decision times. The audit's own finding: "This demonstrates
product logic, not approval lift, decision-time reduction or early-NPA
performance." Every field below is tagged `status: "pilot_target"` with its
formula and the minimum sample size a real claim would need, so nothing
here can be read as an achieved result.
"""

MIN_SAMPLE_FOR_MEASURED_CLAIM = 200  # illustrative minimum for a defensible measured KPI


def build_pilot_metrics(portfolio: dict) -> dict:
    summary = portfolio["summary"]
    cases = portfolio["cases"]
    traditional_approvals = summary["traditional_approvals"]
    alternate_approvals = summary["alternate_data_approvals"]
    total_cases = max(summary["cases"], 1)
    approval_lift = (alternate_approvals - traditional_approvals) / total_cases * 100
    decision_time_reduction = (
        1 - summary["decision_time_minutes"] / (summary["manual_baseline_days"] * 24 * 60)
    ) * 100
    decision_time_reduction = min(decision_time_reduction, 99.9)
    approved_cases = [case for case in cases if case["alternate_data_decision"] == "Approved"]
    sectors = {case["sector"] for case in approved_cases}
    districts = {case["district"] for case in approved_cases}

    return {
        "ntc_ntb_approval_lift_pct": {
            "status": "pilot_target",
            "value": round(approval_lift, 1),
            "formula": "(alternate_data_approvals - traditional_approvals) / total_cases * 100, on the public synthetic cohort.",
            "sample_size": total_cases,
            "caveat": f"Not a measured lift. A defensible measured claim needs >= {MIN_SAMPLE_FOR_MEASURED_CLAIM} real sandbox decisions.",
        },
        "decision_time_reduction_pct": {
            "status": "pilot_target",
            "value": round(decision_time_reduction, 1),
            "formula": "1 - (assumed_automated_minutes / assumed_manual_baseline_days*24*60) * 100.",
            "assumptions": {
                "assumed_automated_minutes": summary["decision_time_minutes"],
                "assumed_manual_baseline_days": summary["manual_baseline_days"],
            },
            "caveat": "Both inputs are stated assumptions, not timed observations of any real underwriting process.",
        },
        "early_npa_guardrail": {
            "status": "pilot_target",
            "definition": "Track 30/60/90 DPD by score band and policy-watch reason; pause auto-approval if early delinquency breaches IDBI threshold.",
            "caveat": "No delinquency data exists yet; this is a monitoring plan, not an observed guardrail trigger.",
        },
        "portfolio_diversification": {
            "status": "pilot_target",
            "approved_sector_count": len(sectors),
            "approved_district_count": len(districts),
            "approved_sectors": sorted(sectors),
            "approved_districts": sorted(districts),
            "caveat": f"Computed over {total_cases} synthetic cases, not a real approved-portfolio sample.",
        },
    }
