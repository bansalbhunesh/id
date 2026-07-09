"""Append-only audit log for every scoring decision.

RBI's draft Guidance on Model Risk Management requires AI-assisted credit
decisions to be "consistent, unbiased, explainable and verifiable" -- and
notes that most regulated entities using AI do not keep audit logs. This
module is UdyamPulse's answer: every scored decision is recorded with its
grade, verdict, and top reasons, so any decision can be reconstructed and
reviewed later.

In-memory storage is the source of truth (works identically on a normal
VM/Docker host or an ephemeral serverless function). Disk persistence to
LOG_PATH is attempted best-effort on top of that -- serverless filesystems
are often read-only or reset between invocations, so a failed disk write
must never break a scoring request. Stage 2 swaps this for a real
database/log store.
"""
import json
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "audit_log.jsonl"

_memory_log: list[dict] = []


def record(score_result: dict) -> None:
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
