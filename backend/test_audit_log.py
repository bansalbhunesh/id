from sample_data import SAMPLE_PROFILES
from scoring import score_profile
import audit_log


def test_scoring_appends_to_audit_log(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.jsonl")
    monkeypatch.setattr(audit_log, "_memory_log", [])

    score_profile(SAMPLE_PROFILES["ntc_hero"])
    after = audit_log.read_recent()

    assert len(after) == 1
    assert after[-1]["grade"] in "ABCDE"
    assert "timestamp" in after[-1]
