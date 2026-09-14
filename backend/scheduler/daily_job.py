"""
daily_job.py — Orchestrates the full pipeline (Phase 6 / Scheduler)

Runs the sequence:
  1. build_lateness_profiles()   → behaviour_model.py (P2)
  2. run_forecast()              → forecast_engine.py (P3)
  3. run_monte_carlo()           → monte_carlo.py (P3)
  4. generate_alert()            → alert_engine.py (P4)
  5. generate_suggestions()      → suggestion_engine.py (P5)

Returns a DailyJobResult bundle consumed by the Streamlit dashboard.

Production: triggered once daily by GCP Cloud Scheduler + Cloud Run.
Demo:       called on every dashboard load (st.rerun).
"""

from __future__ import annotations

import sys, os
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DB_PATH
from forecasting.behaviour_model import LatenessProfile, build_lateness_profiles
from forecasting.forecast_engine  import ForecastResult, run_forecast
from forecasting.monte_carlo      import MonteCarloResult, run_monte_carlo
from alerts.alert_engine          import AlertResult, generate_alert
from suggestions.suggestion_engine import SuggestionResult, generate_suggestions


# ── Result bundle ─────────────────────────────────────────────────────────────

@dataclass
class DailyJobResult:
    profiles:     dict[int, LatenessProfile]
    forecast:     ForecastResult
    monte_carlo:  MonteCarloResult
    alert:        AlertResult
    suggestions:  SuggestionResult
    starting_balance: float


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_daily_job(
    starting_balance: float,
    db_path: str = DB_PATH,
) -> DailyJobResult:
    """
    Single entry-point into the backend pipeline.

    Args:
        starting_balance: Current bank balance (₹), from dashboard sidebar
        db_path:          Path to SQLite database

    Returns:
        DailyJobResult bundle with all computed data for the dashboard
    """
    # P2 — Build per-customer lateness profiles
    profiles = build_lateness_profiles(db_path)

    # P3a — Deterministic best-estimate forecast
    forecast = run_forecast(starting_balance, profiles, db_path)

    # P3b — Monte Carlo probability bands
    mc = run_monte_carlo(starting_balance, profiles, db_path)

    # P4 — Alert tier
    # Use the Monte Carlo shortfall probability at the deterministic shortfall day
    if forecast.days_to_shortfall is not None:
        shortfall_prob = mc.shortfall_prob[forecast.days_to_shortfall]
    else:
        shortfall_prob = mc.peak_shortfall_prob

    alert = generate_alert(
        first_shortfall_date=forecast.first_shortfall_date,
        days_to_shortfall=forecast.days_to_shortfall,
        shortfall_probability=shortfall_prob,
    )

    # P5 — Suggestions & gap-closing optimization
    if forecast.first_shortfall_date and forecast.days_to_shortfall is not None:
        # Gap = magnitude of the most negative balance
        import numpy as np
        bal_arr = forecast.daily_balance
        min_bal = min(bal_arr)
        gap = abs(min_bal) if min_bal < 0 else 0.0
    else:
        gap = 0.0

    suggestions = generate_suggestions(
        shortfall_gap=gap,
        shortfall_date=forecast.first_shortfall_date,
        profiles=profiles,
        db_path=db_path,
    )

    return DailyJobResult(
        profiles=profiles,
        forecast=forecast,
        monte_carlo=mc,
        alert=alert,
        suggestions=suggestions,
        starting_balance=starting_balance,
    )


if __name__ == "__main__":
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db    = os.path.join(_root, DB_PATH)
    result = run_daily_job(500_000, db)

    print(f"\n{'='*60}")
    print(f"  {result.alert.emoji}  {result.alert.headline}")
    print(f"  {result.alert.detail}")
    print(f"\n  AR outstanding : ₹{result.forecast.total_ar:>12,.0f}")
    print(f"  AP pending     : ₹{result.forecast.total_ap:>12,.0f}")
    print(f"  Shortfall prob : {result.monte_carlo.peak_shortfall_prob:.1%}")
    print(f"\n  Top suggestion : {result.suggestions.invoice_suggestions[0].customer_name}"
          f" — ₹{result.suggestions.invoice_suggestions[0].amount:,.0f}"
          if result.suggestions.invoice_suggestions else "  No suggestions.")
    print(f"{'='*60}")
