"""
test_behaviour_model.py — Unit tests for the lateness prediction model
"""

import sys, os
import pytest

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_root, "backend"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_history(delays: list[float], customer_id: int = 1) -> list[dict]:
    """Build fake payment_history rows with given delay_days values."""
    from datetime import datetime, timedelta
    today = datetime.today()
    records = []
    for i, d in enumerate(delays):
        issue = (today - timedelta(days=30 * (i + 1))).strftime("%Y-%m-%d")
        records.append({
            "customer_id":   customer_id,
            "customer_name": "Test Customer",
            "expected_days": 30,
            "actual_days":   30 + d,
            "issue_date":    issue,
        })
    return records


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPersonalStats:
    def test_zero_delay_customer(self):
        from forecasting.behaviour_model import _personal_stats
        history = _make_history([0, 0, 0, 0, 0])
        mean, std, p25, p75 = _personal_stats(history)
        assert abs(mean) < 1.0, "Zero-delay customer should have near-zero mean"

    def test_always_late_customer(self):
        from forecasting.behaviour_model import _personal_stats
        history = _make_history([20, 22, 18, 25, 21])
        mean, std, p25, p75 = _personal_stats(history)
        assert mean > 15, "Always-late customer should have positive mean delay"
        assert p25 > 0, "25th percentile should be positive"

    def test_recency_weighting(self):
        """Recent invoices should have more weight than old ones."""
        from forecasting.behaviour_model import _personal_stats
        # Mostly late historically, but recent payments are on-time
        old_delays  = [30, 28, 25, 32, 29]   # very late
        new_delays  = [2, 1, -1]               # nearly on-time
        history_old = _make_history(old_delays)
        # Force old dates
        from datetime import datetime, timedelta
        today = datetime.today()
        for i, h in enumerate(history_old):
            h["issue_date"] = (today - timedelta(days=180 + 30 * i)).strftime("%Y-%m-%d")

        history_new = _make_history(new_delays)
        history = history_new + history_old

        mean, _, _, _ = _personal_stats(history)
        # With recency weighting, recent on-time payments should pull mean down
        assert mean < 25, f"Recency weighting should lower mean; got {mean:.1f}"


class TestBlending:
    def test_blend_pulls_toward_cohort(self):
        from forecasting.behaviour_model import _blend
        from config import MIN_INVOICES_PERSONAL
        personal = 40.0
        cohort   = 10.0
        # With only MIN_INVOICES_PERSONAL data points, should blend significantly
        blended = _blend(personal, cohort, n=MIN_INVOICES_PERSONAL)
        assert cohort < blended < personal, "Blended should be between personal and cohort"

    def test_blend_converges_to_personal_with_more_data(self):
        from forecasting.behaviour_model import _blend
        personal = 40.0
        cohort   = 10.0
        # With lots of data, blending factor → 0, result → personal
        blended_large = _blend(personal, cohort, n=100)
        blended_small = _blend(personal, cohort, n=5)
        assert blended_large > blended_small, "More data → closer to personal mean"

    def test_blend_identical_means(self):
        from forecasting.behaviour_model import _blend
        result = _blend(15.0, 15.0, n=10)
        assert abs(result - 15.0) < 0.01


class TestColdStartFallback:
    def test_new_customer_uses_cohort(self):
        from forecasting.behaviour_model import _compute_cohort_prior
        # Create some fake history
        all_history = [
            {"customer_id": 2, "actual_days": 45, "expected_days": 30},
            {"customer_id": 2, "actual_days": 50, "expected_days": 30},
            {"customer_id": 2, "actual_days": 40, "expected_days": 30},
        ]
        all_customers = [{"id": 2, "name": "Other", "industry": "retail", "region": "west"}]
        target = {"id": 1, "name": "NewCust", "industry": "retail", "region": "west"}
        mean, std, p25, p75 = _compute_cohort_prior(all_history, all_customers, target)
        # Delays: 15, 20, 10 → mean = 15
        assert abs(mean - 15.0) < 1.0

    def test_empty_history_fallback(self):
        from forecasting.behaviour_model import _compute_cohort_prior
        mean, std, p25, p75 = _compute_cohort_prior([], [], {"industry": "x"})
        assert isinstance(mean, float)  # Should not raise


class TestPLateProbability:
    def test_very_late_customer_high_p_late(self):
        from forecasting.behaviour_model import LatenessProfile
        from scipy.stats import norm
        from config import GRACE_PERIOD_DAYS
        mean_delay = 30.0
        std_delay  = 5.0
        p_late = 1.0 - norm.cdf(GRACE_PERIOD_DAYS, loc=mean_delay, scale=std_delay)
        assert p_late > 0.9, "Customer always 30 days late should have high p_late"

    def test_punctual_customer_low_p_late(self):
        from scipy.stats import norm
        from config import GRACE_PERIOD_DAYS
        mean_delay = -5.0   # pays early
        std_delay  = 3.0
        p_late = 1.0 - norm.cdf(GRACE_PERIOD_DAYS, loc=mean_delay, scale=std_delay)
        assert p_late < 0.1, "Early payer should have low p_late"
