"""
forecast_engine.py — Rolling cash-position projection (Phase 3 / P3)

Deterministic best-estimate daily balance timeline:
  - Each unpaid invoice contributes cash on (due_date + expected_delay)
  - Each pending payable deducts cash on its due_date
  - Cumulative sum over FORECAST_HORIZON_DAYS
  - First negative day → first_shortfall_date
"""

from __future__ import annotations

import sys, os
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import FORECAST_HORIZON_DAYS, DB_PATH
from forecasting.behaviour_model import LatenessProfile


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class ForecastResult:
    dates:                  list[str]       # ISO-8601 date strings, length = HORIZON
    daily_balance:          list[float]     # Deterministic daily cumulative balance
    daily_inflows:          list[float]     # Expected cash in per day
    daily_outflows:         list[float]     # Expected cash out per day
    starting_balance:       float
    ending_balance:         float
    first_shortfall_date:   str | None      # First day balance < 0 (None if never)
    days_to_shortfall:      int | None      # Days from today to shortfall (None if never)
    total_ar:               float           # Total accounts receivable outstanding
    total_ap:               float           # Total accounts payable pending


# ── Core forecast ─────────────────────────────────────────────────────────────

def run_forecast(
    starting_balance: float,
    profiles: dict[int, LatenessProfile],
    db_path: str = DB_PATH,
) -> ForecastResult:
    """
    Build a deterministic 90-day cash-flow timeline.

    Args:
        starting_balance: Current bank balance (₹)
        profiles:         Customer lateness profiles from behaviour_model
        db_path:          SQLite database path

    Returns:
        ForecastResult with daily balance array and shortfall info
    """
    from db.database import get_unpaid_invoices, get_pending_payables

    today    = datetime.today().date()
    horizon  = FORECAST_HORIZON_DAYS
    dates    = [(today + timedelta(days=i)) for i in range(horizon)]
    date_strs = [d.strftime("%Y-%m-%d") for d in dates]

    inflows  = np.zeros(horizon)
    outflows = np.zeros(horizon)

    invoices = get_unpaid_invoices(db_path)
    payables = get_pending_payables(db_path)

    total_ar = sum(inv["amount"] for inv in invoices)
    total_ap = sum(pay["amount"] for pay in payables)

    # ── Schedule invoice inflows ──────────────────────────────────────────────
    for inv in invoices:
        cid     = inv["customer_id"]
        profile = profiles.get(cid)
        delay   = profile.expected_delay_days if profile else 15.0  # fallback

        due_date = datetime.strptime(inv["due_date"], "%Y-%m-%d").date()
        expected_pay_date = due_date + timedelta(days=int(round(delay)))

        day_idx = (expected_pay_date - today).days
        if 0 <= day_idx < horizon:
            inflows[day_idx] += inv["amount"]

    # ── Schedule payable outflows ─────────────────────────────────────────────
    for pay in payables:
        due_date = datetime.strptime(pay["due_date"], "%Y-%m-%d").date()
        day_idx  = (due_date - today).days
        if 0 <= day_idx < horizon:
            outflows[day_idx] += pay["amount"]

    # ── Cumulative balance ────────────────────────────────────────────────────
    net_flow      = inflows - outflows
    daily_balance = starting_balance + np.cumsum(net_flow)

    # ── Find first shortfall ──────────────────────────────────────────────────
    shortfall_days = np.where(daily_balance < 0)[0]
    first_shortfall_date = None
    days_to_shortfall    = None

    if len(shortfall_days) > 0:
        idx = int(shortfall_days[0])
        first_shortfall_date = date_strs[idx]
        days_to_shortfall    = idx

    return ForecastResult(
        dates=date_strs,
        daily_balance=daily_balance.tolist(),
        daily_inflows=inflows.tolist(),
        daily_outflows=outflows.tolist(),
        starting_balance=starting_balance,
        ending_balance=float(daily_balance[-1]),
        first_shortfall_date=first_shortfall_date,
        days_to_shortfall=days_to_shortfall,
        total_ar=total_ar,
        total_ap=total_ap,
    )


if __name__ == "__main__":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db = os.path.join(_root, DB_PATH)

    from forecasting.behaviour_model import build_lateness_profiles
    profiles = build_lateness_profiles(db)
    result   = run_forecast(500_000, profiles, db)

    print(f"Starting balance : ₹{result.starting_balance:,.0f}")
    print(f"Ending balance   : ₹{result.ending_balance:,.0f}")
    print(f"First shortfall  : {result.first_shortfall_date or 'None'} "
          f"(in {result.days_to_shortfall} days)" if result.days_to_shortfall is not None
          else f"First shortfall  : None")
    print(f"Total AR         : ₹{result.total_ar:,.0f}")
    print(f"Total AP         : ₹{result.total_ap:,.0f}")
