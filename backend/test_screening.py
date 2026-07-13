"""The screening surface must be honest about its sample data and must
route hits the governed way: exact-ID -> forced human review, name-only ->
advisory, and never an automated decline."""
from fastapi.testclient import TestClient

from main import app
from screening import SAMPLE_REGISTRY

client = TestClient(app)


def test_clear_applicant_has_no_registry_objection():
    body = client.get(
        "/screening/check", params={"name": "Shree Ganesh Textiles"}
    ).json()
    assert body["routing_advice"] == "no_registry_objection"
    assert body["hits"] == []
    assert body["sample_data_only"] is True
    assert "advisory" in body["truth_boundary"]


def test_exact_id_hit_forces_review_never_decline():
    sample_gstin = next(
        r["id_value"] for r in SAMPLE_REGISTRY if r["id_type"] == "gstin")
    body = client.get(
        "/screening/check",
        params={"name": "Any Business", "gstin": sample_gstin.lower()},
    ).json()
    assert body["routing_advice"] == "mandatory_human_review"
    assert body["hits"][0]["match_kind"] == "exact_id"
    assert body["hits"][0]["is_sample"] is True
    assert "not allowed" in body["rationale"]  # the no-auto-decline stance


def test_name_only_hit_is_advisory_because_names_collide():
    sample_name = next(
        r["id_value"] for r in SAMPLE_REGISTRY if r["id_type"] == "name")
    body = client.get(
        "/screening/check", params={"name": sample_name}
    ).json()
    assert body["routing_advice"] == "advisory_manual_disposition"
    assert body["hits"][0]["match_kind"] == "name_only"
    assert "never gates" in body["rationale"]


def test_screening_validates_input_lengths():
    assert client.get("/screening/check").status_code == 422  # name required
    assert client.get(
        "/screening/check", params={"name": "x", "gstin": "y" * 16}
    ).status_code == 422
