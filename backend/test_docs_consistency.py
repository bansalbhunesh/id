"""Guard against decision-figure drift between prose and the live backend.

UdyamPulse's core claim is that its headline numbers are backend-verifiable
(`curl /portfolio`). These tests fail if a judge-facing document stops matching
what `build_portfolio_snapshot()` actually computes, or if a known-stale figure
creeps back in. This is the automated fix for the README/pitch/demo-script
figure that had drifted from the live API.
"""
import re
from pathlib import Path

from portfolio import build_portfolio_snapshot

REPO_ROOT = Path(__file__).resolve().parent.parent
JUDGE_FACING_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "PITCH_OUTLINE.md",
    REPO_ROOT / "docs" / "DEMO_SCRIPT.md",
]

# Figures that were once documented but never matched the computed cohort.
STALE_STRINGS = ["30,80,000", "3,080,000", "4 alternate-data approvals"]


def _inr_group(rupees: float) -> str:
    """Format an integer rupee amount with Indian digit grouping.

    3023000 -> "30,23,000" (last three digits, then groups of two).
    """
    digits = str(int(round(rupees)))
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    head = re.sub(r"(?<=\d)(?=(?:\d\d)+$)", ",", head)
    return f"{head},{tail}"


def test_no_stale_portfolio_figures_in_judge_facing_docs():
    for doc in JUDGE_FACING_DOCS:
        text = doc.read_text(encoding="utf-8")
        for stale in STALE_STRINGS:
            assert stale not in text, f"{doc.name} still contains stale figure '{stale}'"


def test_live_credit_unlocked_figure_present_in_readme():
    summary = build_portfolio_snapshot()["summary"]
    figure = _inr_group(summary["credit_unlocked"])
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert figure in readme, (
        f"README does not contain the live credit-unlocked figure Rs {figure}; "
        "prose has drifted from GET /portfolio again."
    )


def test_inr_group_formatting():
    assert _inr_group(3023000) == "30,23,000"
    assert _inr_group(2700000) == "27,00,000"
    assert _inr_group(950) == "950"
