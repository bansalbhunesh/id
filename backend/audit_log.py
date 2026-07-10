"""Append-only, hash-chained audit log for every scoring decision.

RBI's draft Guidance on Model Risk Management requires AI-assisted credit
decisions to be "consistent, unbiased, explainable and verifiable" -- and
notes that most regulated entities using AI do not keep audit logs. This
module is UdyamPulse's answer: every scored decision is recorded with its
grade, verdict, and top reasons, so any decision can be reconstructed and
reviewed later.

Each entry is chained to the previous one's hash (`prev_hash`/`entry_hash`),
so `verify_chain` can detect if any past entry was edited or removed --
append-only in practice, not just in name. Full records (including borrower
name) are only exposed via the auditor-gated `GET /audit-log`; every public
surface that touches audit data (see portfolio.py's `_redact_latest_decision`)
redacts the name first.

In-memory storage is the source of truth (works identically on a normal
VM/Docker host or an ephemeral serverless function). Disk persistence to
LOG_PATH is attempted best-effort on top of that -- serverless filesystems
are often read-only or reset between invocations, so a failed disk write
must never break a scoring request. A production pilot swaps this for a
real database/log store with the same hash-chain contract.
"""
import hashlib
import json
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "audit_log.jsonl"
GENESIS_HASH = "0" * 64

_memory_log: list[dict] = []
_last_hash: str = GENESIS_HASH


def _compute_entry_hash(entry_without_hash: dict, prev_hash: str) -> str:
    payload = json.dumps({**entry_without_hash, "prev_hash": prev_hash}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record(score_result: dict) -> None:
    global _last_hash

    entry = {
        "timestamp": time.time(),
        "name": score_result["name"],
        "score": score_result["score"],
        "grade": score_result["grade"],
        "risk_band": score_result.get("risk_band"),
        "eligible_limit": score_result.get("eligible_limit"),
        "traditional_decision": score_result["traditional"]["decision"],
        "alternate_data_decision": score_result["alternate_data_decision"],
        "reasons": score_result["reasons"],
    }
    prev_hash = _last_hash
    entry_hash = _compute_entry_hash(entry, prev_hash)
    entry["prev_hash"] = prev_hash
    entry["entry_hash"] = entry_hash
    _last_hash = entry_hash

    _memory_log.append(entry)

    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # read-only filesystem (e.g. serverless) -- in-memory log still holds it


def read_recent(limit: int = 50) -> list[dict]:
    limit = max(1, min(limit, 500))

    if _memory_log:
        return _memory_log[-limit:]

    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines[-limit:]]


def verify_chain(entries: list[dict]) -> dict:
    """Recomputes each entry's hash from its own fields and checks it links
    to the previous entry in this window. Returns the first break found, if
    any. `entries` may be a truncated window (e.g. read_recent's limit), so
    the first entry's prev_hash is only checked for internal consistency
    (its own entry_hash recomputation), not against a global genesis -- a
    window doesn't know what came before it.
    """
    for index, entry in enumerate(entries):
        claimed_hash = entry.get("entry_hash")
        claimed_prev = entry.get("prev_hash")
        body = {k: v for k, v in entry.items() if k not in ("prev_hash", "entry_hash")}
        recomputed = _compute_entry_hash(body, claimed_prev)

        if recomputed != claimed_hash:
            return {"valid": False, "break_index": index, "reason": "entry_hash does not match recomputed hash (entry was modified)"}
        if index > 0 and claimed_prev != entries[index - 1].get("entry_hash"):
            return {"valid": False, "break_index": index, "reason": "prev_hash does not match preceding entry in this window"}

    return {"valid": True, "break_index": None, "reason": None, "entries_checked": len(entries)}
