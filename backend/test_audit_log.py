from sample_data import SAMPLE_PROFILES
from scoring import score_profile
import audit_log


def test_scoring_appends_to_audit_log(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.jsonl")
    monkeypatch.setattr(audit_log, "_memory_log", [])
    monkeypatch.setattr(audit_log, "_last_hash", audit_log.GENESIS_HASH)
    monkeypatch.setattr(audit_log, "_loaded_path", None)

    score_profile(SAMPLE_PROFILES["ntc_hero"])
    after = audit_log.read_recent()

    assert len(after) == 1
    assert after[-1]["grade"] in "ABCDE"
    assert "timestamp" in after[-1]
    assert after[-1]["prev_hash"] == audit_log.GENESIS_HASH
    assert after[-1]["entry_hash"]
    assert "name" not in after[-1]
    assert after[-1]["subject_ref"].startswith("subject_")


def test_hash_chain_links_consecutive_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.jsonl")
    monkeypatch.setattr(audit_log, "_memory_log", [])
    monkeypatch.setattr(audit_log, "_last_hash", audit_log.GENESIS_HASH)
    monkeypatch.setattr(audit_log, "_loaded_path", None)

    score_profile(SAMPLE_PROFILES["ntc_hero"])
    score_profile(SAMPLE_PROFILES["stressed_retailer"])
    entries = audit_log.read_recent()

    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    result = audit_log.verify_chain(entries)
    assert result["valid"] is True
    assert result["entries_checked"] == 2


def test_audit_log_path_can_target_a_writable_runtime_directory(tmp_path, monkeypatch):
    runtime_log = tmp_path / "runtime" / "audit.jsonl"
    monkeypatch.setenv("UDYAMPULSE_AUDIT_LOG_PATH", str(runtime_log))

    assert audit_log.configured_log_path() == runtime_log


def test_verify_chain_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.jsonl")
    monkeypatch.setattr(audit_log, "_memory_log", [])
    monkeypatch.setattr(audit_log, "_last_hash", audit_log.GENESIS_HASH)
    monkeypatch.setattr(audit_log, "_loaded_path", None)

    score_profile(SAMPLE_PROFILES["ntc_hero"])
    score_profile(SAMPLE_PROFILES["stressed_retailer"])
    entries = audit_log.read_recent()

    tampered = [dict(e) for e in entries]
    tampered[0]["score"] = 999  # simulate a retroactive edit to a past decision

    result = audit_log.verify_chain(tampered)
    assert result["valid"] is False
    assert result["break_index"] == 0


def test_verify_chain_requires_genesis_for_a_complete_log(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.jsonl")
    monkeypatch.setattr(audit_log, "_memory_log", [])
    monkeypatch.setattr(audit_log, "_last_hash", audit_log.GENESIS_HASH)
    monkeypatch.setattr(audit_log, "_loaded_path", None)

    score_profile(SAMPLE_PROFILES["ntc_hero"])
    entries = audit_log.read_recent()
    forged = [dict(entries[0])]
    forged[0]["prev_hash"] = "f" * 64
    body = {key: value for key, value in forged[0].items() if key not in ("prev_hash", "entry_hash")}
    forged[0]["entry_hash"] = audit_log._compute_entry_hash(body, forged[0]["prev_hash"])

    result = audit_log.verify_chain(forged)
    assert result["valid"] is False
    assert "genesis" in result["reason"]


def test_restart_reloads_last_hash_and_continues_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.jsonl")
    monkeypatch.setattr(audit_log, "_memory_log", [])
    monkeypatch.setattr(audit_log, "_last_hash", audit_log.GENESIS_HASH)
    monkeypatch.setattr(audit_log, "_loaded_path", None)

    score_profile(SAMPLE_PROFILES["ntc_hero"])
    first_hash = audit_log.read_recent()[-1]["entry_hash"]

    monkeypatch.setattr(audit_log, "_memory_log", [])
    monkeypatch.setattr(audit_log, "_last_hash", audit_log.GENESIS_HASH)
    monkeypatch.setattr(audit_log, "_loaded_path", None)
    score_profile(SAMPLE_PROFILES["stressed_retailer"])
    entries = audit_log.read_recent()

    assert entries[-1]["prev_hash"] == first_hash
    assert audit_log.verify_chain(entries)["valid"] is True
