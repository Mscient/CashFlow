"""
database.py — SQLite schema + connection helper (Phase 1)

Run directly to initialise the DB and load sample data:
    python backend/db/database.py
"""

import sqlite3
import os
import sys
import pandas as pd
from datetime import datetime

# Make imports work whether run directly or as a module
_this_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_this_dir, "..", ".."))
sys.path.insert(0, os.path.join(_root, "backend"))

from config import DB_PATH, SAMPLE_CSV_PATH


# ── Connection helper ─────────────────────────────────────────────────────────

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row          # rows accessible as dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Schema DDL ────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    industry        TEXT    DEFAULT 'general',
    region          TEXT    DEFAULT 'india',
    size_bracket    TEXT    DEFAULT 'small',
    phone           TEXT,
    email           TEXT
);

CREATE TABLE IF NOT EXISTS vendors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    category        TEXT    DEFAULT 'general'
);

CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    amount          REAL    NOT NULL,
    issue_date      TEXT    NOT NULL,
    due_date        TEXT    NOT NULL,
    status          TEXT    DEFAULT 'unpaid',
    paid_date       TEXT,
    category        TEXT    DEFAULT 'product'
);

CREATE TABLE IF NOT EXISTS payables (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id       INTEGER NOT NULL REFERENCES vendors(id),
    amount          REAL    NOT NULL,
    due_date        TEXT    NOT NULL,
    category        TEXT    DEFAULT 'fixed',
    status          TEXT    DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS payment_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id      INTEGER REFERENCES invoices(id),
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    expected_days   REAL    NOT NULL,
    actual_days     REAL    NOT NULL,
    delay_days      REAL    GENERATED ALWAYS AS (actual_days - expected_days) VIRTUAL,
    chased          INTEGER DEFAULT 0,
    issue_date      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS chase_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER REFERENCES invoices(id),
    channel     TEXT    NOT NULL DEFAULT 'whatsapp',
    message     TEXT    NOT NULL,
    sent_at     TEXT    NOT NULL,
    response    TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""


def init_db(db_path: str = DB_PATH) -> None:
    """Create all tables if they don't exist."""
    with get_connection(db_path) as conn:
        conn.executescript(_SCHEMA_SQL)
    print(f"[DB] Schema initialised at {db_path}")


# ── Sample data loader ────────────────────────────────────────────────────────

def load_sample_data(db_path: str = DB_PATH, csv_path: str = None) -> None:
    """Load sample_transactions.csv into the database (idempotent)."""
    if csv_path is None:
        csv_path = os.path.join(_root, SAMPLE_CSV_PATH)

    if not os.path.exists(csv_path):
        print(f"[DB] Sample CSV not found at {csv_path} — skipping load.")
        return

    df = pd.read_csv(csv_path)
    conn = get_connection(db_path)

    inserted = {"customers": 0, "vendors": 0, "invoices": 0,
                "payables": 0, "payment_history": 0}

    for _, row in df.iterrows():
        rtype = str(row.get("type", "")).strip().lower()

        if rtype == "customer":
            conn.execute(
                "INSERT OR IGNORE INTO customers (name, industry, region, size_bracket) "
                "VALUES (?,?,?,?)",
                (row["name"], row.get("industry", "general"),
                 row.get("region", "india"), row.get("size_bracket", "small"))
            )
            inserted["customers"] += 1

        elif rtype == "vendor":
            conn.execute(
                "INSERT OR IGNORE INTO vendors (name, category) VALUES (?,?)",
                (row["name"], row.get("category", "general"))
            )
            inserted["vendors"] += 1

        elif rtype == "invoice":
            cust = conn.execute(
                "SELECT id FROM customers WHERE name=?", (row["customer_name"],)
            ).fetchone()
            if cust:
                conn.execute(
                    "INSERT OR IGNORE INTO invoices "
                    "(id, customer_id, amount, issue_date, due_date, status, paid_date, category) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (row.get("id"), cust["id"], float(row["amount"]),
                     row["issue_date"], row["due_date"],
                     row.get("status", "unpaid"), row.get("paid_date") or None,
                     row.get("category", "product"))
                )
                inserted["invoices"] += 1

        elif rtype == "payable":
            vend = conn.execute(
                "SELECT id FROM vendors WHERE name=?", (row["vendor_name"],)
            ).fetchone()
            if vend:
                conn.execute(
                    "INSERT OR IGNORE INTO payables "
                    "(id, vendor_id, amount, due_date, category, status) VALUES (?,?,?,?,?,?)",
                    (row.get("id"), vend["id"], float(row["amount"]),
                     row["due_date"], row.get("category", "fixed"),
                     row.get("status", "pending"))
                )
                inserted["payables"] += 1

        elif rtype == "payment":
            cust = conn.execute(
                "SELECT id FROM customers WHERE name=?", (row["customer_name"],)
            ).fetchone()
            if cust:
                conn.execute(
                    "INSERT INTO payment_history "
                    "(invoice_id, customer_id, expected_days, actual_days, chased, issue_date) "
                    "VALUES (?,?,?,?,?,?)",
                    (None, cust["id"],
                     float(row["expected_days"]), float(row["actual_days"]),
                     int(row.get("chased", 0) if pd.notna(row.get("chased")) else 0), row["issue_date"])
                )
                inserted["payment_history"] += 1

    conn.commit()
    conn.close()
    print(f"[DB] Sample data loaded: {inserted}")


# ── Convenience query helpers ─────────────────────────────────────────────────

def get_unpaid_invoices(db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("""
            SELECT i.*, c.name AS customer_name, c.industry, c.region, c.size_bracket
            FROM invoices i
            JOIN customers c ON i.customer_id = c.id
            WHERE i.status IN ('unpaid', 'overdue')
            ORDER BY i.due_date
        """).fetchall()
    return [dict(r) for r in rows]


def get_pending_payables(db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("""
            SELECT p.*, v.name AS vendor_name
            FROM payables p
            JOIN vendors v ON p.vendor_id = v.id
            WHERE p.status IN ('pending')
            ORDER BY p.due_date
        """).fetchall()
    return [dict(r) for r in rows]


def get_payment_history(db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("""
            SELECT ph.*, c.name AS customer_name
            FROM payment_history ph
            JOIN customers c ON ph.customer_id = c.id
            ORDER BY ph.issue_date DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_all_customers(db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM customers").fetchall()
    return [dict(r) for r in rows]


def get_all_vendors(db_path: str = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM vendors").fetchall()
    return [dict(r) for r in rows]


def mark_invoice_paid(invoice_id: int, paid_date: str = None,
                      db_path: str = DB_PATH) -> None:
    if paid_date is None:
        paid_date = datetime.today().strftime("%Y-%m-%d")
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE invoices SET status='paid', paid_date=? WHERE id=?",
            (paid_date, invoice_id)
        )
    print(f"[DB] Invoice #{invoice_id} marked paid on {paid_date}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db = os.path.join(_root, DB_PATH)
    init_db(db)
    load_sample_data(db)
    print("[DB] Ready.")
