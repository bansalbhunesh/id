"""IDBI sandbox feed contracts and normalization.

The public build ships synthetic personas, while the same scoring surface
also accepts consented AA/GST/UPI/EPFO-style payloads. This module keeps
raw feed handling outside the scoring engine and maps only the derived
underwriting features into `MSMEProfile`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import sqrt
from statistics import mean
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from scoring import MSMEProfile

NonNegativeFloat = Annotated[float, Field(ge=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class ProfileFeed(BaseModel):
    name: str
    sector: str = "General Trade"
    district: str = "Mumbai"
    gender: str | None = None
    vintage_months: int = Field(default=24, ge=0, le=600)


class AccountAggregatorFeed(BaseModel):
    monthly_inflows: list[NonNegativeFloat] = Field(default_factory=list)
    cheque_bounces: NonNegativeInt = 0
    cheque_presentations: NonNegativeInt = 0
    outstanding_debt: NonNegativeFloat = 0

    @model_validator(mode="after")
    def cheque_bounces_cannot_exceed_presentations(self):
        if self.cheque_bounces and self.cheque_presentations == 0:
            raise ValueError("cheque_presentations is required when cheque_bounces is positive")
        if self.cheque_bounces > self.cheque_presentations:
            raise ValueError("cheque_bounces cannot exceed cheque_presentations")
        return self


class GSTFeed(BaseModel):
    filing_streak_months: int = Field(default=0, ge=0, le=120)
    trailing_6m_turnover: list[NonNegativeFloat] = Field(default_factory=list)


class UPIFeed(BaseModel):
    monthly_transaction_count: NonNegativeInt = 0
    unique_counterparties: NonNegativeInt = 0
    # Share of monthly digital inflow value from the single largest counterparty.
    # 0 means not supplied, not "no concentration" -- the guardrail treats it as unknown.
    top_counterparty_share_pct: float = Field(default=0.0, ge=0, le=100)


class EPFOFeed(BaseModel):
    employees: NonNegativeInt = 0


class BureauFeed(BaseModel):
    has_bureau_history: bool = True


class ConsentRecord(BaseModel):
    """A real sandbox feed (unlike the public synthetic demo) must carry a
    purpose-bound, scoped, time-limited consent -- not just an opaque
    optional ID that's reported as present/absent and never checked."""

    consent_id: str = Field(min_length=1)
    purpose: Literal["msme_underwriting"]
    scope: list[str] = Field(min_length=1)
    granted_at: datetime
    expires_at: datetime
    status: Literal["active", "revoked"] = "active"

    @model_validator(mode="after")
    def expiry_after_grant(self):
        granted = self.granted_at if self.granted_at.tzinfo else self.granted_at.replace(tzinfo=timezone.utc)
        expires = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if expires <= granted:
            raise ValueError("consent.expires_at must be after consent.granted_at")
        if granted > now + timedelta(minutes=5):
            raise ValueError("consent.granted_at cannot be in the future")
        if expires - granted > timedelta(days=365):
            raise ValueError("consent validity cannot exceed 365 days")
        allowed = {"account_aggregator", "gst", "upi", "epfo", "bureau"}
        unknown = sorted(set(self.scope) - allowed)
        if unknown:
            raise ValueError(f"consent.scope contains unsupported sources: {unknown}")
        if len(self.scope) != len(set(self.scope)):
            raise ValueError("consent.scope cannot contain duplicates")
        if self.status != "active":
            raise ValueError("consent is revoked")
        return self

    def is_expired(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        expires = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return expires <= now


class IDBISandboxPayload(BaseModel):
    profile: ProfileFeed
    account_aggregator: AccountAggregatorFeed
    gst: GSTFeed
    upi: UPIFeed
    epfo: EPFOFeed
    bureau: BureauFeed = Field(default_factory=BureauFeed)
    consent: ConsentRecord

    @model_validator(mode="after")
    def consent_scope_covers_supplied_feeds(self):
        required = {"bureau"}
        if (
            self.account_aggregator.monthly_inflows
            or self.account_aggregator.cheque_presentations
            or self.account_aggregator.outstanding_debt
        ):
            required.add("account_aggregator")
        if self.gst.filing_streak_months or self.gst.trailing_6m_turnover:
            required.add("gst")
        if self.upi.monthly_transaction_count or self.upi.unique_counterparties:
            required.add("upi")
        if self.epfo.employees:
            required.add("epfo")
        missing = sorted(required - set(self.consent.scope))
        if missing:
            raise ValueError(f"consent.scope does not cover supplied feeds: {missing}")
        return self


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
        "consent_id_present": True,
        "consent_scope": payload.consent.scope,
        "consent_expired": payload.consent.is_expired(),
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
    consent_status = (
        f"Verified: consent {payload.consent.consent_id} for purpose '{payload.consent.purpose}', "
        f"scope {payload.consent.scope}, expires {payload.consent.expires_at.isoformat()}"
    )

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
        top_counterparty_share_pct=payload.upi.top_counterparty_share_pct,
        outstanding_debt_to_inflow=round(debt_to_inflow, 4),
        has_bureau_history=payload.bureau.has_bureau_history,
        consent_status=consent_status,
    )
