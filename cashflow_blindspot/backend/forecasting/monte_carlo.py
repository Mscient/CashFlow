"""
monte_carlo.py — Shortfall-date confidence band (Phase 3 / P3)

Runs MONTE_CARLO_RUNS simulation paths.
Each path samples payment arrival dates from each customer's
lateness distribution (modelled as Normal(expected_delay, std)).

Output:
  - P5 / P25 / P50 / P75 / P95 daily balance bands
  - Per-day shortfall probability P(balance < 0)
  - Most-likely shortfall date and probability
"""

from __future__ import annotations

import sys, os
from dataclasses import dataclass

import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import FORECAST_HORIZON_DAYS, MONTE_CARLO_RUNS, DB_PATH
from forecasting.behaviour_model import LatenessProfile


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class MonteCarloResult:
    dates:               list[str]    # ISO-8601 date strings
    p5:                  list[float]  # 5th percentile daily balance
    p25:                 list[float]  # 25th percentile
    p50:                 list[float]  # Median (50th percentile)
    p75:                 list[float]  # 75th percentile
    p95:                 list[float]  # 95th percentile
    shortfall_prob:      list[float]  # P(balance < 0) per day
    peak_shortfall_prob: float        # Max shortfall probability in horizon
    most_likely_shortfall_day: int | None  # Day index with highest P(shortfall)
    most_likely_shortfall_date: str | None # Corresponding date string
    n_runs:              int


# ── Simulation ────────────────────────────────────────────────────────────────

def run_monte_carlo(
    starting_balance: float,
    profiles: dict[int, LatenessProfile],
    db_path: str = DB_PATH,
    n: int = MONTE_CARLO_RUNS,
    seed: int = 42,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for cash-flow probability bands.

    Args:
        starting_balance: Current bank balance (₹)
        profiles:         Customer lateness profiles from behaviour_model
        db_path:          SQLite database path
        n:                Number of simulation runs (default 2000)
        seed:             Random seed for reproducibility

    Returns:
        MonteCarloResult with percentile bands and shortfall probabilities
    """
    from db.database import get_unpaid_invoices, get_pending_payables

    rng     = np.random.default_rng(seed)
    today   = datetime.today().date()
    horizon = FORECAST_HORIZON_DAYS

    invoices = get_unpaid_invoices(db_path)
    payables = get_pending_payables(db_path)

    # ── Pre-compute deterministic outflow schedule ────────────────────────────
    outflows = np.zeros(horizon)
    for pay in payables:
        due_date = datetime.strptime(pay["due_date"], "%Y-%m-%d").date()
        day_idx  = (due_date - today).days
        if 0 <= day_idx < horizon:
            outflows[day_idx] += pay["amount"]

    # ── For each invoice, build (day_idx_base, amount, mean_delay, std_delay) ─
    invoice_params = []
    for inv in invoices:
        cid     = inv["customer_id"]
        profile = profiles.get(cid)
        if profile:
            mean_delay = profile.expected_delay_days
            # Use IQR-based std: (p75 - p25) / 1.35 ≈ sigma for normal
            std_delay  = max((profile.p75_delay - profile.p25_delay) / 1.35, 1.0)
        else:
            mean_delay = 15.0
            std_delay  = 10.0

        due_date      = datetime.strptime(inv["due_date"], "%Y-%m-%d").date()
        base_day      = (due_date - today).days

        invoice_params.append((base_day, inv["amount"], mean_delay, std_delay))

    # ── Run n simulation paths (vectorised) ──────────────────────────────────
    # Shape: (n, horizon) — each row is one simulation path
    all_balances = np.empty((n, horizon))

    # Sample all delays at once: shape (n, num_invoices)
    num_invoices = len(invoice_params)

    if num_invoices > 0:
        delays_matrix = rng.normal(
            loc  = np.array([p[2] for p in invoice_params]),
            scale= np.array([p[3] for p in invoice_params]),
            size = (n, num_invoices),
        ).round().astype(int)

        for run_idx in range(n):
            inflows = np.zeros(horizon)
            for inv_idx, (base_day, amount, _, _) in enumerate(invoice_params):
                pay_day = base_day + delays_matrix[run_idx, inv_idx]
                if 0 <= pay_day < horizon:
                    inflows[pay_day] += amount

            net_flow = inflows - outflows
            all_balances[run_idx] = starting_balance + np.cumsum(net_flow)
    else:
        for run_idx in range(n):
            all_balances[run_idx] = starting_balance + np.cumsum(-outflows)

    # ── Compute percentile bands ──────────────────────────────────────────────
    p5  = np.percentile(all_balances, 5,  axis=0).tolist()
    p25 = np.percentile(all_balances, 25, axis=0).tolist()
    p50 = np.percentile(all_balances, 50, axis=0).tolist()
    p75 = np.percentile(all_balances, 75, axis=0).tolist()
    p95 = np.percentile(all_balances, 95, axis=0).tolist()

    # ── Shortfall probabilities ───────────────────────────────────────────────
    shortfall_prob = (all_balances < 0).mean(axis=0).tolist()

    peak_prob     = float(max(shortfall_prob))
    peak_day      = int(np.argmax(shortfall_prob)) if peak_prob > 0 else None

    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range(horizon)]

    return MonteCarloResult(
        dates=dates,
        p5=p5,
        p25=p25,
        p50=p50,
        p75=p75,
        p95=p95,
        shortfall_prob=shortfall_prob,
        peak_shortfall_prob=peak_prob,
        most_likely_shortfall_day=peak_day,
        most_likely_shortfall_date=dates[peak_day] if peak_day is not None else None,
        n_runs=n,
    )


if __name__ == "__main__":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db = os.path.join(_root, DB_PATH)

    from forecasting.behaviour_model import build_lateness_profiles
    profiles = build_lateness_profiles(db)
    mc = run_monte_carlo(500_000, profiles, db)

    print(f"Peak shortfall probability : {mc.peak_shortfall_prob:.1%}")
    print(f"Most likely shortfall date : {mc.most_likely_shortfall_date}")
    print(f"P50 balance day 30         : ₹{mc.p50[30]:,.0f}")
    print(f"P5  balance day 30         : ₹{mc.p5[30]:,.0f}")
    print(f"P95 balance day 30         : ₹{mc.p95[30]:,.0f}")
