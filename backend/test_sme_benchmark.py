"""Real SBA small-business outcome benchmark: endpoint, integrity, and honesty.

These lock in the domination claim: real outcomes + out-of-distribution
validation + exact TreeSHAP, without silently overclaiming.
"""
from fastapi.testclient import TestClient

from main import app
from sme_benchmark import artifact_integrity, sme_benchmark, sme_benchmark_summary

client = TestClient(app)


def test_sme_benchmark_endpoint_returns_real_outcome_evidence():
    response = client.get("/model/sme-benchmark")
    assert response.status_code == 200
    body = response.json()
    assert body["evidence_type"] == "real_small_business_outcome_benchmark"
    # Real holdout discrimination on real SBA charge-offs.
    assert body["holdout"]["auc"] > 0.6
    # Out-of-distribution generalisation is reported over a genuine shift.
    assert body["out_of_distribution"]["auc"] > 0.6
    assert body["out_of_distribution"]["psi_holdout_vs_shift"] > 0.1
    # Native TreeSHAP is exact (additive) in logit space.
    assert body["explainability"]["max_reconstruction_error_logit"] < 1e-3


def test_sme_benchmark_artifact_integrity_passes():
    assert artifact_integrity()["status"] == "pass"


def test_sme_benchmark_declares_honesty_caveats():
    body = sme_benchmark()
    assert "caveats" in body and len(body["caveats"]) >= 2
    assert body["honesty_boundary"]["domain"].startswith("US small business")
    assert body["dataset"]["train_rows"] > 0 and body["dataset"]["shift_rows"] > 0


def test_sme_benchmark_excludes_leakage_features():
    # The model must not consume post-outcome leakage columns.
    body = sme_benchmark()
    for leak in ("ChgOffPrinGr", "Selected", "label"):
        assert leak not in body["features"]


def test_sme_benchmark_summary_headline():
    summary = sme_benchmark_summary()
    assert summary["holdout_auc"] is not None
    assert summary["out_of_distribution_auc"] is not None


def test_submission_proof_includes_real_outcome_benchmark():
    body = client.get("/submission/proof").json()
    assert body["real_outcome_benchmark"] is not None
    assert body["real_outcome_benchmark"]["evidence_type"] == "real_small_business_outcome_benchmark"
    proofs = {item["proof"] for item in body["competitor_gap_map"]}
    assert "/model/sme-benchmark" in proofs
