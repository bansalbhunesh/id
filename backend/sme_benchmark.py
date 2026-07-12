"""Runtime access to the real SBA small-business default benchmark.

This is UdyamPulse's answer to the field's shared weakness: every public
competitor validates on synthetic labels or a single cross-sectional holdout.
This benchmark trains the exact production methodology (monotone constraints,
calibration, native exact TreeSHAP) on REAL small-business charge-off outcomes
and validates it OUT OF DISTRIBUTION on a differently-distributed real sample.

It is exposed as read-only evidence (`GET /model/sme-benchmark`) and summarised
in `/governance` and `/submission/proof`. It is deliberately separate from the
served alternate-data pillar decision -- it is real-outcome methodology proof,
not an IDBI production calibration.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ARTIFACT_DIR = Path(__file__).parent / "model_training" / "artifacts"
SME_EVALUATION_PATH = ARTIFACT_DIR / "sme_evaluation.json"
SBA_MODEL_PATH = ARTIFACT_DIR / "sba_xgboost_model.json"
SBA_METADATA_PATH = ARTIFACT_DIR / "sba_xgboost_metadata.json"

_ARTIFACT_HASH_KEYS = {
    "sba_xgboost_model_sha256": SBA_MODEL_PATH,
    "sba_xgboost_metadata_sha256": SBA_METADATA_PATH,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_evaluation() -> dict | None:
    if not SME_EVALUATION_PATH.exists():
        return None
    with SME_EVALUATION_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def artifact_integrity() -> dict:
    evaluation = _read_evaluation()
    if evaluation is None:
        return {"status": "absent", "detail": "SME benchmark artifact not built"}
    expected = evaluation.get("artifacts", {})
    failures = []
    for key, path in _ARTIFACT_HASH_KEYS.items():
        if not path.exists() or not expected.get(key) or _sha256(path) != expected[key]:
            failures.append(path.name)
    if failures:
        return {"status": "fail", "detail": f"hash mismatch or missing: {', '.join(failures)}"}
    return {"status": "pass", "detail": f"{len(_ARTIFACT_HASH_KEYS)} SME artifact hashes verified"}


def sme_benchmark() -> dict | None:
    """Full evaluation payload (for GET /model/sme-benchmark)."""
    evaluation = _read_evaluation()
    if evaluation is None:
        return None
    evaluation = dict(evaluation)
    evaluation["artifact_integrity"] = artifact_integrity()
    return evaluation


def sme_benchmark_summary() -> dict | None:
    """Compact headline for governance / submission proof."""
    evaluation = _read_evaluation()
    if evaluation is None:
        return None
    holdout = evaluation.get("holdout", {})
    ood = evaluation.get("out_of_distribution", {})
    return {
        "evidence_type": "real_small_business_outcome_benchmark",
        "dataset": evaluation.get("dataset", {}).get("name"),
        "champion": evaluation.get("champion_provider"),
        "holdout_auc": holdout.get("auc"),
        "holdout_ks": holdout.get("ks"),
        "holdout_brier": holdout.get("brier_score"),
        "out_of_distribution_auc": ood.get("auc"),
        "out_of_distribution_psi": ood.get("psi_holdout_vs_shift"),
        "treeshap_exact": evaluation.get("explainability", {}).get("max_reconstruction_error_logit"),
        "boundary": "real US small-business outcomes; out-of-distribution validated; not IDBI/MSME production calibration",
    }
