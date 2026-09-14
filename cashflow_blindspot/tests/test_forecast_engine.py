"""
test_forecast_engine.py — Unit tests for forecast engine and Monte Carlo
"""

import sys, os
import pytest
import numpy as np

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_root, "backend"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_profile(cid: int, expected_delay: float = 10.0,
                   p_late: float = 0.5, confidence: str = "medium") -> object:
    from forecasting.behaviour_model import LatenessProfile
    return LatenessProfile(
        customer_id=cid,
        customer_name="TestCust",
        expected_delay_days=expected_delay,
        p_late=p_late,
        p25_delay=expected_delay - 5,
        p75_delay=expected_delay + 5,
        confidence=confidence,
        personal_hazard_offset=0.0,
        invoice_count=10,
        tier=2,
    )


def _make_invoice(cid: int, amount: float, due_in_days: int = 10) -> dict:
    from datetime import datetime, timedelta
    due = (datetime.today() + timedelta(days=due_in_days)).strftime("%Y-%m-%d")
    return {
        "id": 1, "customer_id": cid, "amount": amount,
        "due_date": due, "status": "unpaid",
        "customer_name": "TestCust", "issue_date": "2026-01-01",
    }


def _make_payable(amount: float, due_in_days: int = 20,
                  category: str = "fixed") -> dict:
    from datetime import datetime, timedelta
    due = (datetime.today() + timedelta(days=due_in_days)).strftime("%Y-%m-%d")
    return {
        "id": 1, "vendor_id": 1, "amount": amount,
        "due_date": due, "category": category, "status": "pending",
        "vendor_name": "TestVendor",
    }


# ── Forecast Engine Tests ─────────────────────────────────────────────────────

class TestForecastEngine:
    def test_positive_balance_no_shortfall(self):
        """Large starting balance with small payables → no shortfall."""
        from unittest.mock import patch
        from forecasting.forecast_engine import run_forecast
        profiles = {1: _make_profile(1, expected_delay=5.0)}
        invoices = [_make_invoice(1, 100_000, due_in_days=5)]
        payables = [_make_payable(50_000, due_in_days=20)]

        with patch("db.database.get_unpaid_invoices", return_value=invoices), \
             patch("db.database.get_pending_payables", return_value=payables):
            result = run_forecast(500_000, profiles, ":memory:")

        assert result.first_shortfall_date is None
        assert result.days_to_shortfall is None

    def test_shortfall_detected(self):
        """No income + large payable → shortfall detected."""
        from unittest.mock import patch
        from forecasting.forecast_engine import run_forecast
        profiles = {}
        invoices = []
        payables = [_make_payable(600_000, due_in_days=10)]

        with patch("db.database.get_unpaid_invoices", return_value=invoices), \
             patch("db.database.get_pending_payables", return_value=payables):
            result = run_forecast(100_000, profiles, ":memory:")

        assert result.first_shortfall_date is not None
        assert result.days_to_shortfall == 10

    def test_balance_array_length(self):
        """Daily balance array should match FORECAST_HORIZON_DAYS."""
        from unittest.mock import patch
        from forecasting.forecast_engine import run_forecast
        from config import FORECAST_HORIZON_DAYS
        profiles = {}

        with patch("db.database.get_unpaid_invoices", return_value=[]), \
             patch("db.database.get_pending_payables", return_value=[]):
            result = run_forecast(100_000, profiles, ":memory:")

        assert len(result.daily_balance) == FORECAST_HORIZON_DAYS
        assert len(result.dates) == FORECAST_HORIZON_DAYS

    def test_inflow_increases_balance(self):
        """An invoice payment should increase the balance on the expected day."""
        from unittest.mock import patch
        from forecasting.forecast_engine import run_forecast
        profiles = {1: _make_profile(1, expected_delay=0.0)}  # pays exactly on due date
        invoices = [_make_invoice(1, 50_000, due_in_days=10)]

        with patch("db.database.get_unpaid_invoices", return_value=invoices), \
             patch("db.database.get_pending_payables", return_value=[]):
            result = run_forecast(100_000, profiles, ":memory:")

        assert result.daily_balance[10] > result.daily_balance[9]

    def test_total_ar_and_ap(self):
        from unittest.mock import patch
        from forecasting.forecast_engine import run_forecast
        profiles = {}
        invoices = [_make_invoice(1, 75_000), _make_invoice(1, 25_000)]
        payables = [_make_payable(30_000), _make_payable(20_000)]

        with patch("db.database.get_unpaid_invoices", return_value=invoices), \
             patch("db.database.get_pending_payables", return_value=payables):
            result = run_forecast(0, profiles, ":memory:")

        assert result.total_ar == 100_000
        assert result.total_ap == 50_000


# ── Monte Carlo Tests ─────────────────────────────────────────────────────────

class TestMonteCarlo:
    def test_percentile_ordering(self):
        """P5 ≤ P25 ≤ P50 ≤ P75 ≤ P95 at every day."""
        from unittest.mock import patch
        from forecasting.monte_carlo import run_monte_carlo
        profiles = {1: _make_profile(1, expected_delay=15.0)}
        invoices = [_make_invoice(1, 80_000, due_in_days=15)]
        payables = [_make_payable(50_000, due_in_days=30)]

        with patch("db.database.get_unpaid_invoices", return_value=invoices), \
             patch("db.database.get_pending_payables", return_value=payables):
            mc = run_monte_carlo(200_000, profiles, ":memory:", n=500, seed=99)

        for i in range(0, 90, 10):
            assert mc.p5[i] <= mc.p25[i] + 0.01
            assert mc.p25[i] <= mc.p50[i] + 0.01
            assert mc.p50[i] <= mc.p75[i] + 0.01
            assert mc.p75[i] <= mc.p95[i] + 0.01

    def test_shortfall_prob_in_range(self):
        """Shortfall probabilities must be in [0, 1]."""
        from unittest.mock import patch
        from forecasting.monte_carlo import run_monte_carlo
        profiles = {}
        with patch("db.database.get_unpaid_invoices", return_value=[]), \
             patch("db.database.get_pending_payables", return_value=[]):
            mc = run_monte_carlo(100_000, profiles, ":memory:", n=100, seed=1)

        for p in mc.shortfall_prob:
            assert 0.0 <= p <= 1.0

    def test_no_invoices_no_payables(self):
        """With no cash flows, balance should stay flat."""
        from unittest.mock import patch
        from forecasting.monte_carlo import run_monte_carlo
        profiles = {}
        with patch("db.database.get_unpaid_invoices", return_value=[]), \
             patch("db.database.get_pending_payables", return_value=[]):
            mc = run_monte_carlo(100_000, profiles, ":memory:", n=100, seed=1)

        # Median should stay near starting balance (no inflows or outflows)
        assert abs(mc.p50[0] - 100_000) < 1
        assert mc.peak_shortfall_prob == 0.0

    def test_output_length(self):
        from unittest.mock import patch
        from forecasting.monte_carlo import run_monte_carlo
        from config import FORECAST_HORIZON_DAYS
        profiles = {}
        with patch("db.database.get_unpaid_invoices", return_value=[]), \
             patch("db.database.get_pending_payables", return_value=[]):
            mc = run_monte_carlo(100_000, profiles, ":memory:", n=100, seed=1)

        assert len(mc.dates) == FORECAST_HORIZON_DAYS
        assert len(mc.p50)   == FORECAST_HORIZON_DAYS
        assert len(mc.shortfall_prob) == FORECAST_HORIZON_DAYS
