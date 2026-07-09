from portfolio import build_governance_summary, build_portfolio_snapshot


def test_portfolio_snapshot_shows_ntc_credit_unlocked():
    snapshot = build_portfolio_snapshot()

    assert snapshot["summary"]["cases"] >= 5
    assert snapshot["summary"]["ntc_rescued"] >= 1
    assert snapshot["summary"]["credit_unlocked"] > 0
    assert len(snapshot["fairness"]["by_bureau_history"]) == 2
    assert {item["dimension"] for item in snapshot["fairness"]["monitors"]} == {
        "Bureau history",
        "Sector",
        "Geography",
        "Vintage",
        "Gender",
    }


def test_governance_summary_exposes_live_controls():
    summary = build_governance_summary([])

    statuses = {control["status"] for control in summary["controls"]}
    assert "Live" in statuses
    assert summary["model"]["version"]
    assert summary["model"]["runtime"]["active_provider"]
    assert "fairness" in summary
