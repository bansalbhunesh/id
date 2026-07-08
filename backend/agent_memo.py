"""Generates a plain-language underwriter memo from a score result.

Template-based for the prototype -- no AWS credentials are available in
this dev environment. `generate_memo` is the seam: Stage 2 swaps this
implementation for an AWS Bedrock call (Claude/Titan) that takes the same
score payload and produces a richer, model-written memo. The calling code
in main.py does not need to change.
"""


def generate_memo(score_result: dict) -> str:
    name = score_result["name"]
    grade = score_result["grade"]
    limit = score_result["eligible_limit"]
    reasons = score_result["reasons"]
    trad = score_result["traditional"]

    strengths = [r for r in reasons if r.startswith("Strong")]
    watch_items = [r for r in reasons if r.startswith("Watch")]

    lines = [
        f"{name} scores grade {grade} ({score_result['score']}/100) on alternate-data underwriting, "
        f"suggesting an eligible limit of Rs {limit:,.0f}."
    ]

    if trad["decision"] == "Rejected" and score_result["alternate_data_decision"] == "Approved":
        lines.append(
            f"Traditional bureau-only underwriting would decline this applicant ({trad['reason']}), "
            "but alternate data (GST filing consistency, UPI transaction velocity, low cheque-bounce "
            "rate) shows a creditworthy, active business."
        )

    if strengths:
        lines.append("Strengths: " + "; ".join(s.replace("Strong: ", "") for s in strengths) + ".")
    if watch_items:
        lines.append("Watch items: " + "; ".join(w.replace("Watch: ", "") for w in watch_items) + ".")

    return " ".join(lines)
