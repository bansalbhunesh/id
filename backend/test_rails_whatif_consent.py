"""Contract tests for the OCEN output rail, the what-if lever, and the
visible consent contract -- the three judge-facing surfaces added on top of
the existing scoring pipeline. Everything asserted here is recomputed from
first principles (EMI amortisation, decision mapping) rather than snapshotted."""
import audit_log
from fastapi.testclient import TestClient

from feed_ingestion import ConsentRecord
from main import app
from rails import GRADE_RATE_SPREAD, OFFER_VALIDITY_DAYS
from sample_data import SAMPLE_PROFILES
from scoring import POLICY_ANNUAL_RATE, POLICY_TENOR_MONTHS

client = TestClient(app)

_STATUS_FOR = {
    "Approved": "OFFER_EXTENDED",
    "Review": "PENDING_MANUAL_REVIEW",
    "Rejected": "REJECTED",
}


def _emi(principal: float, annual_rate: float, months: int) -> float:
    monthly = annual_rate / 12
    return principal * monthly / (1 - (1 + monthly) ** -months)


def test_rails_registry_is_honest_about_every_rail():
    body = client.get("/rails").json()
    statuses = {r["rail"]: r["status"] for r in body["rails"]}
    # No rail may ever claim a production connection on this deployment.
    assert "connected" not in " ".join(statuses.values()).lower()
    assert statuses["ocen"] == "spec_aligned_output_artifact"
    assert statuses["uli"] == "adapter_design_only"
    assert statuses["account_aggregator"] == "simulated_ingestion_validated_schema"
    assert all(r["evidence"] for r in body["rails"])
    assert "honesty_note" in body


def test_ocen_offer_status_and_pricing_for_every_seeded_case():
    for msme_id in SAMPLE_PROFILES:
        score = client.get(f"/msmes/{msme_id}/score").json()
        offer = client.get(f"/rails/ocen/offer/{msme_id}")
        assert offer.status_code == 200, msme_id
        body = offer.json()
        assert body["status"] == _STATUS_FOR[score["alternate_data_decision"]], msme_id
        assert body["offer_validity_days"] == OFFER_VALIDITY_DAYS
        assert "not an IDBI sanction" in body["spec_alignment"]
        if body["status"] == "REJECTED":
            assert "terms" not in body
            assert body["rejection_reason"]
            continue
        terms = body["terms"]
        assert terms["principal_inr"] == score["eligible_limit"], msme_id
        expected_rate = POLICY_ANNUAL_RATE + GRADE_RATE_SPREAD[score["grade"]]
        assert terms["annual_interest_rate_pct"] == round(expected_rate * 100, 2)
        # The quoted EMI must amortise the quoted principal at the quoted
        # rate/tenor -- recomputed here, not trusted.
        assert abs(terms["emi_inr"] - _emi(terms["principal_inr"], expected_rate,
                                           POLICY_TENOR_MONTHS)) < 1.0, msme_id
        assert terms["tenure_months"] == POLICY_TENOR_MONTHS
        if body["status"] == "PENDING_MANUAL_REVIEW":
            assert body["review_reason"]
            assert "underwriter review" in terms["note"]


def test_ocen_offer_is_deterministic_and_side_effect_free():
    before = len(audit_log.read_recent(500))
    first = client.get("/rails/ocen/offer/ntc_hero").json()
    second = client.get("/rails/ocen/offer/ntc_hero").json()
    assert first == second  # replay-identical, including offer_id
    assert len(audit_log.read_recent(500)) == before


def test_ocen_offer_unknown_case_is_404():
    assert client.get("/rails/ocen/offer/nope").status_code == 404


def test_whatif_lever_moves_the_decision_honestly():
    # Give the hero a chronic bounce problem: the score must fall and the
    # baseline must equal the plain GET score for the same case.
    score = client.get("/msmes/ntc_hero/score").json()
    body = client.get(
        "/msmes/ntc_hero/whatif",
        params={"field": "cheque_bounce_rate", "value": 0.5},
    ).json()
    assert body["baseline"]["score"] == score["score"]
    assert body["baseline"]["decision"] == score["alternate_data_decision"]
    assert body["hypothetical"]["score"] < body["baseline"]["score"]
    assert body["delta"]["score"] == (
        body["hypothetical"]["score"] - body["baseline"]["score"])
    assert body["lever"]["label"]
    assert "no audit record" in body["note"]


def test_whatif_rejects_unknown_field_and_out_of_bounds_value():
    assert client.get(
        "/msmes/ntc_hero/whatif", params={"field": "name", "value": 1}
    ).status_code == 422
    # cheque_bounce_rate is bounded to [0, 1] by the same schema as the API.
    resp = client.get(
        "/msmes/ntc_hero/whatif",
        params={"field": "cheque_bounce_rate", "value": 2.0},
    )
    assert resp.status_code == 422
    assert "input schema" in resp.json()["detail"]


def test_whatif_is_side_effect_free_and_404s_unknown_case():
    before = len(audit_log.read_recent(500))
    ok = client.get(
        "/msmes/stressed_retailer/whatif",
        params={"field": "gst_filing_streak_months", "value": 36},
    )
    assert ok.status_code == 200
    assert len(audit_log.read_recent(500)) == before
    assert client.get(
        "/msmes/nope/whatif", params={"field": "cheque_bounce_rate", "value": 0}
    ).status_code == 404


def test_consent_contract_rules_are_present_and_sample_actually_validates():
    body = client.get("/consent/contract").json()
    rules = {r["rule"] for r in body["contract"]}
    assert {"Purpose-bound", "Time-limited", "Revocable", "Demo boundary"} <= rules
    assert all(r["trigger"] for r in body["contract"])
    # The advertised sample must satisfy the *real* enforcement model -- the
    # surface can never drift from what the sandbox route actually accepts.
    ConsentRecord.model_validate(body["sample_valid_consent"])
