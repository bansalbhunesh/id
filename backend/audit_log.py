"""Append-only audit log for every scoring decision.

RBI's draft Guidance on Model Risk Management requires AI-assisted credit
decisions to be "consistent, unbiased, explainable and verifiable" -- and
notes that most regulated entities using AI do not keep audit logs. This
module is UdyamPulse's answer: every scored decision is recorded with its
grade, verdict, and top reasons, so any decision can be reconstructed and
reviewed later.
"""
import json
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "audit_log.jsonl"


def record(score_result: dict) -> None:
    entry = {
        "timestamp": time.time(),
        "name": score_result["name"],
        "score": score_result["score"],
        "grade": score_result["grade"],
        "traditional_decision": score_result["traditional"]["decision"],
        "alternate_data_decision": score_result["alternate_data_decision"],
        "reasons": score_result["reasons"],
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_recent(limit: int = 50) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines[-limit:]]
