"""Pilot KPI calculations for the Stage 2 IDBI sandbox rollout."""


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
        "ntc_ntb_approval_lift_pct": round(approval_lift, 1),
        "decision_time_reduction_pct": round(decision_time_reduction, 1),
        "early_npa_guardrail": {
            "status": "Pilot metric",
            "definition": "Track 30/60/90 DPD by score band and policy-watch reason; pause auto-approval if early delinquency breaches IDBI threshold.",
        },
        "portfolio_diversification": {
            "approved_sector_count": len(sectors),
            "approved_district_count": len(districts),
            "approved_sectors": sorted(sectors),
            "approved_districts": sorted(districts),
        },
    }
