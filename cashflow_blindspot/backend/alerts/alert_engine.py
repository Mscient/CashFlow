"""
alert_engine.py — Tiered alert generation (Phase 4 / P4)

Converts the first_shortfall_date + Monte Carlo shortfall probability
into a human-readable, colour-coded alert tier.

Tiers (controlled by config.py):
  CRITICAL  — shortfall within 7 days AND P ≥ 70%   → red
  WARNING   — shortfall within 14 days AND P ≥ 50%  → orange
  INFO      — shortfall within 21 days AND P ≥ 30%  → yellow
  NONE      — no near-term risk                       → green
"""

from __future__ import annotations

import sys, os
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    ALERT_CRITICAL_DAYS, ALERT_WARNING_DAYS, ALERT_INFO_DAYS,
    ALERT_CRITICAL_PROB, ALERT_WARNING_PROB, ALERT_INFO_PROB,
)


# ── Alert result dataclass ────────────────────────────────────────────────────

@dataclass
class AlertResult:
    tier:                   str         # 'CRITICAL' | 'WARNING' | 'INFO' | 'NONE'
    color:                  str         # Hex color code for the UI
    emoji:                  str
    headline:               str         # Short headline sentence
    detail:                 str         # Longer explanation
    days_to_shortfall:      int | None
    shortfall_date:         str | None
    shortfall_probability:  float       # 0–1


_TIER_META = {
    "CRITICAL": {"color": "#FF3B30", "emoji": "🚨"},
    "WARNING":  {"color": "#FF9500", "emoji": "⚠️"},
    "INFO":     {"color": "#FFCC00", "emoji": "ℹ️"},
    "NONE":     {"color": "#34C759", "emoji": "✅"},
}


def generate_alert(
    first_shortfall_date: str | None,
    days_to_shortfall: int | None,
    shortfall_probability: float,
) -> AlertResult:
    """
    Determine alert tier based on time-to-shortfall and probability.

    Args:
        first_shortfall_date:   ISO-8601 date of predicted first shortfall (or None)
        days_to_shortfall:      Integer days until shortfall (or None)
        shortfall_probability:  Monte Carlo P(balance < 0) on that day

    Returns:
        AlertResult with tier, colors, and human-readable text
    """
    if days_to_shortfall is None or first_shortfall_date is None:
        return AlertResult(
            tier="NONE", color=_TIER_META["NONE"]["color"],
            emoji=_TIER_META["NONE"]["emoji"],
            headline="Cash position looks healthy",
            detail="No shortfall detected in the next 90-day forecast horizon. "
                   "Keep monitoring weekly.",
            days_to_shortfall=None,
            shortfall_date=None,
            shortfall_probability=shortfall_probability,
        )

    d   = days_to_shortfall
    p   = shortfall_probability
    fmt = first_shortfall_date  # ISO string

    if d <= ALERT_CRITICAL_DAYS and p >= ALERT_CRITICAL_PROB:
        tier    = "CRITICAL"
        headline = f"Critical: Shortfall in {d} day{'s' if d != 1 else ''} ({p:.0%} probability)"
        detail   = (f"Your balance is projected to go negative by {fmt}. "
                    f"Immediate action is required — chase overdue invoices and consider "
                    f"delaying discretionary payables.")

    elif d <= ALERT_WARNING_DAYS and p >= ALERT_WARNING_PROB:
        tier    = "WARNING"
        headline = f"Warning: Shortfall risk in {d} days ({p:.0%} probability)"
        detail   = (f"A cash shortfall is likely around {fmt}. "
                    f"Prioritise chasing the top-ranked invoices below to close the gap.")

    elif d <= ALERT_INFO_DAYS and p >= ALERT_INFO_PROB:
        tier    = "INFO"
        headline = f"Notice: Potential shortfall in {d} days ({p:.0%} probability)"
        detail   = (f"Cash position may tighten around {fmt}. "
                    f"Review the suggestions below to stay ahead of the gap.")

    else:
        tier    = "NONE"
        headline = "Cash position looks healthy"
        detail   = (f"While a shortfall is modelled at {fmt}, probability is low ({p:.0%}). "
                    f"Continue normal operations and review next week.")

    return AlertResult(
        tier=tier,
        color=_TIER_META[tier]["color"],
        emoji=_TIER_META[tier]["emoji"],
        headline=headline,
        detail=detail,
        days_to_shortfall=d,
        shortfall_date=fmt,
        shortfall_probability=p,
    )
