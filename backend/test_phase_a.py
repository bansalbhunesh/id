"""Phase A product upgrades: GST-vs-bank divergence detection, EMI-capacity
indicative limit, favorable-only conduct prior, and vernacular reason codes."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from sample_data import SAMPLE_PROFILES
from scoring import (
    MSMEProfile,
    conduct_prior_adjustment,
    eligible_limit,
    limit_basis,
    score_profile,
)

client = TestClient(app)
UNDERWRITER_HEADERS = {"Authorization": "Bearer saakhscore-demo-underwriter-key"}


def _profile(**overrides) -> MSMEProfile:
    base = dict(
        name="Phase A Test Co",
        avg_monthly_inflow=400000,
        inflow_volatility=0.2,
        cheque_bounce_rate=0.02,
        gst_filing_streak_months=18,
        gst_turnover_growth_pct=10,
        upi_txn_count_monthly=150,
        unique_counterparties=30,
        outstanding_debt_to_inflow=0.2,
    )
    base.update(overrides)
    return MSMEProfile(**base)


# ------------------------------------------------------------- divergence ---

def test_divergence_guardrail_flags_declared_above_observed():
    result = score_profile(_profile(gst_bank_divergence_pct=38), record_audit=False)
    guardrail = next(g for g in result["policy_guardrails"]
                     if g["control"] == "GST-vs-bank turnover reconciliation")
    assert guardrail["status"] == "Review"
    assert "+38%" in guardrail["detail"]


def test_divergence_guardrail_passes_inside_band():
    result = score_profile(_profile(gst_bank_divergence_pct=-4), record_audit=False)
    guardrail = next(g for g in result["policy_guardrails"]
                     if g["control"] == "GST-vs-bank turnover reconciliation")
    assert guardrail["status"] == "Pass"


def test_divergence_absent_means_no_assertion_either_way():
    result = score_profile(_profile(), record_audit=False)
    assert not any(g["control"] == "GST-vs-bank turnover reconciliation"
                   for g in result["policy_guardrails"])


def test_material_divergence_drives_next_best_action():
    result = score_profile(_profile(gst_bank_divergence_pct=45), record_audit=False)
    action = result["next_best_action"]
    assert "Reconcile GST-declared turnover" in action["action"]
    assert action["urgency"] == "high"
    assert action["action_hi"]


def test_sandbox_payload_computes_divergence():
    now = datetime.now(timezone.utc)
    payload = {
        "profile": {"name": "Divergent Traders"},
        "account_aggregator": {"monthly_inflows": [100000, 100000, 100000],
                               "cheque_presentations": 10, "outstanding_debt": 20000},
        "gst": {"filing_streak_months": 12,
                "trailing_6m_turnover": [150000, 150000, 150000, 150000, 150000, 150000]},
        "upi": {"monthly_transaction_count": 80, "unique_counterparties": 15},
        "epfo": {"employees": 4},
        "consent": {"consent_id": "c-1", "purpose": "msme_underwriting",
                    "scope": ["account_aggregator", "gst", "upi", "epfo", "bureau"],
                    "granted_at": (now - timedelta(days=1)).isoformat(),
                    "expires_at": (now + timedelta(days=30)).isoformat()},
    }
    response = client.post("/sandbox/score", json=payload, headers=UNDERWRITER_HEADERS)
    assert response.status_code == 200
    body = response.json()
    guardrail = next(g for g in body["policy_guardrails"]
                     if g["control"] == "GST-vs-bank turnover reconciliation")
    # Declared 150k vs observed 100k = +50% divergence -> Review.
    assert guardrail["status"] == "Review"
    assert "+50%" in guardrail["detail"]


# ---------------------------------------------------------- economic limit --

def test_limit_is_grade_capped_for_healthy_low_debt_profiles():
    basis = limit_basis(86, SAMPLE_PROFILES["ntc_hero"])
    assert basis["binding_constraint"] == "grade_policy_cap"
    # The hero case keeps its documented Rs 27,00,000 indicative limit.
    assert basis["indicative_limit"] == 2700000.0


def test_limit_binds_on_debt_service_capacity_for_leveraged_profiles():
    heavy_debt = _profile(outstanding_debt_to_inflow=10, inflow_volatility=0.1)
    basis = limit_basis(85, heavy_debt)
    assert basis["binding_constraint"] == "debt_service_capacity"
    # The EMI-capacity limit must be strictly below the bare grade multiple.
    assert basis["indicative_limit"] < basis["grade_policy_cap"]


def test_limit_never_negative_even_when_existing_service_exceeds_capacity():
    drowning = _profile(outstanding_debt_to_inflow=50)
    assert eligible_limit(85, drowning) == 0.0


def test_limit_basis_ships_in_score_payload():
    result = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)
    assert result["limit_basis"]["indicative_limit"] == result["eligible_limit"]
    assert result["limit_basis"]["policy_inputs"]["tenor_months"] == 36


# ------------------------------------------------------------ conduct prior -

def test_strong_momentum_and_footprint_reduce_adjusted_pd():
    pillars = {"liquidity": 15, "discipline": 15, "momentum": 18,
               "leverage": 15, "digital_footprint": 20}
    prior = conduct_prior_adjustment(pillars, 0.20)
    assert prior["offset_logit"] < 0
    assert prior["pd_adjusted"] < prior["pd_model"]


def test_weak_footprint_never_inflates_pd():
    pillars = {"liquidity": 15, "discipline": 15, "momentum": 5,
               "leverage": 15, "digital_footprint": 2}
    prior = conduct_prior_adjustment(pillars, 0.20)
    assert prior["offset_logit"] == 0.0
    assert prior["pd_adjusted"] == prior["pd_model"]


def test_prior_offset_is_capped():
    pillars = {"liquidity": 15, "discipline": 15, "momentum": 20,
               "leverage": 15, "digital_footprint": 20}
    prior = conduct_prior_adjustment(pillars, 0.20)
    assert prior["offset_logit"] >= -prior["total_cap_logit"]


def test_prior_ships_in_ml_block_and_policy_uses_adjusted_pd():
    result = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)
    prior = result["ml"]["conduct_prior"]
    assert prior["asymmetry"].startswith("favorable_only")
    assert result["policy"]["pd_estimate"] == prior["pd_adjusted"]


# -------------------------------------------------------------- vernacular --

def test_reason_codes_ship_bilingual():
    result = score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)
    assert result["reasons_vernacular"], "expected at least one bilingual reason"
    for reason in result["reasons_vernacular"]:
        assert reason["en"] and reason["hi"]
    assert any("मज़बूत" in reason["hi"] or "निगरानी" in reason["hi"]
               for reason in result["reasons_vernacular"])


def test_improvement_plan_and_next_action_carry_hindi():
    result = score_profile(SAMPLE_PROFILES["borderline_improving"], record_audit=False)
    assert result["improvement_plan"]["action_hi"]
    assert result["next_best_action"]["action_hi"]
