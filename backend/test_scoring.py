from sample_data import SAMPLE_PROFILES
from scoring import grade_for, score_profile


def test_ntc_hero_scores_well_despite_no_credit_history():
    result = score_profile(SAMPLE_PROFILES["ntc_hero"])
    assert result["grade"] in ("A", "B")
    assert result["eligible_limit"] > 0


def test_stressed_retailer_scores_poorly():
    result = score_profile(SAMPLE_PROFILES["stressed_retailer"])
    assert result["grade"] in ("D", "E")


def test_grade_boundaries():
    assert grade_for(85) == "A"
    assert grade_for(70) == "B"
    assert grade_for(55) == "C"
    assert grade_for(40) == "D"
    assert grade_for(10) == "E"


def test_ntc_hero_rejected_traditionally_but_approved_on_alternate_data():
    result = score_profile(SAMPLE_PROFILES["ntc_hero"])
    assert result["traditional"]["decision"] == "Rejected"
    assert result["alternate_data_decision"] == "Approved"


def test_reasons_present_for_every_profile():
    for profile in SAMPLE_PROFILES.values():
        result = score_profile(profile)
        assert isinstance(result["reasons"], list)
        assert "score" in result and 0 <= result["score"] <= 100


def test_improvement_plan_present_for_non_a_grades_and_raises_limit():
    for profile in SAMPLE_PROFILES.values():
        result = score_profile(profile)
        plan = result["improvement_plan"]
        if result["grade"] == "A":
            assert plan is None
        else:
            assert plan is not None
            assert plan["limit_increase"] >= 0
            assert plan["focus_pillar"] in result["pillars"]


def test_memo_mentions_rejection_reversal_for_ntc_hero():
    result = score_profile(SAMPLE_PROFILES["ntc_hero"])
    assert "decline" in result["memo"].lower() or "reject" in result["memo"].lower()
    assert result["name"] in result["memo"]
