"""
suggestion_engine.py — Ranked action recommendations (Phase 5 / P5)

Implements the 3-step recommendation flow from Section 6 of the TDD:

  Step 1: Rank every unpaid invoice by Expected Risk
          Expected_Risk = Value × P(late beyond grace) × Urgency_Weight

  Step 2: Greedy gap-closing optimization
          Select the minimum-friction set of (chase invoice + delay payable)
          actions that closes the cash shortfall G.

  Step 3: Draft WhatsApp/SMS message for each selected invoice
          (one-tap send — the flagship demo moment)
"""

from __future__ import annotations

import sys, os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    CHASE_COST_DEFAULT,
    P_ACCELERATED_SUCCESS_DEFAULT,
    URGENCY_WINDOW_DAYS,
    CHASE_MESSAGE_TEMPLATE,
    UPCOMING_CHASE_TEMPLATE,
    GRACE_PERIOD_DAYS,
    DB_PATH,
)
from forecasting.behaviour_model import LatenessProfile


# ── Suggestion dataclasses ────────────────────────────────────────────────────

@dataclass
class InvoiceSuggestion:
    invoice_id:       int
    customer_name:    str
    amount:           float
    due_date:         str
    days_overdue:     int
    expected_delay:   float
    p_late:           float
    expected_risk:    float        # Value × P(late) × Urgency
    urgency_weight:   float
    confidence:       str
    draft_message:    str
    action:           str = "CHASE"  # always CHASE for invoices


@dataclass
class PayableSuggestion:
    payable_id:    int
    vendor_name:   str
    amount:        float
    due_date:      str
    days_until_due: int
    category:      str
    action:        str = "DELAY"   # always DELAY for discretionary payables


@dataclass
class SuggestionResult:
    gap:                 float               # Cash gap to close (₹)
    shortfall_date:      str | None
    invoice_suggestions: list[InvoiceSuggestion]   # Ranked chase list
    payable_suggestions: list[PayableSuggestion]   # Delayable payables
    gap_closable:        bool                # Can we close the gap?
    gap_coverage:        float               # ₹ amount covered by suggestions
    financing_needed:    float               # Remaining gap after chase+delay
    summary:             str


# ── Step 1: Expected Risk ranking ─────────────────────────────────────────────

def _urgency_weight(due_date_str: str, shortfall_date_str: str | None) -> float:
    """
    Urgency multiplier: spikes if invoice is expected to pay near the shortfall date.
    Scale: 1.0 (normal) → 3.0 (right before shortfall).
    """
    if shortfall_date_str is None:
        return 1.0

    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        sf  = datetime.strptime(shortfall_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 1.0

    days_gap = (sf - due).days
    if days_gap <= URGENCY_WINDOW_DAYS:
        # Linearly interpolate from 3.0 (0 days gap) to 1.0 (7 days gap)
        return max(1.0, 3.0 - (days_gap / URGENCY_WINDOW_DAYS) * 2.0)

    return 1.0


def _draft_message(invoice: dict, customer_name: str) -> str:
    today = datetime.today().date()
    due   = datetime.strptime(invoice["due_date"], "%Y-%m-%d").date()
    days_overdue = (today - due).days

    if days_overdue > 0:
        return CHASE_MESSAGE_TEMPLATE.format(
            customer_name=customer_name,
            invoice_id=invoice["id"],
            amount=invoice["amount"],
            days_overdue=days_overdue,
        )
    else:
        return UPCOMING_CHASE_TEMPLATE.format(
            customer_name=customer_name,
            invoice_id=invoice["id"],
            amount=invoice["amount"],
            due_date=invoice["due_date"],
        )


def _rank_invoices(
    invoices: list[dict],
    profiles: dict[int, LatenessProfile],
    shortfall_date: str | None,
) -> list[InvoiceSuggestion]:
    """
    Rank unpaid invoices by Expected Risk (descending).
    Expected_Risk = Value × P(late) × Urgency_Weight
    """
    today = datetime.today().date()
    suggestions = []

    for inv in invoices:
        cid     = inv["customer_id"]
        profile = profiles.get(cid)

        p_late     = profile.p_late          if profile else 0.5
        exp_delay  = profile.expected_delay_days if profile else 15.0
        confidence = profile.confidence      if profile else "low"

        due  = datetime.strptime(inv["due_date"], "%Y-%m-%d").date()
        days_overdue = (today - due).days
        urgency = _urgency_weight(inv["due_date"], shortfall_date)
        risk    = inv["amount"] * p_late * urgency

        msg = _draft_message(inv, inv.get("customer_name", "Customer"))

        suggestions.append(InvoiceSuggestion(
            invoice_id=inv["id"],
            customer_name=inv.get("customer_name", "Unknown"),
            amount=inv["amount"],
            due_date=inv["due_date"],
            days_overdue=days_overdue,
            expected_delay=round(exp_delay, 1),
            p_late=round(p_late, 4),
            expected_risk=round(risk, 0),
            urgency_weight=round(urgency, 2),
            confidence=confidence,
            draft_message=msg,
        ))

    return sorted(suggestions, key=lambda s: s.expected_risk, reverse=True)


# ── Step 2: Greedy gap-closing ────────────────────────────────────────────────

def _greedy_close_gap(
    gap: float,
    ranked_invoices: list[InvoiceSuggestion],
    delayable_payables: list[dict],
) -> tuple[list[InvoiceSuggestion], list[PayableSuggestion], float]:
    """
    Greedily select invoices (chase) and payables (delay) to close gap G.

    Returns: (selected_invoices, selected_payables, remaining_gap)
    """
    remaining = gap
    selected_invoices: list[InvoiceSuggestion] = []
    selected_payables: list[PayableSuggestion] = []

    today = datetime.today().date()

    for inv_sug in ranked_invoices:
        if remaining <= 0:
            break
        # Expected cash recovered = amount × P(chase pulls forward)
        expected_recovery = inv_sug.amount * P_ACCELERATED_SUCCESS_DEFAULT
        selected_invoices.append(inv_sug)
        remaining -= expected_recovery

    for pay in delayable_payables:
        if remaining <= 0:
            break
        due = datetime.strptime(pay["due_date"], "%Y-%m-%d").date()
        days_until = (due - today).days
        selected_payables.append(PayableSuggestion(
            payable_id=pay["id"],
            vendor_name=pay.get("vendor_name", "Vendor"),
            amount=pay["amount"],
            due_date=pay["due_date"],
            days_until_due=days_until,
            category=pay.get("category", "discretionary"),
        ))
        remaining -= pay["amount"]

    return selected_invoices, selected_payables, max(remaining, 0)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_suggestions(
    shortfall_gap: float,
    shortfall_date: str | None,
    profiles: dict[int, LatenessProfile],
    db_path: str = DB_PATH,
) -> SuggestionResult:
    """
    Generate a ranked, gap-closing suggestion set.

    Args:
        shortfall_gap:   Size of the cash gap to close (₹); 0 if no shortfall
        shortfall_date:  Date of the shortfall (ISO-8601) or None
        profiles:        Customer lateness profiles
        db_path:         SQLite DB path

    Returns:
        SuggestionResult with ranked invoices, delayable payables, and gap analysis
    """
    from db.database import get_unpaid_invoices, get_pending_payables

    invoices = get_unpaid_invoices(db_path)
    payables = get_pending_payables(db_path)

    # Rank ALL invoices by expected risk (shown in full in the UI)
    ranked_invoices = _rank_invoices(invoices, profiles, shortfall_date)

    # Only discretionary payables are delay candidates
    delayable = [p for p in payables if p.get("category") == "discretionary"]
    delayable_sorted = sorted(delayable, key=lambda p: p["amount"], reverse=True)

    # If there's a gap, run greedy optimizer
    if shortfall_gap > 0:
        sel_inv, sel_pay, remaining = _greedy_close_gap(
            shortfall_gap, ranked_invoices, delayable_sorted
        )
        gap_coverage   = shortfall_gap - remaining
        gap_closable   = remaining <= 0
        financing_needed = remaining
    else:
        sel_inv, sel_pay, remaining = [], [], 0.0
        gap_coverage   = 0.0
        gap_closable   = True
        financing_needed = 0.0

    # Build payable suggestion objects for all discretionary payables (for display)
    today = datetime.today().date()
    payable_suggestions = []
    for pay in delayable_sorted:
        due = datetime.strptime(pay["due_date"], "%Y-%m-%d").date()
        payable_suggestions.append(PayableSuggestion(
            payable_id=pay["id"],
            vendor_name=pay.get("vendor_name", "Vendor"),
            amount=pay["amount"],
            due_date=pay["due_date"],
            days_until_due=(due - today).days,
            category=pay.get("category", "discretionary"),
        ))

    if shortfall_gap <= 0:
        summary = "No shortfall detected. All invoices shown below ranked by collection priority."
    elif gap_closable:
        summary = (f"Gap of ₹{shortfall_gap:,.0f} can be closed by chasing "
                   f"{len(sel_inv)} invoice(s) and delaying "
                   f"{len(sel_pay)} payable(s). "
                   f"Estimated coverage: ₹{gap_coverage:,.0f}.")
    else:
        summary = (f"Gap of ₹{shortfall_gap:,.0f} partially addressed "
                   f"(₹{gap_coverage:,.0f} covered). "
                   f"₹{financing_needed:,.0f} remaining — consider a short-term credit line.")

    return SuggestionResult(
        gap=shortfall_gap,
        shortfall_date=shortfall_date,
        invoice_suggestions=ranked_invoices,
        payable_suggestions=payable_suggestions,
        gap_closable=gap_closable,
        gap_coverage=gap_coverage,
        financing_needed=financing_needed,
        summary=summary,
    )
