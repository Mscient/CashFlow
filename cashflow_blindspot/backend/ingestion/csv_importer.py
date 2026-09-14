"""
csv_importer.py — CSV → cleaned DB rows (Phase 1 / P1)

Reads a flat CSV where each row is tagged with a `type` column:
  customer | vendor | invoice | payable | payment

Row dispatch → fuzzy name resolution → SQLite insert.
Smart defaults applied (missing due_date → Net-30).
"""

import pandas as pd
import sqlite3
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DEFAULT_PAYMENT_TERMS_DAYS, DB_PATH
from ingestion.fuzzy_match import get_or_create_customer, get_or_create_vendor

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _parse_date(val) -> str | None:
    """Parse a date value into ISO-8601 string, or return None."""
    if pd.isna(val) or str(val).strip() == "":
        return None
    try:
        return pd.to_datetime(str(val)).strftime("%Y-%m-%d")
    except Exception:
        return None


def _net30_from(issue_date: str) -> str:
    """Return a Net-30 due date string from an issue date string."""
    dt = datetime.strptime(issue_date, "%Y-%m-%d")
    return (dt + timedelta(days=DEFAULT_PAYMENT_TERMS_DAYS)).strftime("%Y-%m-%d")


def _handle_customer(row: pd.Series, conn: sqlite3.Connection) -> None:
    name = str(row.get("name", "")).strip()
    if not name:
        return
    get_or_create_customer(
        name, conn,
        industry=str(row.get("industry", "general") or "general"),
        region=str(row.get("region", "india") or "india"),
        size_bracket=str(row.get("size_bracket", "small") or "small"),
    )


def _handle_vendor(row: pd.Series, conn: sqlite3.Connection) -> None:
    name = str(row.get("name", "")).strip()
    if not name:
        return
    get_or_create_vendor(
        name, conn,
        category=str(row.get("category", "general") or "general"),
    )


def _handle_invoice(row: pd.Series, conn: sqlite3.Connection) -> None:
    cname = str(row.get("customer_name", "")).strip()
    if not cname:
        return

    cid = get_or_create_customer(cname, conn)

    issue_date = _parse_date(row.get("issue_date"))
    due_date   = _parse_date(row.get("due_date"))

    if not issue_date:
        issue_date = datetime.today().strftime("%Y-%m-%d")
    if not due_date:
        due_date = _net30_from(issue_date)

    inv_id = row.get("id") if not pd.isna(row.get("id", float("nan"))) else None
    paid_date = _parse_date(row.get("paid_date"))
    status = str(row.get("status", "unpaid") or "unpaid").strip()

    conn.execute(
        "INSERT OR IGNORE INTO invoices "
        "(id, customer_id, amount, issue_date, due_date, status, paid_date, category) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (inv_id, cid, float(row["amount"]), issue_date, due_date,
         status, paid_date, str(row.get("category", "product") or "product"))
    )


def _handle_payable(row: pd.Series, conn: sqlite3.Connection) -> None:
    vname = str(row.get("vendor_name", "")).strip()
    if not vname:
        return

    vid = get_or_create_vendor(vname, conn)
    due_date = _parse_date(row.get("due_date")) or datetime.today().strftime("%Y-%m-%d")
    pay_id = row.get("id") if not pd.isna(row.get("id", float("nan"))) else None

    conn.execute(
        "INSERT OR IGNORE INTO payables "
        "(id, vendor_id, amount, due_date, category, status) VALUES (?,?,?,?,?,?)",
        (pay_id, vid, float(row["amount"]), due_date,
         str(row.get("category", "fixed") or "fixed"),
         str(row.get("status", "pending") or "pending"))
    )


def _handle_payment(row: pd.Series, conn: sqlite3.Connection) -> None:
    cname = str(row.get("customer_name", "")).strip()
    if not cname:
        return

    cid = get_or_create_customer(cname, conn)
    issue_date = _parse_date(row.get("issue_date")) or datetime.today().strftime("%Y-%m-%d")
    inv_id = row.get("invoice_id") if not pd.isna(row.get("invoice_id", float("nan"))) else None

    conn.execute(
        "INSERT INTO payment_history "
        "(invoice_id, customer_id, expected_days, actual_days, chased, issue_date) "
        "VALUES (?,?,?,?,?,?)",
        (inv_id, cid, float(row["expected_days"]), float(row["actual_days"]),
         int(row.get("chased", 0) or 0), issue_date)
    )


# ── Public API ────────────────────────────────────────────────────────────────

_HANDLERS = {
    "customer": _handle_customer,
    "vendor":   _handle_vendor,
    "invoice":  _handle_invoice,
    "payable":  _handle_payable,
    "payment":  _handle_payment,
}


def import_csv(path: str, db_path: str = DB_PATH) -> dict:
    """
    Import a transaction CSV into the database.

    Args:
        path:    Path to the CSV file
        db_path: SQLite database path

    Returns:
        Dict with counts of rows processed per type.
    """
    from db.database import get_connection
    df = pd.read_csv(path, comment="#")
    df.columns = [c.strip().lower() for c in df.columns]

    counts = {k: 0 for k in _HANDLERS}
    errors = []

    conn = get_connection(db_path)
    try:
        for idx, row in df.iterrows():
            rtype = str(row.get("type", "")).strip().lower()
            handler = _HANDLERS.get(rtype)
            if handler is None:
                continue
            try:
                handler(row, conn)
                counts[rtype] += 1
            except Exception as e:
                errors.append(f"Row {idx} ({rtype}): {e}")
        conn.commit()
    finally:
        conn.close()

    if errors:
        print(f"[CSV] {len(errors)} errors during import:")
        for e in errors[:10]:
            print(f"  {e}")

    print(f"[CSV] Import complete: {counts}")
    return counts


if __name__ == "__main__":
    path = os.path.join(_root, "data", "sample_transactions.csv")
    db   = os.path.join(_root, DB_PATH)
    import_csv(path, db)
