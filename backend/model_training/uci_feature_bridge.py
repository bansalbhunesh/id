"""Training-side (UCI dataset) half of the universal-risk-feature bridge.

No public dataset of real Indian MSME GST/UPI/EPFO alternate-data with a
default outcome exists (that gap is exactly what the IDBI sandbox is for).
This bridge is the documented, honest workaround: reduce both domains to the
same small set of economically-equivalent risk concepts, train the outcome
relationship on the public proxy dataset, and apply the identical concept
definitions to the production feature space at inference time (see
../feature_bridge.py's `msme_pillars_to_universal`, which this module's
UNIVERSAL_FEATURES stays in lockstep with).

Named `uci_feature_bridge` (not `feature_bridge`) specifically so it never
collides on `sys.path` with the runtime module of the same concept name in
backend/feature_bridge.py.

Universal features (all 0-1, higher = lower risk):
  discipline -- repayment/conduct history
  leverage   -- debt relative to capacity
  liquidity  -- stability of cash/balance

Deliberately excluded:
  momentum -- rising credit-card bill amount (UCI) means *more borrowing*
              (higher risk) but rising GST turnover (MSME) means business
              growth (lower risk). The sign flips between domains, so there
              is no honest single mapping; it stays a descriptive-only
              pillar in the rule-based score (scoring.py) pending real GST
              trend data from the IDBI sandbox.
  digital_footprint -- UCI has no transaction-count/counterparty-breadth
              analog at all. Stays descriptive-only pending real UPI data.

Deliberately excluded from BOTH domains as model inputs: demographic fields
(age/sex/education/marital status in UCI; gender/district in MSMEProfile).
Fair-lending practice: never use protected/proxy-for-protected attributes as
risk-model inputs. They are monitored as *outcomes* only, via the approval-
rate parity checks in portfolio.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from feature_bridge import UNIVERSAL_FEATURES  # noqa: E402  (re-exported for callers of this module)

assert UNIVERSAL_FEATURES == ["discipline", "leverage", "liquidity"]


def uci_row_to_universal(row: dict, pay_cols: list[str], bill_cols: list[str], limit_col: str) -> dict[str, float]:
    pay_values = [row[c] for c in pay_cols]
    delinquency = sum(max(0.0, v) for v in pay_values) / len(pay_values)
    discipline = 1.0 - min(max(delinquency / 6.0, 0.0), 1.0)

    bill_values = [row[c] for c in bill_cols]
    limit = row[limit_col] or 1.0
    avg_bill = sum(bill_values) / len(bill_values)
    utilization = avg_bill / limit
    leverage = 1.0 - min(max(utilization, 0.0), 1.0)

    positive_bills = [v for v in bill_values if v > 0]
    if len(positive_bills) < 2:
        cv = 1.0
    else:
        mean_bill = sum(positive_bills) / len(positive_bills)
        variance = sum((v - mean_bill) ** 2 for v in positive_bills) / len(positive_bills)
        cv = min((variance ** 0.5) / mean_bill, 2.0) if mean_bill > 0 else 1.0
    liquidity = 1.0 - min(max(cv, 0.0), 1.0)

    return {"discipline": discipline, "leverage": leverage, "liquidity": liquidity}
