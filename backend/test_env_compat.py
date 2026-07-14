"""The SAAKHSCORE_ prefix is preferred; legacy UDYAMPULSE_ still works.

The rest of the suite sets UDYAMPULSE_* variables throughout, so the legacy
fallback path is exercised continuously; these tests pin the preferred-name
path and the precedence rule.
"""
from env_compat import env_setting


def test_preferred_prefix_is_read(monkeypatch):
    monkeypatch.delenv("UDYAMPULSE_MODE", raising=False)
    monkeypatch.setenv("SAAKHSCORE_MODE", "public_demo")
    assert env_setting("MODE", "fallback-default") == "public_demo"


def test_legacy_prefix_still_honored(monkeypatch):
    monkeypatch.delenv("SAAKHSCORE_MODE", raising=False)
    monkeypatch.setenv("UDYAMPULSE_MODE", "pilot")
    assert env_setting("MODE", "fallback-default") == "pilot"


def test_preferred_wins_when_both_set(monkeypatch):
    monkeypatch.setenv("SAAKHSCORE_MODE", "public_demo")
    monkeypatch.setenv("UDYAMPULSE_MODE", "pilot")
    assert env_setting("MODE") == "public_demo"


def test_default_when_neither_set(monkeypatch):
    monkeypatch.delenv("SAAKHSCORE_MODE", raising=False)
    monkeypatch.delenv("UDYAMPULSE_MODE", raising=False)
    assert env_setting("MODE", "public_demo") == "public_demo"
    assert env_setting("MODE") is None


def test_empty_string_counts_as_set_like_os_getenv_chain(monkeypatch):
    monkeypatch.setenv("SAAKHSCORE_MODE", "")
    monkeypatch.setenv("UDYAMPULSE_MODE", "pilot")
    assert env_setting("MODE", "public_demo") == ""
