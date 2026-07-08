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


def test_reasons_present_for_every_profile():
    for profile in SAMPLE_PROFILES.values():
        result = score_profile(profile)
        assert isinstance(result["reasons"], list)
        assert "score" in result and 0 <= result["score"] <= 100
