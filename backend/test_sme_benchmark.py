"""Real small-business benchmark suite: v2 champion + v1 baseline serving,
integrity, leakage exclusions, and honesty framing."""
from fastapi.testclient import TestClient

from main import app
from sme_benchmark import artifact_integrity, sme_benchmark, sme_benchmark_summary

client = TestClient(app)


def test_sme_benchmark_endpoint_serves_v2_champion_with_v1_baseline():
    response = client.get("/model/sme-benchmark")
    assert response.status_code == 200
    body = response.json()
    assert body["evidence_type"] == "real_small_business_outcome_benchmarks"
    assert body["champion_version"] == "v2"

    champion = body["champion"]
    # Natural-base-rate, temporally-split real-loan evidence.
    assert champion["evidence_type"] == "real_loan_level_temporal_benchmark"
    assert champion["dataset"]["oot_rows"] > 100_000
    assert champion["splits"]["holdout"]["auc"] > 0.9
    assert champion["splits"]["oot"]["auc"] > 0.9
    assert champion["splits"]["stress"]["auc"] > 0.85
    # Operating-point evidence a lender can act on.
    approve30 = champion["splits"]["oot"]["operating_points"]["approve_30pct"]
    assert approve30["bad_rate_in_approved_book"] < approve30["vs_population_bad_rate"]
    # Risk bands must rank-order within binomial noise for a usable scorecard
    # (strict flag is also reported; holdout and stress are strictly monotone).
    assert champion["splits"]["oot"]["risk_bands"]["monotone_within_noise"] is True
    assert champion["splits"]["holdout"]["risk_bands"]["monotone"] is True
    assert champion["splits"]["stress"]["risk_bands"]["monotone"] is True

    # The old benchmark stays committed as the baseline.
    baseline = body["baseline_v1"]
    assert baseline["evidence_type"] == "real_small_business_outcome_benchmark"
    assert baseline["out_of_distribution"]["auc"] > 0.6


def test_sme_benchmark_artifact_integrity_passes_for_both_models():
    integrity = artifact_integrity()
    assert integrity["status"] == "pass"
    assert integrity["v1_baseline"]["status"] == "pass"
    assert integrity["v2_champion"]["status"] == "pass"


def test_v2_champion_excludes_leakage_features():
    champion = sme_benchmark()["champion"]
    for leak in ("ChargeoffDate", "GrossChargeoffAmount", "PaidinFullDate", "LoanStatus",
                 "initial_interest_rate", "label", "Selected"):
        assert leak not in champion["features"]


def test_v2_champion_declares_honesty_boundary_and_selection_gates():
    champion = sme_benchmark()["champion"]
    assert champion["honesty_boundary"]["domain"].startswith("US small business")
    assert "censoring" in champion["honesty_boundary"]
    # Pre-registered anti-complexity gate is recorded with the decision.
    assert champion["bag_complexity_gate"]["applied"] is False
    # Baseline comparisons are DeLong-tested, not eyeballed.
    assert champion["baseline_comparison_oot"]["v1_recipe_blanket_monotone"]["delong_vs_v2"]["significant_5pct"] is True


def test_v2_served_treeshap_is_exact():
    champion = sme_benchmark()["champion"]
    assert champion["explainability"]["served_reconstruction_error_logit"] < 1e-4


def test_summary_headline_reports_champion_and_baseline():
    summary = sme_benchmark_summary()
    assert summary["champion_version"] == "v2"
    assert summary["oot_auc"] is not None
    assert summary["stress_auc"] is not None
    assert summary["v1_baseline"]["holdout_auc"] is not None


def test_submission_proof_includes_real_outcome_benchmark():
    body = client.get("/submission/proof").json()
    benchmark = body["real_outcome_benchmark"]
    assert benchmark is not None
    assert benchmark["champion_version"] == "v2"
    proofs = {item["proof"] for item in body["competitor_gap_map"]}
    assert "/model/sme-benchmark" in proofs
