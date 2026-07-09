"""IDBI sandbox feed contracts and normalization.

The live demo still ships synthetic personas, but Stage 2 needs the same
scoring surface to accept consented AA/GST/UPI/EPFO-style payloads. This
module keeps raw feed handling outside the scoring engine and maps only the
derived underwriting features into `MSMEProfile`.
"""
from __future__ import annotations

from math import sqrt
from statistics import mean

from pydantic import BaseModel, Field

from scoring import MSMEProfile


class ProfileFeed(BaseModel):
    name: str
    sector: str = "General Trade"
    district: str = "Mumbai"
    gender: str | None = None
    vintage_months: int = 24


class AccountAggregatorFeed(BaseModel):
    monthly_inflows: list[float] = Field(default_factory=list)
    cheque_bounces: int = 0
    cheque_presentations: int = 0
    outstanding_debt: float = 0


class GSTFeed(BaseModel):
    filing_streak_months: int = 0
    trailing_6m_turnover: list[float] = Field(default_factory=list)


class UPIFeed(BaseModel):
    monthly_transaction_count: int = 0
    unique_counterparties: int = 0


class EPFOFeed(BaseModel):
    employees: int = 0


class BureauFeed(BaseModel):
    has_bureau_history: bool = True


class IDBISandboxPayload(BaseModel):
    profile: ProfileFeed
    account_aggregator: AccountAggregatorFeed
    gst: GSTFeed
    upi: UPIFeed
    epfo: EPFOFeed
    bureau: BureauFeed = Field(default_factory=BureauFeed)
    consent_id: str | None = None


def _coefficient_of_variation(values: list[float]) -> float:
    positives = [value for value in values if value > 0]
    if not positives:
        return 1.0
    avg = mean(positives)
    variance = sum((value - avg) ** 2 for value in positives) / len(positives)
    return round(min(sqrt(variance) / avg, 2.0), 4)


def _growth_pct(values: list[float]) -> float:
    positives = [value for value in values if value > 0]
    if len(positives) < 2:
        return 0.0
    first = positives[0]
    last = positives[-1]
    if first <= 0:
        return 0.0
    return round((last - first) / first * 100, 2)


def readiness(payload: IDBISandboxPayload) -> dict:
    sources = {
        "Account Aggregator": bool(payload.account_aggregator.monthly_inflows),
        "GST": payload.gst.filing_streak_months > 0 or bool(payload.gst.trailing_6m_turnover),
        "UPI": payload.upi.monthly_transaction_count > 0,
        "EPFO": payload.epfo.employees > 0,
        "Bureau": True,
    }
    connected = [name for name, ok in sources.items() if ok]
    return {
        "mode": "idbi_sandbox_payload",
        "consent_id_present": bool(payload.consent_id),
        "sources_connected": connected,
        "coverage_pct": round(len(connected) / len(sources) * 100, 1),
        "missing_sources": [name for name, ok in sources.items() if not ok],
    }


def to_profile(payload: IDBISandboxPayload) -> MSMEProfile:
    inflows = [value for value in payload.account_aggregator.monthly_inflows if value > 0]
    avg_inflow = mean(inflows) if inflows else 0
    cheque_presentations = max(payload.account_aggregator.cheque_presentations, 1)
    bounce_rate = payload.account_aggregator.cheque_bounces / cheque_presentations
    debt_to_inflow = payload.account_aggregator.outstanding_debt / avg_inflow if avg_inflow else 1

    return MSMEProfile(
        name=payload.profile.name,
        sector=payload.profile.sector,
        district=payload.profile.district,
        gender=payload.profile.gender,
        vintage_months=payload.profile.vintage_months,
        employees=payload.epfo.employees,
        avg_monthly_inflow=round(avg_inflow, 2),
        inflow_volatility=_coefficient_of_variation(inflows),
        cheque_bounce_rate=round(bounce_rate, 4),
        gst_filing_streak_months=payload.gst.filing_streak_months,
        gst_turnover_growth_pct=_growth_pct(payload.gst.trailing_6m_turnover),
        upi_txn_count_monthly=payload.upi.monthly_transaction_count,
        unique_counterparties=payload.upi.unique_counterparties,
        outstanding_debt_to_inflow=round(debt_to_inflow, 4),
        has_bureau_history=payload.bureau.has_bureau_history,
    )
