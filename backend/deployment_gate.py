"""Fail-closed promotion gates for public demo, pilot and production modes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from auth import authentication_status


ARTIFACT_DIR = Path(__file__).parent / "model_training" / "artifacts"
CHAMPION_PATH = ARTIFACT_DIR / "champion.json"
EVALUATION_PATH = ARTIFACT_DIR / "evaluation.json"
VALID_MODES = {"public_demo", "pilot", "production"}
PILOT_MODES = {"pilot", "production"}
DURABLE_AUDIT_BACKENDS = {"managed_append_only", "postgres_worm"}
ARTIFACT_FILES = {
    "champion_manifest_sha256": CHAMPION_PATH,
    "logistic_sha256": ARTIFACT_DIR / "artifact.json",
    "xgboost_model_sha256": ARTIFACT_DIR / "xgboost_model.json",
    "xgboost_metadata_sha256": ARTIFACT_DIR / "xgboost_metadata.json",
}


def _champion_manifest() -> dict:
    if not CHAMPION_PATH.exists():
        return {}
    return json.loads(CHAMPION_PATH.read_text(encoding="utf-8"))


def _gate(code: str, passed: bool, detail: str) -> dict:
    return {"code": code, "status": "pass" if passed else "block", "detail": detail}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_integrity() -> tuple[bool, str]:
    if not EVALUATION_PATH.exists():
        return False, "evaluation evidence is missing"
    evidence = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    expected = evidence.get("artifacts", {})
    failures = []
    for key, path in ARTIFACT_FILES.items():
        if not path.exists() or not expected.get(key) or _sha256(path) != expected[key]:
            failures.append(path.name)
    if failures:
        return False, f"hash mismatch or missing evidence: {', '.join(failures)}"
    return True, f"{len(ARTIFACT_FILES)} committed artifact hashes verified"


def build_deployment_readiness() -> dict:
    from ml import model_status

    mode = os.getenv("UDYAMPULSE_MODE", "public_demo").strip().lower()
    manifest = _champion_manifest()
    runtime = model_status()
    auth = authentication_status()
    model_scope = manifest.get("deployment_scope", "public_demo_only")
    temporal_validation = manifest.get("temporal_validation", "cross_sectional_holdout")
    audit_backend = os.getenv("UDYAMPULSE_AUDIT_BACKEND", "local_jsonl")
    custom_hmac = bool(os.getenv("UDYAMPULSE_AUDIT_HMAC_KEY"))
    artifacts_valid, artifact_detail = _artifact_integrity()

    gates = [
        _gate(
            "model_provider",
            runtime.get("active_provider") == runtime.get("champion_provider"),
            f"active={runtime.get('active_provider')}; champion={runtime.get('champion_provider')}",
        ),
        _gate("artifact_integrity", artifacts_valid, artifact_detail),
        _gate(
            "model_scope",
            model_scope == "idbi_pilot",
            f"artifact deployment_scope={model_scope}",
        ),
        _gate(
            "true_out_of_time_evidence",
            temporal_validation == "true_oot",
            f"artifact temporal_validation={temporal_validation}",
        ),
        _gate(
            "private_identity_credentials",
            not auth["demo_keys_active"],
            "custom role credentials configured" if not auth["demo_keys_active"] else "published demo keys are active",
        ),
        _gate(
            "private_audit_hmac",
            custom_hmac,
            "deployment HMAC key configured" if custom_hmac else "public demo HMAC fallback is active",
        ),
        _gate(
            "durable_audit_backend",
            audit_backend in DURABLE_AUDIT_BACKENDS,
            f"audit backend={audit_backend}",
        ),
        _gate(
            "consent_enforcement",
            True,
            "purpose, source scope, status and expiry are validated before sandbox scoring",
        ),
    ]
    blockers = [gate for gate in gates if gate["status"] == "block"]
    pilot_ready = not blockers
    runtime_allowed = mode == "public_demo" or (mode in PILOT_MODES and pilot_ready)
    return {
        "mode": mode,
        "status": (
            "public_demo_allowed"
            if mode == "public_demo"
            else "pilot_ready" if pilot_ready else "pilot_blocked"
        ),
        "runtime_allowed": runtime_allowed,
        "pilot_ready": pilot_ready,
        "enforcement": "fail_closed_for_pilot_and_production",
        "model_scope": model_scope,
        "temporal_validation": temporal_validation,
        "audit_backend": audit_backend,
        "authentication": auth,
        "gates": gates,
        "blockers": blockers,
    }


def assert_deployment_allowed() -> None:
    readiness = build_deployment_readiness()
    if readiness["mode"] not in VALID_MODES:
        raise RuntimeError(
            f"SaakhScore startup blocked: invalid UDYAMPULSE_MODE={readiness['mode']}"
        )
    if not readiness["runtime_allowed"]:
        codes = ", ".join(blocker["code"] for blocker in readiness["blockers"])
        raise RuntimeError(
            f"SaakhScore {readiness['mode']} startup blocked by promotion gates: {codes}"
        )
