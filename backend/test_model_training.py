import hashlib
import json
from pathlib import Path

from feature_bridge import msme_pillars_to_universal
from scoring import apply_decision_policy
from xgb_pd_model import XGBoostPDModel


ARTIFACT_DIR = Path(__file__).parent / "model_training" / "artifacts"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_evidence_hashes_match_artifacts():
    evaluation = json.loads((ARTIFACT_DIR / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["artifacts"]["champion_manifest_sha256"] == _sha256(
        ARTIFACT_DIR / "champion.json"
    )
    assert evaluation["artifacts"]["logistic_sha256"] == _sha256(
        ARTIFACT_DIR / "artifact.json"
    )
    assert evaluation["artifacts"]["xgboost_model_sha256"] == _sha256(
        ARTIFACT_DIR / "xgboost_model.json"
    )


def test_holdout_evidence_is_honest_and_has_uncertainty_and_fairness():
    evaluation = json.loads((ARTIFACT_DIR / "evaluation.json").read_text(encoding="utf-8"))
    assert "out_of_time" not in evaluation["splits"]
    assert "not an out-of-time" in evaluation["validation_design"]
    holdout_auc = evaluation["splits"]["holdout"]["auc"]
    interval = evaluation["holdout_confidence_intervals"]["auc"]
    assert interval["lower_95"] <= holdout_auc <= interval["upper_95"]
    assert set(evaluation["fairness"]["dimensions"]) == {"gender", "age_band"}
    assert evaluation["disclosed_gaps"]["out_of_time_validation"]


def test_domain_bridge_maps_strong_msm_e_conduct_to_no_adverse_conduct_state():
    bridged = msme_pillars_to_universal(
        {"discipline": 17, "leverage": 19, "liquidity": 16}
    )
    assert bridged == {"discipline": 1.0, "leverage": 0.95, "liquidity": 0.8}


def test_monotonic_xgboost_never_penalises_a_stronger_universal_feature():
    model = XGBoostPDModel.load(
        ARTIFACT_DIR / "xgboost_model.json",
        ARTIFACT_DIR / "xgboost_metadata.json",
    )
    base = {"discipline": 0.5, "leverage": 0.5, "liquidity": 0.5}
    base_pd = model.predict_proba(base)
    for feature in base:
        improved = dict(base)
        improved[feature] = 0.9
        assert model.predict_proba(improved) <= base_pd


def test_policy_uses_proxy_pd_only_as_a_human_review_guardrail():
    review = apply_decision_policy("B", pd_estimate=0.35, pd_threshold=0.25)
    assert review["decision"] == "Review"
    assert review["route"] == "model_disagreement_review"
    assert review["auto_decline_from_proxy_model"] is False

    approved = apply_decision_policy("B", pd_estimate=0.10, pd_threshold=0.25)
    assert approved["decision"] == "Approved"

    declined = apply_decision_policy("D", pd_estimate=0.05, pd_threshold=0.25)
    assert declined["decision"] == "Rejected"
