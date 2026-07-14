"""Pseudonymised, persistent, hash-chained decision audit events."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

from env_compat import env_setting
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_PATH = Path(__file__).parent / "audit_log.jsonl"


def configured_log_path() -> Path:
    configured = env_setting("AUDIT_LOG_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_LOG_PATH


LOG_PATH = configured_log_path()
GENESIS_HASH = "0" * 64

_memory_log: list[dict] = []
_last_hash: str = GENESIS_HASH
_loaded_path: Path | None = None
_lock = threading.RLock()


class AuditIntegrityError(RuntimeError):
    pass


def _compute_entry_hash(entry_without_hash: dict, prev_hash: str) -> str:
    payload = json.dumps(
        {**entry_without_hash, "prev_hash": prev_hash},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _subject_ref(name: str) -> str:
    # A deployment must override this key. The demo default is intentionally
    # labelled and never protects real data; it merely keeps names out of logs.
    key = env_setting("AUDIT_HMAC_KEY", "public-demo-not-for-real-data")
    digest = hmac.new(
        key.encode("utf-8"),
        name.strip().casefold().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"subject_{digest[:20]}"


def verify_chain(entries: list[dict], *, require_genesis: bool = True) -> dict:
    for index, entry in enumerate(entries):
        claimed_hash = entry.get("entry_hash")
        claimed_prev = entry.get("prev_hash")
        if not claimed_hash or not claimed_prev:
            return {
                "valid": False,
                "break_index": index,
                "reason": "entry is missing prev_hash or entry_hash",
            }
        body = {
            key: value
            for key, value in entry.items()
            if key not in ("prev_hash", "entry_hash")
        }
        if _compute_entry_hash(body, claimed_prev) != claimed_hash:
            return {
                "valid": False,
                "break_index": index,
                "reason": "entry_hash does not match recomputed hash",
            }
        if index == 0 and require_genesis and claimed_prev != GENESIS_HASH:
            return {
                "valid": False,
                "break_index": 0,
                "reason": "first entry does not link to the audit genesis hash",
            }
        if index > 0 and claimed_prev != entries[index - 1].get("entry_hash"):
            return {
                "valid": False,
                "break_index": index,
                "reason": "prev_hash does not match the preceding entry",
            }
    return {
        "valid": True,
        "break_index": None,
        "reason": None,
        "entries_checked": len(entries),
    }


def _ensure_initialized() -> None:
    global _memory_log, _last_hash, _loaded_path
    resolved = LOG_PATH.resolve()
    if _loaded_path == resolved:
        return

    entries: list[dict] = []
    if LOG_PATH.exists():
        for line_number, line in enumerate(
            LOG_PATH.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AuditIntegrityError(
                    f"Audit log contains invalid JSON on line {line_number}"
                ) from exc
        legacy_entries = entries and any(
            "prev_hash" not in entry or "entry_hash" not in entry for entry in entries
        )
        if legacy_entries:
            migrated: list[dict] = []
            previous = GENESIS_HASH
            for index, old in enumerate(entries):
                body = {
                    key: value
                    for key, value in old.items()
                    if key not in ("name", "prev_hash", "entry_hash")
                }
                body.update(
                    {
                        "event_id": body.get(
                            "event_id", f"legacy_{index}_{int(body.get('timestamp', 0) * 1_000_000)}"
                        ),
                        "subject_ref": _subject_ref(old.get("name", "unknown")),
                        "data_classification": "pseudonymised_legacy_decision_metadata",
                        "migrated_from_legacy": True,
                    }
                )
                entry_hash = _compute_entry_hash(body, previous)
                body["prev_hash"] = previous
                body["entry_hash"] = entry_hash
                migrated.append(body)
                previous = entry_hash
            temporary = LOG_PATH.with_suffix(".jsonl.migrating")
            temporary.write_text(
                "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in migrated),
                encoding="utf-8",
            )
            temporary.replace(LOG_PATH)
            entries = migrated
        verification = verify_chain(entries)
        if not verification["valid"]:
            raise AuditIntegrityError(
                f"Audit chain failed at entry {verification['break_index']}: {verification['reason']}"
            )

    _memory_log = entries
    _last_hash = entries[-1]["entry_hash"] if entries else GENESIS_HASH
    _loaded_path = resolved


def record(score_result: dict) -> None:
    global _last_hash
    with _lock:
        _ensure_initialized()
        policy = score_result.get("policy", {})
        entry = {
            "audit_schema_version": "decision-audit-v2",
            "event_id": f"decision_{time.time_ns()}",
            "timestamp": time.time(),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "subject_ref": _subject_ref(score_result["name"]),
            "data_classification": "pseudonymised_decision_metadata",
            "score": score_result["score"],
            "grade": score_result["grade"],
            "risk_band": score_result.get("risk_band"),
            "pd_estimate": score_result.get("pd_estimate"),
            "eligible_limit": score_result.get("eligible_limit"),
            "traditional_decision": score_result["traditional"]["decision"],
            "alternate_data_decision": score_result["alternate_data_decision"],
            "policy_version": policy.get("version"),
            "policy_route": policy.get("route"),
            "model_provider": score_result.get("ml", {}).get("provider"),
            "reasons": score_result["reasons"],
        }
        entry_hash = _compute_entry_hash(entry, _last_hash)
        entry["prev_hash"] = _last_hash
        entry["entry_hash"] = entry_hash

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        _memory_log.append(entry)
        _last_hash = entry_hash


def read_recent(limit: int = 50) -> list[dict]:
    with _lock:
        _ensure_initialized()
        bounded = max(1, min(limit, 500))
        return [dict(entry) for entry in _memory_log[-bounded:]]
