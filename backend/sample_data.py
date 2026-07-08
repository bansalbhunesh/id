"""Synthetic MSME personas for the demo (no real bank data)."""
from scoring import MSMEProfile

SAMPLE_PROFILES: dict[str, MSMEProfile] = {
    "ntc_hero": MSMEProfile(
        name="Shree Ganesh Textiles (New-to-Credit)",
        sector="Textiles",
        district="Surat",
        vintage_months=31,
        employees=18,
        avg_monthly_inflow=450000,
        inflow_volatility=0.18,
        cheque_bounce_rate=0.02,
        gst_filing_streak_months=18,
        gst_turnover_growth_pct=22,
        upi_txn_count_monthly=340,
        unique_counterparties=64,
        outstanding_debt_to_inflow=0.05,
        has_bureau_history=False,
        # No credit bureau history at all -> traditional scoring rejects this business outright.
        # Alternate data (GST streak, UPI velocity, low bounce rate) tells a different story.
    ),
    "steady_wholesaler": MSMEProfile(
        name="Patel Wholesale Traders",
        sector="Wholesale",
        district="Ahmedabad",
        vintage_months=84,
        employees=26,
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
        sector="Retail",
        district="Nagpur",
        vintage_months=52,
        employees=7,
        avg_monthly_inflow=180000,
        inflow_volatility=0.55,
        cheque_bounce_rate=0.14,
        gst_filing_streak_months=6,
        gst_turnover_growth_pct=-12,
        upi_txn_count_monthly=45,
        unique_counterparties=12,
        outstanding_debt_to_inflow=0.68,
    ),
    "borderline_improving": MSMEProfile(
        name="Sunrise Auto Parts",
        sector="Auto Components",
        district="Pune",
        vintage_months=46,
        employees=14,
        avg_monthly_inflow=310000,
        inflow_volatility=0.28,
        cheque_bounce_rate=0.06,
        gst_filing_streak_months=14,
        gst_turnover_growth_pct=15,
        upi_txn_count_monthly=95,
        unique_counterparties=22,
        outstanding_debt_to_inflow=0.42,
        has_bureau_history=True,
        # A middling grade with a clear single lever (leverage) -- good for
        # demoing the improvement-plan feature on a business that isn't
        # already rejected outright.
    ),
    "digitally_thin": MSMEProfile(
        name="Himalayan Handicrafts Co-op",
        sector="Handicrafts",
        district="Dehradun",
        vintage_months=64,
        employees=21,
        avg_monthly_inflow=95000,
        inflow_volatility=0.20,
        cheque_bounce_rate=0.03,
        gst_filing_streak_months=30,
        gst_turnover_growth_pct=5,
        upi_txn_count_monthly=18,
        unique_counterparties=6,
        outstanding_debt_to_inflow=0.15,
        has_bureau_history=False,
        # Disciplined and low-leverage, but a thin digital footprint (few
        # counterparties, low UPI volume) -- a different NTC story than the
        # ntc_hero case: healthy business, just not very digitally visible yet.
    ),
}
