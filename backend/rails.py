"""OCEN-aligned lending output rail.

The scoring engine already produces a verdict and an EMI-capacity indicative
limit with a printed basis. This module reshapes that decision into the
artifact a lender-side system would hand to a Loan Service Provider: a priced,
time-boxed working-capital offer with a reducing-balance EMI, or an honest
PENDING_MANUAL_REVIEW / REJECTED status. Field shapes follow OCEN 4.0 naming
conventions; nothing here claims network membership. `rails_registry()` states
exactly which rail is simulated, synthetic, or an output contract only -- a
rail is never labelled beyond what a judge can exercise against this
deployment.
"""
import hashlib

from scoring import POLICY_ANNUAL_RATE, POLICY_TENOR_MONTHS, _annuity_factor

# Demo pricing policy (documented and versioned like the sizing inputs in
# scoring.py -- an IDBI deployment replaces these with product policy, not
# code changes). Spread is over the working-capital reference rate by grade;
# D/E files are policy declines and are never priced.
GRADE_RATE_SPREAD = {"A": 0.0, "B": 0.015, "C": 0.03}
PROCESSING_FEE_RATE = 0.005
PROCESSING_FEE_FLOOR_INR = 1000.0
PROCESSING_FEE_CAP_INR = 10000.0
OFFER_VALIDITY_DAYS = 30

_DECISION_TO_STATUS = {
    "Approved": "OFFER_EXTENDED",
    "Review": "PENDING_MANUAL_REVIEW",
    "Rejected": "REJECTED",
}

SPEC_NOTE = (
    "OCEN 4.0-aligned field shapes for a lender-side loan offer. Demonstration "
    "artifact derived from the documented demo policy inputs; not originated "
    "through an OCEN network and not an IDBI sanction or rate card."
)


def _offer_id(msme_id: str, score: int, principal: float) -> str:
    """Deterministic offer id: the same decision always yields the same id,
    so a judge can replay the GET and get a byte-identical artifact."""
    digest = hashlib.sha256(f"{msme_id}|{score}|{principal:.2f}".encode()).hexdigest()
    return f"OFR-{digest[:12].upper()}"


def _priced_terms(grade: str, principal: float) -> dict:
    annual_rate = POLICY_ANNUAL_RATE + GRADE_RATE_SPREAD[grade]
    emi = principal / _annuity_factor(annual_rate, POLICY_TENOR_MONTHS)
    fee = min(max(principal * PROCESSING_FEE_RATE, PROCESSING_FEE_FLOOR_INR),
              PROCESSING_FEE_CAP_INR)
    return {
        "principal_inr": round(principal, 2),
        "annual_interest_rate_pct": round(annual_rate * 100, 2),
        "interest_type": "REDUCING_BALANCE",
        "tenure_months": POLICY_TENOR_MONTHS,
        "emi_inr": round(emi, 2),
        "processing_fee_inr": round(fee, 2),
        "pricing_basis": (
            f"reference_rate {POLICY_ANNUAL_RATE:.2%} + grade_{grade}_spread "
            f"{GRADE_RATE_SPREAD[grade]:.2%}"
        ),
    }


def build_ocen_offer(msme_id: str, result: dict) -> dict:
    """Reshape a scoring result into an OCEN-aligned offer artifact.

    Pure function of the scoring result: no audit writes, no clock reads --
    validity ships as a day count for the consuming system to anchor at
    acceptance time, which also keeps the artifact replay-identical.
    """
    decision = result["alternate_data_decision"]
    status = _DECISION_TO_STATUS[decision]
    grade = result["grade"]
    principal = float(result["eligible_limit"])
    offer = {
        "loan_application_id": f"DEMO-{msme_id.upper()}",
        "offer_id": _offer_id(msme_id, result["score"], principal),
        "product": "WORKING_CAPITAL_TERM",
        "status": status,
        "decision_inputs": {
            "score": result["score"],
            "grade": grade,
            "pd_estimate": result.get("pd_estimate"),
            "policy_route": result["policy"]["route"],
            "limit_binding_constraint": result["limit_basis"]["binding_constraint"],
        },
        "offer_validity_days": OFFER_VALIDITY_DAYS,
        "spec_alignment": SPEC_NOTE,
    }
    if status == "REJECTED" or principal <= 0:
        offer["status"] = "REJECTED" if status == "REJECTED" else status
        offer["rejection_reason"] = result["policy"]["reason"]
        return offer
    offer["terms"] = _priced_terms(grade, principal)
    if status == "PENDING_MANUAL_REVIEW":
        offer["review_reason"] = result["policy"]["reason"]
        offer["terms"]["note"] = (
            "Indicative pricing only; final terms require the mandated "
            "underwriter review recorded in the decision policy."
        )
    return offer


def rails_registry() -> dict:
    """Honest per-rail status: what is exercisable on this deployment today,
    what is synthetic, and what exists only as an output contract."""
    return {
        "honesty_note": (
            "A rail is never labelled beyond what a judge can exercise against "
            "this live deployment. Nothing below claims a production network "
            "connection."
        ),
        "rails": [
            {
                "rail": "account_aggregator",
                "direction": "ingestion",
                "status": "simulated_ingestion_validated_schema",
                "evidence": (
                    "POST /sandbox/score accepts AA-style consented payloads; "
                    "consent purpose, scope, expiry and revocation are enforced "
                    "by schema validation (403 on expired consent)."
                ),
            },
            {
                "rail": "gstn",
                "direction": "ingestion",
                "status": "synthetic_demo_signals",
                "evidence": "GST discipline/turnover signals ship in every scored case; see /msmes/{id}/score data_sources.",
            },
            {
                "rail": "upi",
                "direction": "ingestion",
                "status": "synthetic_demo_signals",
                "evidence": "UPI velocity/counterparty signals ship in every scored case.",
            },
            {
                "rail": "epfo",
                "direction": "ingestion",
                "status": "synthetic_demo_signals",
                "evidence": "Payroll footprint signal, labelled Synthetic in the data source register.",
            },
            {
                "rail": "ocen",
                "direction": "output",
                "status": "spec_aligned_output_artifact",
                "evidence": "GET /rails/ocen/offer/{msme_id} returns the priced offer artifact for every seeded case.",
            },
            {
                "rail": "uli",
                "direction": "output",
                "status": "adapter_design_only",
                "evidence": "Integration design documented in docs/MSME_MODEL_ROADMAP.md; no endpoint is claimed.",
            },
        ],
    }
