"""Runtime access to the real small-business default benchmarks.

Two committed, hash-verified evidence artifacts:

- **v2 champion** (`sme_evaluation_v2.json`): trained on 418k resolved real
  SBA 7(a) FOIA loans at natural base rates, validated on a genuinely
  later-in-time FY2017-19 out-of-time window and a FY2005-07 recession stress
  cohort, with selective monotonicity, exact TreeSHAP, operating-point
  analysis, bootstrap CIs and a pre-registered complexity gate. Produced by
  `model_training/train_sme_pd_model_v2.py` from the registry-tracked
  experiment programme in `model_training/experiments/`.
- **v1 baseline** (`sme_evaluation.json`): the earlier 943-loan balanced
  case-sample benchmark with an out-of-distribution shift test. Kept committed
  so the improvement is itself verifiable.

This is real-outcome methodology evidence for the exact serving stack
(monotone-capable XGBoost + calibration + native exact TreeSHAP); it is not an
IDBI production calibration, and the honesty caveats ship inside the payloads.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ARTIFACT_DIR = Path(__file__).parent / "model_training" / "artifacts"

V1_EVALUATION_PATH = ARTIFACT_DIR / "sme_evaluation.json"
V1_HASH_KEYS = {
    "sba_xgboost_model_sha256": ARTIFACT_DIR / "sba_xgboost_model.json",
    "sba_xgboost_metadata_sha256": ARTIFACT_DIR / "sba_xgboost_metadata.json",
}
V2_EVALUATION_PATH = ARTIFACT_DIR / "sme_evaluation_v2.json"
V2_HASH_KEYS = {
    "sba_v2_model_sha256": ARTIFACT_DIR / "sba_v2_model.json",
    "sba_v2_metadata_sha256": ARTIFACT_DIR / "sba_v2_metadata.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _integrity(evaluation: dict | None, hash_keys: dict) -> dict:
    if evaluation is None:
        return {"status": "absent", "detail": "benchmark artifact not built"}
    expected = evaluation.get("artifacts", {})
    failures = []
    for key, path in hash_keys.items():
        if not path.exists() or not expected.get(key) or _sha256(path) != expected[key]:
            failures.append(path.name)
    if failures:
        return {"status": "fail", "detail": f"hash mismatch or missing: {', '.join(failures)}"}
    return {"status": "pass", "detail": f"{len(hash_keys)} artifact hashes verified"}


def artifact_integrity() -> dict:
    v1 = _integrity(_read(V1_EVALUATION_PATH), V1_HASH_KEYS)
    v2 = _integrity(_read(V2_EVALUATION_PATH), V2_HASH_KEYS)
    overall = "pass" if v1["status"] == "pass" and v2["status"] in ("pass", "absent") else (
        "fail" if "fail" in (v1["status"], v2["status"]) else v1["status"])
    return {"status": overall, "v1_baseline": v1, "v2_champion": v2}


def sme_benchmark() -> dict | None:
    """Full evidence payload (GET /model/sme-benchmark)."""
    v1 = _read(V1_EVALUATION_PATH)
    v2 = _read(V2_EVALUATION_PATH)
    if v1 is None and v2 is None:
        return None
    champion_version = "v2" if v2 is not None else "v1"
    return {
        "evidence_type": "real_small_business_outcome_benchmarks",
        "champion_version": champion_version,
        "champion": v2 if v2 is not None else v1,
        "baseline_v1": v1,
        "artifact_integrity": artifact_integrity(),
        "experiment_registry": "backend/model_training/experiments/registry.json",
    }


def sme_benchmark_summary() -> dict | None:
    """Compact headline for /governance and /submission/proof."""
    payload = sme_benchmark()
    if payload is None:
        return None
    champion = payload["champion"]
    summary = {
        "evidence_type": payload["evidence_type"],
        "champion_version": payload["champion_version"],
        "dataset": champion.get("dataset", {}).get("name"),
        "boundary": ("real US SBA small-business outcomes at natural base rates; "
                     "true temporal OOT + recession stress validated; not an IDBI/MSME production calibration"),
    }
    if payload["champion_version"] == "v2":
        splits = champion.get("splits", {})
        summary.update({
            "holdout_auc": splits.get("holdout", {}).get("auc"),
            "oot_auc": splits.get("oot", {}).get("auc"),
            "oot_ks": splits.get("oot", {}).get("ks"),
            "stress_auc": splits.get("stress", {}).get("auc"),
            "oot_rows": champion.get("dataset", {}).get("oot_rows"),
            "treeshap_exact": champion.get("explainability", {}).get("served_reconstruction_error_logit"),
        })
        v1 = payload.get("baseline_v1") or {}
        summary["v1_baseline"] = {
            "holdout_auc": v1.get("holdout", {}).get("auc"),
            "out_of_distribution_auc": v1.get("out_of_distribution", {}).get("auc"),
        }
    else:
        summary.update({
            "holdout_auc": champion.get("holdout", {}).get("auc"),
            "out_of_distribution_auc": champion.get("out_of_distribution", {}).get("auc"),
            "treeshap_exact": champion.get("explainability", {}).get("max_reconstruction_error_logit"),
        })
    return summary
