"""
fuzzy_match.py — Customer / vendor name resolution (Phase 1 / P1)

Uses difflib to collapse spelling variants to one canonical record.
Threshold is controlled by config.FUZZY_MATCH_THRESHOLD.
"""

import difflib
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import FUZZY_MATCH_THRESHOLD


def best_match(name: str, candidates: list[str],
               threshold: float = FUZZY_MATCH_THRESHOLD) -> str | None:
    """
    Return the best fuzzy match for `name` among `candidates`,
    or None if no match exceeds the threshold.

    Args:
        name:       Incoming name string (e.g. from CSV)
        candidates: List of existing canonical names in the DB
        threshold:  difflib similarity ratio (0–1); default from config

    Returns:
        Best-matching canonical name, or None.
    """
    if not candidates:
        return None

    name_lower = name.strip().lower()
    cands_lower = [c.lower() for c in candidates]

    matches = difflib.get_close_matches(
        name_lower, cands_lower, n=1, cutoff=threshold
    )

    if matches:
        # Map back to original-case candidate
        idx = cands_lower.index(matches[0])
        return candidates[idx]

    return None


def resolve_customer(name: str, conn) -> int | None:
    """
    Fuzzy-match `name` against existing customers in the DB.

    Returns the customer id of the best match, or None if no match found
    (caller is responsible for inserting a new customer).

    Args:
        name: Raw customer name from CSV or user input
        conn: sqlite3.Connection (with row_factory = sqlite3.Row)
    """
    rows = conn.execute("SELECT id, name FROM customers").fetchall()
    if not rows:
        return None

    existing_names = [r["name"] for r in rows]
    matched = best_match(name, existing_names)

    if matched:
        row = conn.execute(
            "SELECT id FROM customers WHERE name=?", (matched,)
        ).fetchone()
        return row["id"] if row else None

    return None


def resolve_vendor(name: str, conn) -> int | None:
    """
    Fuzzy-match `name` against existing vendors in the DB.

    Returns vendor id of best match, or None.
    """
    rows = conn.execute("SELECT id, name FROM vendors").fetchall()
    if not rows:
        return None

    existing_names = [r["name"] for r in rows]
    matched = best_match(name, existing_names)

    if matched:
        row = conn.execute(
            "SELECT id FROM vendors WHERE name=?", (matched,)
        ).fetchone()
        return row["id"] if row else None

    return None


def get_or_create_customer(name: str, conn,
                            industry: str = "general",
                            region: str = "india",
                            size_bracket: str = "small") -> int:
    """
    Resolve or insert a customer; returns their DB id.
    """
    cid = resolve_customer(name, conn)
    if cid is not None:
        return cid

    cursor = conn.execute(
        "INSERT INTO customers (name, industry, region, size_bracket) VALUES (?,?,?,?)",
        (name.strip(), industry, region, size_bracket)
    )
    return cursor.lastrowid


def get_or_create_vendor(name: str, conn, category: str = "general") -> int:
    """
    Resolve or insert a vendor; returns their DB id.
    """
    vid = resolve_vendor(name, conn)
    if vid is not None:
        return vid

    cursor = conn.execute(
        "INSERT INTO vendors (name, category) VALUES (?,?)",
        (name.strip(), category)
    )
    return cursor.lastrowid
