"""Contract tests for the multi-lever sensitivity endpoint and the stress
battery. Both are views over the identical scoring pipeline: hypotheticals
are recomputed here from first principles (direct pipeline runs on mutated
profiles), shocks must stay inside the schema clamp bounds, and neither
route may ever append an audit event."""
import audit_log
from fastapi.testclient import TestClient

from main import app
from sample_data import SAMPLE_PROFILES
from scoring import MSMEProfile, score_profile
from whatif import FIELD_BOUNDS, MAX_LEVERS, STRESS_SCENARIOS

client = TestClient(app)


def _direct(msme_id: str, overrides: dict) -> dict:
    payload = SAMPLE_PROFILES[msme_id].model_dump()
    payload.update(overrides)
    return score_profile(MSMEProfile.model_validate(payload), record_audit=False)


def test_multi_lever_matches_a_direct_pipeline_run():
    body = client.get(
        "/msmes/ntc_hero/whatif/multi",
        params={"levers": "cheque_bounce_rate:0.4,gst_filing_streak_months:6"},
    ).json()
    direct = _direct("ntc_hero",
                     {"cheque_bounce_rate": 0.4, "gst_filing_streak_months": 6})
    assert body["hypothetical"]["score"] == direct["score"]
    assert body["hypothetical"]["grade"] == direct["grade"]
    assert body["hypothetical"]["eligible_limit"] == direct["eligible_limit"]
    assert body["delta"]["score"] == (
        body["hypothetical"]["score"] - body["baseline"]["score"])
    assert {lever["field"] for lever in body["levers"]} == {
        "cheque_bounce_rate", "gst_filing_streak_months"}
    # Baseline must equal the plain GET score for the same case.
    score = client.get("/msmes/ntc_hero/score").json()
    assert body["baseline"]["score"] == score["score"]
    assert "no audit record" in body["note"]


def test_multi_lever_interactions_are_one_joint_run_not_a_sum():
    # A combined run must equal the jointly mutated profile even when the
    # two levers interact (both hit conduct-adjacent pillars).
    combined = client.get(
        "/msmes/stressed_retailer/whatif/multi",
        params={"levers": "gst_filing_streak_months:36,cheque_bounce_rate:0.0"},
    ).json()
    direct = _direct("stressed_retailer",
                     {"gst_filing_streak_months": 36, "cheque_bounce_rate": 0.0})
    assert combined["hypothetical"]["score"] == direct["score"]
    assert combined["hypothetical"]["decision"] == direct["alternate_data_decision"]


def test_multi_lever_validation_contract():
    def status(levers: str) -> int:
        return client.get("/msmes/ntc_hero/whatif/multi",
                          params={"levers": levers}).status_code

    assert status("name:1") == 422                       # not whitelisted
    assert status("cheque_bounce_rate") == 422           # malformed pair
    assert status("cheque_bounce_rate:abc") == 422       # not a number
    assert status("") == 422                             # empty
    assert status(
        "cheque_bounce_rate:0.1,cheque_bounce_rate:0.2") == 422  # duplicate
    too_many = ",".join(
        f"{field}:1" for field in list(FIELD_BOUNDS)[: MAX_LEVERS + 1])
    assert status(too_many) == 422                       # over the lever cap
    schema_reject = client.get(
        "/msmes/ntc_hero/whatif/multi",
        params={"levers": "cheque_bounce_rate:2.0"})
    assert schema_reject.status_code == 422
    assert "input schema" in schema_reject.json()["detail"]
    assert client.get(
        "/msmes/nope/whatif/multi",
        params={"levers": "cheque_bounce_rate:0.1"}).status_code == 404


def test_stress_battery_is_clamped_adverse_and_side_effect_free():
    before = len(audit_log.read_recent(500))
    body = client.get("/msmes/ntc_hero/stress").json()
    assert len(audit_log.read_recent(500)) == before
    assert {s["id"] for s in body["scenarios"]} == set(STRESS_SCENARIOS)
    score = client.get("/msmes/ntc_hero/score").json()
    assert body["baseline"]["score"] == score["score"]
    for scenario in body["scenarios"]:
        assert scenario["applied"], scenario["id"]
        for shock in scenario["applied"]:
            lo, hi = FIELD_BOUNDS[shock["field"]]
            assert lo <= shock["to"] <= hi, shock
        assert scenario["delta"]["score"] == (
            scenario["result"]["score"] - body["baseline"]["score"])
        # Shocks are adverse by construction: stress can never raise a score.
        assert scenario["delta"]["score"] <= 0, scenario["id"]
        assert scenario["delta"]["decision_changed"] == (
            scenario["result"]["decision"] != body["baseline"]["decision"])
    verdict = body["verdict"]
    assert verdict["scenarios_run"] == len(STRESS_SCENARIOS)
    assert (set(verdict["decision_holds_under"])
            | set(verdict["decision_breaks_under"])) == {
        s["label"] for s in body["scenarios"]}


def test_stress_scenario_matches_a_direct_pipeline_run():
    body = client.get("/msmes/stressed_retailer/stress").json()
    scenario = next(s for s in body["scenarios"] if s["id"] == "conduct_slip")
    direct = _direct("stressed_retailer",
                     {shock["field"]: shock["to"] for shock in scenario["applied"]})
    assert scenario["result"]["score"] == direct["score"]
    assert scenario["result"]["grade"] == direct["grade"]
    assert scenario["result"]["eligible_limit"] == direct["eligible_limit"]


def test_stress_skips_unknown_concentration_instead_of_inventing_it():
    # For any case with top_counterparty_share_pct == 0 ("not supplied"),
    # leverage creep must not conjure a counterparty share out of nothing.
    for msme_id, profile in SAMPLE_PROFILES.items():
        if profile.top_counterparty_share_pct:
            continue
        body = client.get(f"/msmes/{msme_id}/stress").json()
        creep = next(s for s in body["scenarios"] if s["id"] == "leverage_creep")
        assert all(shock["field"] != "top_counterparty_share_pct"
                   for shock in creep["applied"]), msme_id


def test_stress_covers_every_seeded_case_and_404s_unknown():
    for msme_id in SAMPLE_PROFILES:
        assert client.get(f"/msmes/{msme_id}/stress").status_code == 200, msme_id
    assert client.get("/msmes/nope/stress").status_code == 404


def test_portfolio_cases_carry_pd_for_the_risk_map():
    cases = client.get("/portfolio").json()["cases"]
    assert cases
    assert all("pd_estimate" in case for case in cases)
