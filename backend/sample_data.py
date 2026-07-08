"""Synthetic MSME personas for the demo (no real bank data)."""
from scoring import MSMEProfile

SAMPLE_PROFILES: dict[str, MSMEProfile] = {
    "ntc_hero": MSMEProfile(
        name="Shree Ganesh Textiles (New-to-Credit)",
        avg_monthly_inflow=450000,
        inflow_volatility=0.18,
        cheque_bounce_rate=0.02,
        gst_filing_streak_months=18,
        gst_turnover_growth_pct=22,
        upi_txn_count_monthly=340,
        unique_counterparties=64,
        outstanding_debt_to_inflow=0.05,
        # No credit bureau history at all -> traditional scoring rejects this business outright.
        # Alternate data (GST streak, UPI velocity, low bounce rate) tells a different story.
    ),
    "steady_wholesaler": MSMEProfile(
        name="Patel Wholesale Traders",
        avg_monthly_inflow=820000,
        inflow_volatility=0.12,
        cheque_bounce_rate=0.01,
        gst_filing_streak_months=42,
        gst_turnover_growth_pct=8,
        upi_txn_count_monthly=120,
        unique_counterparties=38,
        outstanding_debt_to_inflow=0.30,
    ),
    "stressed_retailer": MSMEProfile(
        name="City Corner Retail",
        avg_monthly_inflow=180000,
        inflow_volatility=0.55,
        cheque_bounce_rate=0.14,
        gst_filing_streak_months=6,
        gst_turnover_growth_pct=-12,
        upi_txn_count_monthly=45,
        unique_counterparties=12,
        outstanding_debt_to_inflow=0.68,
    ),
}
