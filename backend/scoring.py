"""Rule-based MSME financial health scoring engine.

Five pillars, each 0-20, summed to a 0-100 score with an A-E grade.
The descriptive score stays separate from the calibrated XGBoost PD model
and the versioned lending policy so each layer can be audited independently.
"""
from pydantic import BaseModel, ConfigDict, Field


class MSMEProfile(BaseModel):
    # allow_inf_nan=False rejects non-finite floats (JSON `1e309` -> inf, NaN) at
    # the validation boundary. Without it, `inf` passes `ge=0` (inf >= 0 is True),
    # propagates into limit maths, and either crashes JSON serialisation (500)
    # or emits non-standard `Infinity` into the audit log. Every numeric field
    # is also range-bounded so an underwriting input cannot be absurd, and every
    # free-text field is length-capped to bound request size and log growth.
    model_config = ConfigDict(allow_inf_nan=False, str_max_length=500)

    name: str = Field(min_length=1, max_length=200)
    sector: str = Field(default="General Trade", max_length=100)
    district: str = Field(default="Mumbai", max_length=100)
    gender: str | None = Field(default=None, max_length=40)
    vintage_months: int = Field(default=24, ge=0, le=600)
    employees: int = Field(default=12, ge=0, le=1_000_000)
    avg_monthly_inflow: float = Field(ge=0, le=1e12)
    inflow_volatility: float = Field(ge=0, le=100)  # coefficient of variation, 0-1+
    cheque_bounce_rate: float = Field(ge=0, le=1)  # 0-1
    gst_filing_streak_months: int = Field(ge=0, le=120)
    gst_turnover_growth_pct: float = Field(ge=-100, le=100_000)  # trailing 6mo, can be negative
    upi_txn_count_monthly: int = Field(ge=0, le=10_000_000)
    unique_counterparties: int = Field(ge=0, le=10_000_000)
    top_counterparty_share_pct: float = Field(default=0.0, ge=0, le=100)  # 0 = not supplied
    outstanding_debt_to_inflow: float = Field(ge=0, le=1_000_000)  # ratio
    # GST-declared turnover vs bank-observed inflow divergence, in percent of
    # bank inflow (+38 = declared 38% above observed). None = not computable
    # (single-source application); the guardrail then simply does not assert.
    gst_bank_divergence_pct: float | None = Field(default=None, ge=-100, le=10_000)
    has_bureau_history: bool = True  # False = New-to-Credit / New-to-Bank
    consent_status: str = Field(
        default="Not applicable: public synthetic demo data, no real consent required",
        max_length=500,
    )


PILLAR_MAX = 20


def score_liquidity(p: MSMEProfile) -> int:
    if p.avg_monthly_inflow <= 0:
        return 0
    volatility_penalty = min(p.inflow_volatility, 1.0) * PILLAR_MAX
    return round(PILLAR_MAX - volatility_penalty)


def score_discipline(p: MSMEProfile) -> int:
    bounce_penalty = min(p.cheque_bounce_rate, 1.0) * PILLAR_MAX
    filing_bonus = min(p.gst_filing_streak_months / 24, 1.0) * PILLAR_MAX
    return round(max(0, min(PILLAR_MAX, (PILLAR_MAX - bounce_penalty + filing_bonus) / 2)))


def score_momentum(p: MSMEProfile) -> int:
    growth = max(-50, min(50, p.gst_turnover_growth_pct))
    return round((growth + 50) / 100 * PILLAR_MAX)


def score_leverage(p: MSMEProfile) -> int:
    ratio = max(0, p.outstanding_debt_to_inflow)
    return round(max(0, PILLAR_MAX - min(ratio, 1.0) * PILLAR_MAX))


def score_digital_footprint(p: MSMEProfile) -> int:
    counterparty_score = min(p.unique_counterparties / 50, 1.0) * (PILLAR_MAX / 2)
    volume_score = min(p.upi_txn_count_monthly / 200, 1.0) * (PILLAR_MAX / 2)
    return round(counterparty_score + volume_score)


def grade_for(total: int) -> str:
    if total >= 80:
        return "A"
    if total >= 65:
        return "B"
    if total >= 50:
        return "C"
    if total >= 35:
        return "D"
    return "E"


CONCENTRATION_WATCH_THRESHOLD_PCT = 40  # shared with the "Counterparty concentration" guardrail
CONCENTRATION_LIMIT_HAIRCUT = 0.85  # 15% reduction: exposure to one counterparty's own payment risk

# GST-declared turnover vs bank-observed inflow: a business declaring far more
# than the bank sees is a classic inflation/diversion red flag; declaring far
# less suggests undisclosed accounts. Either direction warrants reconciliation.
DIVERGENCE_WATCH_THRESHOLD_PCT = 25

# Indicative-limit economics (demo policy inputs, documented and versioned --
# an IDBI deployment replaces these with product policy, not code changes).
POLICY_ANNUAL_RATE = 0.11          # working-capital reference rate
POLICY_TENOR_MONTHS = 36           # working-capital tenor used for sizing
EMI_CAPACITY_SHARE = 0.25          # at most 25% of avg monthly inflow services new debt
EXISTING_DEBT_TENOR_MONTHS = 60    # assumed amortisation of the existing debt stock
GRADE_CAP_MULTIPLIER = {"A": 6, "B": 4, "C": 2.5, "D": 1, "E": 0}


def concentration_multiplier(p: MSMEProfile) -> float:
    """A single counterparty accounting for 40%+ of digital inflow value is a
    direct exposure to that counterparty's own payment behaviour, not just a
    disclosure point -- the indicative limit is sized down accordingly rather
    than purely off the grade."""
    if p.top_counterparty_share_pct >= CONCENTRATION_WATCH_THRESHOLD_PCT:
        return CONCENTRATION_LIMIT_HAIRCUT
    return 1.0


def _annuity_factor(annual_rate: float, months: int) -> float:
    monthly = annual_rate / 12
    return (1 - (1 + monthly) ** -months) / monthly


def limit_basis(total: int, p: MSMEProfile) -> dict:
    """Debt-service-based indicative limit, capped by grade policy.

    The limit is no longer a bare grade multiple: it is the amount whose EMI
    (at the policy rate/tenor) fits inside the borrower's spare debt-service
    capacity, after estimating the service on the existing debt stock. The old
    grade multiple survives as a policy *ceiling*, and the counterparty
    concentration haircut still applies last.
    """
    grade = grade_for(total)
    existing_debt_stock = p.outstanding_debt_to_inflow * p.avg_monthly_inflow
    existing_service = (
        existing_debt_stock / _annuity_factor(POLICY_ANNUAL_RATE, EXISTING_DEBT_TENOR_MONTHS)
        if existing_debt_stock > 0
        else 0.0
    )
    affordable_emi = max(0.0, EMI_CAPACITY_SHARE * p.avg_monthly_inflow - existing_service)
    annuity_capacity = affordable_emi * _annuity_factor(POLICY_ANNUAL_RATE, POLICY_TENOR_MONTHS)
    grade_cap = GRADE_CAP_MULTIPLIER[grade] * p.avg_monthly_inflow
    pre_haircut = min(annuity_capacity, grade_cap)
    multiplier = concentration_multiplier(p)
    return {
        "method": "emi_capacity_annuity_with_grade_cap",
        "policy_inputs": {
            "annual_rate": POLICY_ANNUAL_RATE,
            "tenor_months": POLICY_TENOR_MONTHS,
            "emi_capacity_share_of_inflow": EMI_CAPACITY_SHARE,
            "existing_debt_amortisation_months": EXISTING_DEBT_TENOR_MONTHS,
        },
        "estimated_existing_monthly_service": round(existing_service, 2),
        "affordable_new_emi": round(affordable_emi, 2),
        "debt_service_capacity_limit": round(annuity_capacity, 2),
        "grade_policy_cap": round(grade_cap, 2),
        "binding_constraint": (
            "grade_policy_cap" if grade_cap <= annuity_capacity else "debt_service_capacity"
        ),
        "concentration_multiplier": multiplier,
        "indicative_limit": round(pre_haircut * multiplier, 2),
        "note": (
            "Indicative working-capital sizing from spare EMI capacity at documented policy "
            "inputs; not a sanctioned amount and not an IDBI-calibrated policy."
        ),
    }


def eligible_limit(total: int, p: MSMEProfile) -> float:
    """Indicative limit (key name kept for API compatibility)."""
    return limit_basis(total, p)["indicative_limit"]


def risk_band_for(grade: str) -> str:
    return {
        "A": "Low risk",
        "B": "Low-moderate risk",
        "C": "Bankable with conditions",
        "D": "High risk",
        "E": "Decline",
    }[grade]


def traditional_verdict(p: MSMEProfile) -> dict:
    """What a bureau-only underwriting process would decide.

    Traditional retail/MSME underwriting leans heavily on credit bureau
    history; a business with none is typically declined outright,
    regardless of how healthy its actual cash flows are.
    """
    if not p.has_bureau_history:
        return {
            "decision": "Rejected",
            "reason": "No credit bureau history on file (New-to-Credit/New-to-Bank).",
        }
    if p.outstanding_debt_to_inflow > 0.6:
        return {
            "decision": "Rejected",
            "reason": "Existing debt load exceeds traditional underwriting threshold.",
        }
    return {"decision": "Approved", "reason": "Bureau history present and within thresholds."}


def data_source_signals(p: MSMEProfile) -> list[dict]:
    return [
        {
            "source": "Account Aggregator",
            "signal": f"Monthly inflow Rs {p.avg_monthly_inflow:,.0f}; volatility {p.inflow_volatility:.0%}",
            "status": "Connected",
        },
        {
            "source": "GST",
            "signal": f"{p.gst_filing_streak_months} month filing streak; turnover growth {p.gst_turnover_growth_pct:+.0f}%",
            "status": "Connected",
        },
        {
            "source": "UPI",
            "signal": f"{p.upi_txn_count_monthly} monthly txns across {p.unique_counterparties} counterparties",
            "status": "Connected",
        },
        {
            "source": "EPFO",
            "signal": f"{p.employees} employee-linked payroll footprint",
            "status": "Synthetic",
        },
        {
            "source": "Bureau",
            "signal": "History present" if p.has_bureau_history else "No bureau file",
            "status": "Present" if p.has_bureau_history else "Thin-file",
        },
    ]


def policy_guardrails(
    p: MSMEProfile,
    pillars: dict[str, int],
    total: int,
    policy: dict,
) -> list[dict]:
    return [
        {
            "control": "Consent data boundary",
            "status": "Pass",
            "detail": p.consent_status,
        },
        {
            "control": "Debt-load cap",
            "status": "Pass" if p.outstanding_debt_to_inflow <= 0.6 else "Watch",
            "detail": f"Outstanding debt is {p.outstanding_debt_to_inflow:.0%} of monthly inflow.",
        },
        {
            "control": "Counterparty concentration",
            # Unknown is not a pass. If the share was never supplied (0), the
            # single-buyer dependency risk is unverified and routes to review
            # rather than being silently treated as a measured low value.
            "status": (
                "Watch"
                if p.top_counterparty_share_pct >= CONCENTRATION_WATCH_THRESHOLD_PCT
                else "Pass"
                if p.top_counterparty_share_pct > 0
                else "Review"
            ),
            "detail": (
                f"{p.top_counterparty_share_pct:.0f}% of digital inflow value depends on a single "
                "counterparty; a payment disruption from that buyer would directly hit this "
                f"borrower's cash flow, so the eligible limit is reduced {(1 - CONCENTRATION_LIMIT_HAIRCUT):.0%} "
                "below the grade-only amount."
                if p.top_counterparty_share_pct >= CONCENTRATION_WATCH_THRESHOLD_PCT
                else f"No single counterparty exceeds {CONCENTRATION_WATCH_THRESHOLD_PCT}% of digital inflow "
                f"value ({p.top_counterparty_share_pct:.0f}% max); no limit reduction applied."
                if p.top_counterparty_share_pct > 0
                else "Counterparty concentration not supplied for this application; no limit reduction applied."
            ),
        },
        *(
            [
                {
                    "control": "GST-vs-bank turnover reconciliation",
                    "status": (
                        "Review"
                        if abs(p.gst_bank_divergence_pct) >= DIVERGENCE_WATCH_THRESHOLD_PCT
                        else "Pass"
                    ),
                    "detail": (
                        f"GST-declared turnover runs {p.gst_bank_divergence_pct:+.0f}% versus "
                        "bank-observed inflow. "
                        + (
                            "Declared turnover materially exceeds what the bank account "
                            "sees -- reconcile before relying on GST momentum (possible "
                            "inflation or receipts outside the monitored account)."
                            if p.gst_bank_divergence_pct >= DIVERGENCE_WATCH_THRESHOLD_PCT
                            else "Bank inflows materially exceed declared turnover -- "
                            "reconcile for undisclosed activity."
                            if p.gst_bank_divergence_pct <= -DIVERGENCE_WATCH_THRESHOLD_PCT
                            else "Within the +/-"
                            f"{DIVERGENCE_WATCH_THRESHOLD_PCT}% reconciliation band."
                        )
                    ),
                }
            ]
            if p.gst_bank_divergence_pct is not None
            else []
        ),
        {
            "control": "Conduct signal",
            "status": "Pass" if p.cheque_bounce_rate <= 0.08 else "Watch",
            "detail": f"Cheque bounce rate is {p.cheque_bounce_rate:.0%}; discipline pillar {pillars['discipline']}/20.",
        },
        {
            "control": "Explainability invariant",
            "status": "Pass",
            "detail": "Every decision returns ranked rule reasons plus exact Shapley feature attribution.",
        },
        {
            "control": "Human review lane",
            "status": "Review" if policy["decision"] == "Review" else "Pass",
            "detail": policy["reason"],
        },
        {
            "control": "PD guardrail",
            "status": "Review" if policy["pd_guardrail_triggered"] else "Pass",
            "detail": (
                f"Proxy PD {policy['pd_estimate']:.1%}; human-review threshold "
                f"{policy['pd_review_threshold']:.1%}. The proxy can route to review but never auto-declines."
            ),
        },
        {
            "control": "Data sufficiency",
            "status": "Watch" if policy["missing_data_sources"] else "Pass",
            "detail": (
                f"Source(s) not connected: {', '.join(policy['missing_data_sources'])}. Affected pillars "
                "reflect a missing signal, not confirmed risk, and cannot drive an auto-decision."
                if policy["missing_data_sources"]
                else "Every pillar is backed by a connected source."
            ),
        },
    ]


def decision_path(
    p: MSMEProfile,
    total: int,
    grade: str,
    traditional: dict,
    policy: dict,
) -> list[dict]:
    return [
        {
            "stage": "Traditional bureau screen",
            "decision": traditional["decision"],
            "evidence": traditional["reason"],
        },
        {
            "stage": "Alternate-data health card",
            "decision": policy["decision"],
            "evidence": (
                f"Composite score {total}/100, grade {grade}, {risk_band_for(grade).lower()}; "
                f"proxy PD {policy['pd_estimate']:.1%}."
            ),
        },
        {
            "stage": "Credit-line recommendation",
            "decision": "Limit generated" if eligible_limit(total, p) > 0 else "No limit",
            "evidence": f"Eligible working-capital limit Rs {eligible_limit(total, p):,.0f}.",
        },
    ]


def apply_decision_policy(
    grade: str,
    pd_estimate: float | None,
    pd_threshold: float | None,
    *,
    missing_data_sources: frozenset[str] = frozenset(),
) -> dict:
    """Separate descriptive score, risk estimate and lending policy.

    The public proxy PD may route a nominally bankable file to human review,
    but it is never allowed to auto-decline an MSME across domains. Grades D/E
    remain rule-policy declines; grade C is always reviewed.

    A pillar computed from a source the caller never connected (as opposed to
    a source that was connected and genuinely reported a weak signal) is a
    missing input, not an observed risk. Silently scoring that pillar at its
    worst-case floor and then auto-approving or auto-declining on it would
    penalise absence as if it were confirmed risk, so any missing pillar
    source always routes to review regardless of what the score/PD say.
    """
    estimate = float(pd_estimate) if pd_estimate is not None else 0.0
    threshold = float(pd_threshold) if pd_threshold is not None else 1.0
    pd_triggered = pd_estimate is not None and estimate >= threshold

    if missing_data_sources:
        decision, route = "Review", "insufficient_data_review"
        reason = (
            f"Source(s) not connected for this application: {', '.join(sorted(missing_data_sources))}. "
            "The affected pillar(s) reflect a missing signal, not confirmed risk, so this cannot be "
            "auto-approved or auto-declined; connect the source or have an underwriter verify it manually."
        )
    elif grade in ("D", "E"):
        decision, route = "Rejected", "policy_decline"
        reason = f"Grade {grade} is outside the bankable scorecard range."
    elif grade == "C":
        decision, route = "Review", "mandatory_human_review"
        reason = "Grade C is bankable only with conditions and mandatory underwriter review."
    elif pd_triggered:
        decision, route = "Review", "model_disagreement_review"
        reason = (
            "The scorecard is bankable but the cross-domain proxy PD crossed its calibrated "
            "review threshold; an underwriter must resolve the disagreement."
        )
    else:
        decision, route = "Approved", "fast_track_eligible"
        reason = "Grade A/B and proxy PD below the review threshold; eligible for fast-track approval."
    return {
        "version": "policy-v2-score-pd-separation",
        "decision": decision,
        "route": route,
        "reason": reason,
        "pd_estimate": estimate,
        "pd_review_threshold": threshold,
        "pd_guardrail_triggered": pd_triggered,
        "auto_decline_from_proxy_model": False,
        "missing_data_sources": sorted(missing_data_sources),
    }


# ---------------------------------------------------------------------------
# Conduct-prior adjustment (Phase A2).
#
# The trained cross-domain PD sees only discipline/leverage/liquidity because
# the public proxy has no honest analog for GST momentum or UPI footprint.
# Until dated IDBI sandbox outcomes let those coefficients be *fitted*, they
# enter the risk path as capped, disclosed expert priors: a business growing
# its declared turnover and transacting broadly is treated as somewhat lower
# risk than its conduct pillars alone imply, and vice versa. The adjustment is
# a bounded logit offset -- it can route to review, it can never auto-decline
# (policy invariant), and both the raw and adjusted PDs ship in the payload so
# the effect is always visible and reversible.
PRIOR_BETA_MOMENTUM = 0.15        # logits per full pillar deviation from neutral
PRIOR_BETA_FOOTPRINT = 0.15
PRIOR_TOTAL_CAP_LOGIT = 0.30      # |total offset| never exceeds this
PRIOR_NEUTRAL_PILLAR = 10         # pillar midpoint treated as "no information"


def conduct_prior_adjustment(pillars: dict[str, int], pd_estimate: float | None) -> dict | None:
    """Bounded expert-prior PD adjustment from the two unfitted pillars."""
    if pd_estimate is None:
        return None
    import math

    momentum_dev = (pillars["momentum"] - PRIOR_NEUTRAL_PILLAR) / PRIOR_NEUTRAL_PILLAR
    footprint_dev = (pillars["digital_footprint"] - PRIOR_NEUTRAL_PILLAR) / PRIOR_NEUTRAL_PILLAR
    raw_offset = -(PRIOR_BETA_MOMENTUM * momentum_dev + PRIOR_BETA_FOOTPRINT * footprint_dev)
    # Favorable-only by design: observed strong momentum/footprint may reduce
    # the PD, but a weak or thin signal never inflates it -- absence of digital
    # visibility is a missing/weak signal, not confirmed risk (the same
    # doctrine as missing-source review routing), and the descriptive pillars,
    # EWS flags and grade policy already carry the downside.
    offset = max(-PRIOR_TOTAL_CAP_LOGIT, min(0.0, raw_offset))
    bounded = min(max(float(pd_estimate), 1e-6), 1 - 1e-6)
    adjusted = 1.0 / (1.0 + math.exp(-(math.log(bounded / (1 - bounded)) + offset)))
    return {
        "basis": (
            "Capped, favorable-only expert prior for the momentum/digital-footprint pillars, "
            "which the cross-domain training data cannot fit; coefficients become trainable "
            "the moment dated IDBI sandbox outcomes arrive."
        ),
        "betas_logit": {"momentum": PRIOR_BETA_MOMENTUM, "digital_footprint": PRIOR_BETA_FOOTPRINT},
        "total_cap_logit": PRIOR_TOTAL_CAP_LOGIT,
        "asymmetry": "favorable_only; weak alternate-data signals never increase PD",
        "offset_logit": round(offset, 4),
        "pd_model": round(float(pd_estimate), 4),
        "pd_adjusted": round(adjusted, 4),
        "policy_note": "The adjusted PD can route to human review; it can never auto-decline.",
    }


IMPROVEMENT_ACTIONS = {
    "liquidity": "Smooth out month-to-month cash inflow swings (e.g. staggered receivables) to lower volatility.",
    "discipline": "Reduce cheque bounces and keep GST filings continuous, month after month.",
    "momentum": "Grow GST-reported turnover consistently over the next few filing cycles.",
    "leverage": "Pay down outstanding debt relative to monthly inflow.",
    "digital_footprint": "Route more transactions through UPI and widen the base of counterparties paid/received from.",
}

# Borrower-facing vernacular (Phase A5): the health card is for the MSME owner
# as much as the underwriter, and PS3 is a financial-inclusion track. Hindi
# renderings of every fixed borrower-facing string ship alongside English.
PILLAR_LABELS_HI = {
    "liquidity": "तरलता",
    "discipline": "अनुशासन",
    "momentum": "कारोबार वृद्धि",
    "leverage": "ऋण-भार",
    "digital_footprint": "डिजिटल उपस्थिति",
}

IMPROVEMENT_ACTIONS_HI = {
    "liquidity": "मासिक नक़दी-प्रवाह के उतार-चढ़ाव कम करें (जैसे प्राप्तियाँ किश्तों में लें) ताकि अस्थिरता घटे।",
    "discipline": "चेक बाउंस कम करें और जीएसटी फ़ाइलिंग हर महीने लगातार बनाए रखें।",
    "momentum": "अगले कुछ फ़ाइलिंग चक्रों में जीएसटी-घोषित कारोबार लगातार बढ़ाएँ।",
    "leverage": "मासिक आमदनी की तुलना में बकाया ऋण घटाएँ।",
    "digital_footprint": "अधिक लेनदेन यूपीआई से करें और लेनदेन करने वाले पक्षों का दायरा बढ़ाएँ।",
}

STRENGTH_WORD = {"en": "Strong", "hi": "मज़बूत"}
WATCH_WORD = {"en": "Watch", "hi": "निगरानी"}

IMPROVEMENT_STEP = 5  # assumed achievable pillar-point gain from acting on the suggestion


def improvement_plan(pillars: dict[str, int], p: MSMEProfile) -> dict | None:
    """What would move this business to the next grade, and by how much."""
    current_total = sum(pillars.values())
    current_grade = grade_for(current_total)
    if current_grade == "A":
        return None

    weakest_pillar = min(pillars, key=pillars.get)
    improved_value = min(PILLAR_MAX, pillars[weakest_pillar] + IMPROVEMENT_STEP)
    potential_total = current_total - pillars[weakest_pillar] + improved_value
    potential_grade = grade_for(potential_total)
    potential_limit = eligible_limit(potential_total, p)
    current_limit = eligible_limit(current_total, p)

    return {
        "focus_pillar": weakest_pillar,
        "action": IMPROVEMENT_ACTIONS[weakest_pillar],
        "action_hi": IMPROVEMENT_ACTIONS_HI[weakest_pillar],
        "potential_grade": potential_grade,
        "potential_eligible_limit": potential_limit,
        "limit_increase": round(potential_limit - current_limit, 2),
    }


def reason_codes(pillars: dict[str, int]) -> list[str]:
    reasons = []
    for name, value in pillars.items():
        label = name.replace("_", " ").title()
        if value >= 16:
            reasons.append(f"Strong: {label} ({value}/20)")
        elif value <= 8:
            reasons.append(f"Watch: {label} ({value}/20)")
    return reasons


def reason_codes_vernacular(pillars: dict[str, int]) -> list[dict]:
    """Bilingual borrower-facing reason codes (English + Hindi)."""
    reasons = []
    for name, value in pillars.items():
        if 8 < value < 16:
            continue
        kind = STRENGTH_WORD if value >= 16 else WATCH_WORD
        label_en = name.replace("_", " ").title()
        reasons.append({
            "pillar": name,
            "en": f"{kind['en']}: {label_en} ({value}/20)",
            "hi": f"{kind['hi']}: {PILLAR_LABELS_HI[name]} ({value}/20)",
        })
    return reasons


# Descriptive labels only -- our own category names for the kind of signals
# banks commonly monitor under SMA/NPA early-warning frameworks (cheque/bill
# returns, GST filing lapses, turnover decline, leverage build-up). This is
# not a reproduction of any specific RBI circular text and carries no
# regulatory certification; it exists so an underwriter sees a recognisable
# monitoring theme alongside the pillar score, not just internal jargon.
EWS_TRIGGER_CATEGORIES = {
    "liquidity": "Cash-Flow Stability",
    "discipline": "Cheque Discipline & GST Filing",
    "momentum": "Turnover Momentum",
    "leverage": "Leverage / Debt-Servicing",
    "digital_footprint": "Digital Transaction Footprint",
}


def ews_style_signals(pillars: dict[str, int]) -> list[dict]:
    signals = []
    for pillar, value in pillars.items():
        if value >= 16:
            status = "Clear"
        elif value <= 8:
            status = "Flagged"
        else:
            status = "Monitor"
        signals.append({
            "status": status,
            "control": EWS_TRIGGER_CATEGORIES[pillar],
            "detail": f"{pillar.replace('_', ' ').title()} pillar: {value}/20.",
        })
    return signals


_NEXT_ACTION_BY_PILLAR = {
    "discipline": "Request the latest 3-month bank statement and confirm cheque-bounce reasons directly with the borrower.",
    "liquidity": "Request updated cash-flow projections and confirm the seasonal inflow pattern.",
    "leverage": "Request the current liability schedule and verify outstanding debt against inflow.",
    "momentum": "Request the latest GST returns to confirm the turnover trend is continuing.",
    "digital_footprint": "Confirm counterparty concentration is not a single-buyer dependency risk.",
}

_NEXT_ACTION_BY_PILLAR_HI = {
    "discipline": "पिछले 3 महीनों का बैंक स्टेटमेंट लें और चेक बाउंस के कारण सीधे उधारकर्ता से पुष्ट करें।",
    "liquidity": "ताज़ा नक़दी-प्रवाह अनुमान लें और मौसमी आमदनी के पैटर्न की पुष्टि करें।",
    "leverage": "वर्तमान देनदारियों की सूची लें और आमदनी की तुलना में बकाया ऋण सत्यापित करें।",
    "momentum": "ताज़ा जीएसटी रिटर्न लेकर पुष्टि करें कि कारोबार की वृद्धि जारी है।",
    "digital_footprint": "पुष्टि करें कि किसी एक ख़रीदार पर निर्भरता का जोखिम नहीं है।",
}


def next_best_action(
    pillars: dict[str, int],
    policy: dict,
    traditional: dict,
    p: MSMEProfile | None = None,
) -> dict:
    """Deterministic, rule-based recommendation for the reviewing underwriter.

    Derived entirely from already-computed pillar and policy signals -- not a
    generative or LLM suggestion, so it is reproducible and auditable the same
    way the rest of the decision path is. Ships English + Hindi.
    """
    weakest_pillar = min(pillars, key=pillars.get)
    weakest_label = weakest_pillar.replace("_", " ")

    if policy.get("route") == "insufficient_data_review":
        missing = ", ".join(policy["missing_data_sources"])
        return {
            "action": (
                f"Connect or manually verify: {missing}. "
                "Do not approve or decline until the missing source is confirmed."
            ),
            "action_hi": (
                f"पहले यह स्रोत जोड़ें या स्वयं सत्यापित करें: {missing}। "
                "स्रोत की पुष्टि से पहले न स्वीकृत करें, न अस्वीकृत।"
            ),
            "urgency": "high",
        }

    if policy["decision"] == "Rejected":
        return {
            "action": "Decline per policy; no further underwriter action required.",
            "action_hi": "नीति के अनुसार अस्वीकृत; आगे किसी कार्रवाई की आवश्यकता नहीं।",
            "urgency": "none",
        }

    # A material GST-vs-bank divergence outranks routine review actions: it is
    # the classic looks-fine-but-failing red flag and must be reconciled first.
    if (
        p is not None
        and p.gst_bank_divergence_pct is not None
        and abs(p.gst_bank_divergence_pct) >= DIVERGENCE_WATCH_THRESHOLD_PCT
    ):
        return {
            "action": (
                f"Reconcile GST-declared turnover with bank inflows ({p.gst_bank_divergence_pct:+.0f}% "
                "divergence) against invoices and the full account list before any sanction."
            ),
            "action_hi": (
                f"जीएसटी-घोषित कारोबार और बैंक आमदनी का मिलान करें ({p.gst_bank_divergence_pct:+.0f}% "
                "अंतर) -- मंज़ूरी से पहले चालान और सभी खातों से पुष्टि करें।"
            ),
            "urgency": "high",
        }

    if policy["decision"] == "Review" and policy.get("route") == "model_disagreement_review":
        return {
            "action": (
                f"Resolve the scorecard/model disagreement: re-verify the {weakest_label} "
                "inputs against source documents before sign-off."
            ),
            "action_hi": (
                f"स्कोरकार्ड और मॉडल के मतभेद को सुलझाएँ: {PILLAR_LABELS_HI[weakest_pillar]} "
                "से जुड़े आँकड़े मूल दस्तावेज़ों से दोबारा जाँचें।"
            ),
            "urgency": "high",
        }

    if policy["decision"] == "Review":
        return {
            "action": _NEXT_ACTION_BY_PILLAR[weakest_pillar],
            "action_hi": _NEXT_ACTION_BY_PILLAR_HI[weakest_pillar],
            "urgency": "medium",
        }

    if traditional["decision"] == "Rejected":
        return {
            "action": "Document the bureau-rejection reversal rationale in the credit file for the audit trail.",
            "action_hi": "ब्यूरो-अस्वीकृति को पलटने का आधार ऑडिट हेतु क्रेडिट फ़ाइल में दर्ज करें।",
            "urgency": "low",
        }

    return {
        "action": f"Approve per policy; monitor {weakest_label} at the next quarterly review.",
        "action_hi": (
            f"नीति के अनुसार स्वीकृत; अगली तिमाही समीक्षा में {PILLAR_LABELS_HI[weakest_pillar]} "
            "पर नज़र रखें।"
        ),
        "urgency": "low",
    }


def score_profile(
    p: MSMEProfile,
    record_audit: bool = True,
    *,
    missing_data_sources: frozenset[str] = frozenset(),
) -> dict:
    pillars = {
        "liquidity": score_liquidity(p),
        "discipline": score_discipline(p),
        "momentum": score_momentum(p),
        "leverage": score_leverage(p),
        "digital_footprint": score_digital_footprint(p),
    }
    total = sum(pillars.values())
    grade = grade_for(total)
    traditional = traditional_verdict(p)

    from ml import explain, pd_policy_threshold  # local import avoids circular import at module load

    model_explanation = explain(p, pillars)
    # Phase A2: momentum/footprint enter the risk path as a capped, disclosed
    # expert prior on the trained PD (fitted coefficients await sandbox
    # outcomes). Policy routing uses the adjusted PD; both values ship.
    prior = conduct_prior_adjustment(pillars, model_explanation.get("pd_estimate"))
    if prior is not None:
        model_explanation["conduct_prior"] = prior
    policy_pd = prior["pd_adjusted"] if prior is not None else model_explanation.get("pd_estimate")
    policy = apply_decision_policy(
        grade,
        policy_pd,
        pd_policy_threshold(),
        missing_data_sources=missing_data_sources,
    )
    alternate_data_decision = policy["decision"]
    result = {
        "name": p.name,
        "profile": {
            "sector": p.sector,
            "district": p.district,
            "gender": p.gender or "Unavailable",
            "vintage_months": p.vintage_months,
            "employees": p.employees,
            "has_bureau_history": p.has_bureau_history,
        },
        "score": total,
        "grade": grade,
        "risk_band": risk_band_for(grade),
        "pillars": pillars,
        "eligible_limit": eligible_limit(total, p),
        "limit_basis": limit_basis(total, p),
        "reasons": reason_codes(pillars),
        "reasons_vernacular": reason_codes_vernacular(pillars),
        "traditional": traditional,
        "alternate_data_decision": alternate_data_decision,
        "policy": policy,
        "improvement_plan": improvement_plan(pillars, p),
        "data_sources": data_source_signals(p),
        "policy_guardrails": policy_guardrails(p, pillars, total, policy),
        "decision_path": decision_path(p, total, grade, traditional, policy),
        "ews_signals": ews_style_signals(pillars),
        "next_best_action": next_best_action(pillars, policy, traditional, p),
    }

    from agent_memo import generate_memo
    import audit_log

    result["ml"] = model_explanation
    result["pd_estimate"] = result["ml"].get("pd_estimate")
    result["memo"] = generate_memo(result)
    if record_audit:
        audit_log.record(result)
    return result
