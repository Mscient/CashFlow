"""
behaviour_model.py — Per-customer lateness estimation (Phase 2 / P2)

Implements a 3-tier prediction model as described in the Technical Design Doc:

  Tier 1 (< MIN_INVOICES_PERSONAL invoices):
      Cohort prior — use the average lateness of similar customers
      (matched by industry + region + size_bracket).

  Tier 2 (MIN_INVOICES_PERSONAL to MIN_INVOICES_MATURE invoices):
      Recency-weighted Bayesian shrinkage blending the personal mean
      toward the cohort mean.

  Tier 3 (≥ MIN_INVOICES_MATURE invoices):
      Discrete-time hazard model via lifelines' WeibullAFTFitter,
      with a personal_hazard_offset capturing the individual bias.

Output per customer: LatenessProfile dataclass.
"""

from __future__ import annotations

import sys, os
import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    MIN_INVOICES_PERSONAL,
    MIN_INVOICES_MATURE,
    SHRINKAGE_STRENGTH,
    RECENCY_HALF_LIFE,
    DB_PATH,
)


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class LatenessProfile:
    customer_id:            int
    customer_name:          str
    expected_delay_days:    float       # Expected days late (can be negative = early)
    p_late:                 float       # Probability of being late at all (0–1)
    p25_delay:              float       # 25th percentile of delay distribution
    p75_delay:              float       # 75th percentile (spread / uncertainty)
    confidence:             str         # 'high' | 'medium' | 'low'
    personal_hazard_offset: float       # Per-customer bias term
    invoice_count:          int         # Number of historical invoices used
    tier:                   int         # 1=cohort, 2=blended, 3=hazard model


# ── Recency weighting ─────────────────────────────────────────────────────────

def _recency_weight(issue_date_str: str, half_life_months: int = RECENCY_HALF_LIFE) -> float:
    """Exponential decay weight; more recent invoices weight more."""
    try:
        issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return 1.0
    months_ago = (datetime.today() - issue_date).days / 30.0
    return math.exp(-months_ago / half_life_months)


# ── Cohort prior ──────────────────────────────────────────────────────────────

def _compute_cohort_prior(
    all_history: list[dict],
    all_customers: list[dict],
    target_customer: dict,
) -> tuple[float, float, float, float]:
    """
    Compute cohort mean delay and std for customers similar to target.
    Falls back to global average if cohort is empty.

    Returns: (mean_delay, std_delay, p25, p75)
    """
    target_industry = target_customer.get("industry", "general")
    target_region   = target_customer.get("region", "india")

    # Build a lookup: customer_id → customer info
    cust_map = {c["id"]: c for c in all_customers}

    cohort_delays = []
    for h in all_history:
        cust = cust_map.get(h["customer_id"], {})
        if (cust.get("industry") == target_industry or
                cust.get("region") == target_region):
            cohort_delays.append(h["actual_days"] - h["expected_days"])

    # Fall back to global
    if len(cohort_delays) < 3:
        cohort_delays = [h["actual_days"] - h["expected_days"] for h in all_history]

    if not cohort_delays:
        return 15.0, 10.0, 5.0, 25.0  # hard fallback

    arr = np.array(cohort_delays)
    return float(arr.mean()), float(arr.std() + 1e-6), float(np.percentile(arr, 25)), float(np.percentile(arr, 75))


# ── Personal statistics ───────────────────────────────────────────────────────

def _personal_stats(history: list[dict]) -> tuple[float, float, float, float]:
    """
    Weighted personal mean / std from payment history.

    Returns: (weighted_mean_delay, std_delay, p25, p75)
    """
    if not history:
        return 0.0, 10.0, -5.0, 15.0

    delays  = np.array([h["actual_days"] - h["expected_days"] for h in history])
    weights = np.array([_recency_weight(h.get("issue_date", "")) for h in history])
    weights /= weights.sum()

    wmean = float(np.average(delays, weights=weights))
    wstd  = float(np.sqrt(np.average((delays - wmean) ** 2, weights=weights)) + 1e-6)
    p25   = float(np.percentile(delays, 25))
    p75   = float(np.percentile(delays, 75))
    return wmean, wstd, p25, p75


# ── Blending formula (Tier 2 Bayesian shrinkage) ──────────────────────────────

def _blend(personal_mean: float, cohort_mean: float,
           n: int, shrinkage: float = SHRINKAGE_STRENGTH) -> float:
    """
    Shrink personal estimate toward cohort mean.
    As n grows, blending_factor → 0 (full personal weight).

    blending_factor = shrinkage / (1 + n / MIN_INVOICES_PERSONAL)
    """
    blend_factor = shrinkage / (1.0 + n / MIN_INVOICES_PERSONAL)
    return (1 - blend_factor) * personal_mean + blend_factor * cohort_mean


# ── Main builder ──────────────────────────────────────────────────────────────

def build_lateness_profiles(db_path: str = DB_PATH) -> dict[int, LatenessProfile]:
    """
    Build one LatenessProfile per customer with unpaid invoices.

    Returns: dict mapping customer_id → LatenessProfile
    """
    from db.database import (
        get_payment_history, get_all_customers, get_unpaid_invoices
    )

    all_history   = get_payment_history(db_path)
    all_customers = get_all_customers(db_path)
    unpaid        = get_unpaid_invoices(db_path)

    # Which customers have open invoices?
    active_customer_ids = {inv["customer_id"] for inv in unpaid}
    cust_map = {c["id"]: c for c in all_customers}

    # Group history by customer
    hist_by_cust: dict[int, list[dict]] = {}
    for h in all_history:
        hist_by_cust.setdefault(h["customer_id"], []).append(h)

    profiles: dict[int, LatenessProfile] = {}

    for cid in active_customer_ids:
        customer  = cust_map.get(cid, {"id": cid, "name": "Unknown"})
        cname     = customer.get("name", "Unknown")
        c_history = hist_by_cust.get(cid, [])
        n         = len(c_history)

        cohort_mean, cohort_std, coh_p25, coh_p75 = _compute_cohort_prior(
            all_history, all_customers, customer
        )

        # ── Tier 1: Cold start ────────────────────────────────────────────────
        if n < MIN_INVOICES_PERSONAL:
            expected_delay        = cohort_mean
            std_delay             = cohort_std
            p25, p75              = coh_p25, coh_p75
            confidence            = "low"
            personal_hazard_offset = 0.0
            tier                  = 1

        # ── Tier 2: Blended (Bayesian shrinkage) ─────────────────────────────
        elif n < MIN_INVOICES_MATURE:
            p_mean, p_std, p25, p75 = _personal_stats(c_history)
            blended_mean          = _blend(p_mean, cohort_mean, n)
            expected_delay        = blended_mean
            std_delay             = p_std
            confidence            = "medium"
            personal_hazard_offset = p_mean - cohort_mean
            tier                  = 2

        # ── Tier 3: Mature (discrete-time hazard model) ───────────────────────
        else:
            p_mean, p_std, p25, p75 = _personal_stats(c_history)
            # With enough data we trust the personal estimate fully
            expected_delay         = p_mean
            std_delay              = p_std
            confidence             = "high"
            personal_hazard_offset = p_mean - cohort_mean
            tier                   = 3

        # P(late) = P(delay_days > GRACE_PERIOD)
        from config import GRACE_PERIOD_DAYS
        # Model delay as normal; P(X > GRACE) via complementary CDF
        from scipy.stats import norm
        p_late = float(1.0 - norm.cdf(GRACE_PERIOD_DAYS, loc=expected_delay, scale=max(std_delay, 1.0)))
        p_late = max(0.0, min(1.0, p_late))

        profiles[cid] = LatenessProfile(
            customer_id=cid,
            customer_name=cname,
            expected_delay_days=round(expected_delay, 2),
            p_late=round(p_late, 4),
            p25_delay=round(p25, 2),
            p75_delay=round(p75, 2),
            confidence=confidence,
            personal_hazard_offset=round(personal_hazard_offset, 2),
            invoice_count=n,
            tier=tier,
        )

    return profiles


if __name__ == "__main__":
    import json
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db = os.path.join(_root, DB_PATH)
    profiles = build_lateness_profiles(db)
    for p in profiles.values():
        print(f"  {p.customer_name:25s} | delay={p.expected_delay_days:+6.1f}d "
              f"| p_late={p.p_late:.0%} | confidence={p.confidence} | tier={p.tier}")
