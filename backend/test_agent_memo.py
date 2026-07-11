import agent_memo
from agent_memo import _memo_matches_known_facts, generate_memo
from sample_data import SAMPLE_PROFILES
from scoring import score_profile


def _score():
    return score_profile(SAMPLE_PROFILES["ntc_hero"], record_audit=False)


def test_memo_matching_known_facts_is_accepted():
    score = _score()
    memo = (
        f"{score['name']} scores grade {score['grade']} ({score['score']}/100) "
        f"with an eligible limit of Rs {score['eligible_limit']:,.0f}."
    )
    assert _memo_matches_known_facts(memo, score) is True


def test_memo_with_a_fabricated_limit_is_rejected():
    score = _score()
    fabricated_limit = score["eligible_limit"] + 5_000_000
    memo = f"{score['name']} is approved for Rs {fabricated_limit:,.0f}."
    assert _memo_matches_known_facts(memo, score) is False


def test_memo_with_a_fabricated_score_is_rejected():
    score = _score()
    wrong_score = score["score"] - 1 if score["score"] > 0 else score["score"] + 1
    memo = f"{score['name']} scores {wrong_score}/100."
    assert _memo_matches_known_facts(memo, score) is False


def test_memo_with_a_fabricated_grade_is_rejected():
    score = _score()
    wrong_grade = "E" if score["grade"] != "E" else "A"
    memo = f"{score['name']} is grade {wrong_grade}."
    assert _memo_matches_known_facts(memo, score) is False


def test_generate_memo_falls_back_when_bedrock_output_contradicts_the_score(monkeypatch):
    monkeypatch.setenv("UDYAMPULSE_MEMO_PROVIDER", "bedrock")
    score = _score()
    fabricated = f"{score['name']} is approved for Rs {score['eligible_limit'] + 9_999_999:,.0f}."
    monkeypatch.setattr(agent_memo, "_bedrock_memo", lambda _score_result: fabricated)

    memo = generate_memo(score)

    assert memo == agent_memo._deterministic_memo(score)
    assert "9,999,999" not in memo


def test_generate_memo_accepts_a_bedrock_output_consistent_with_the_score(monkeypatch):
    monkeypatch.setenv("UDYAMPULSE_MEMO_PROVIDER", "bedrock")
    score = _score()
    consistent_memo = (
        f"{score['name']} scores grade {score['grade']} ({score['score']}/100), "
        f"eligible limit Rs {score['eligible_limit']:,.0f}."
    )
    monkeypatch.setattr(agent_memo, "_bedrock_memo", lambda _score_result: consistent_memo)

    assert generate_memo(score) == consistent_memo
