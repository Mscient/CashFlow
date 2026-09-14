"""
app.py — Complete Flask REST API for CashFlow Blindspot

Endpoints:
  Core:
    GET  /api/health
    GET  /api/dashboard?balance=<float>

  Invoices:
    GET  /api/invoices                    ?status=&customer_id=&limit=&offset=
    POST /api/invoices
    GET  /api/invoices/<id>
    PATCH /api/invoices/<id>
    POST /api/invoices/<id>/mark_paid
    GET  /api/invoices/<id>/chase-log
    POST /api/invoices/<id>/chase

  Payables:
    GET  /api/payables                    ?status=&limit=&offset=
    POST /api/payables
    GET  /api/payables/<id>
    PATCH /api/payables/<id>
    POST /api/payables/<id>/mark_paid

  Customers:
    GET  /api/customers
    POST /api/customers
    GET  /api/customers/<id>
    PATCH /api/customers/<id>
    GET  /api/customers/<id>/invoices

  Vendors:
    GET  /api/vendors
    POST /api/vendors
    GET  /api/vendors/<id>

  Analytics:
    GET  /api/analytics/summary
    GET  /api/analytics/cashflow          ?balance=&days=
    GET  /api/analytics/customers

  Alerts:
    GET  /api/alerts/message-center       ?balance=

  Settings:
    GET  /api/settings
    POST /api/settings

  Ingestion:
    POST /api/ingest/seed
    POST /api/ingest/csv

  Export:
    GET  /api/export/invoices.csv
    GET  /api/export/payables.csv
"""

import sys, os, traceback, csv, io
from datetime import datetime

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_root, "backend"))

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

from config import DB_PATH
from db.database import (
    init_db, get_connection,
    get_unpaid_invoices, get_pending_payables,
    get_all_customers, get_all_vendors,
    mark_invoice_paid, load_sample_data,
)
from scheduler.daily_job import run_daily_job

app = Flask(__name__)
CORS(app)
DB = os.path.join(_root, DB_PATH)

# Default settings stored in app_settings table
_DEFAULT_SETTINGS = {
    "starting_balance":       "300000",
    "alert_critical_days":    "7",
    "alert_warning_days":     "14",
    "alert_info_days":        "21",
    "alert_critical_prob":    "0.70",
    "alert_warning_prob":     "0.50",
    "monte_carlo_runs":       "2000",
    "forecast_horizon_days":  "90",
    "company_name":           "My Business",
    "company_phone":          "",
}


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _ok(data, status=200):
    return jsonify(data), status


def _err(msg, status=400):
    return jsonify({"error": msg}), status


def _run(balance: float):
    return run_daily_job(balance, DB)


def _get_settings():
    with get_connection(DB) as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    s = dict(_DEFAULT_SETTINGS)
    for r in rows:
        s[r["key"]] = r["value"]
    return s


def _fmt_alert(a):
    tier = a.tier
    if hasattr(tier, "value"):
        tier = tier.value
    return {
        "tier":              tier,
        "headline":          a.headline,
        "detail":            a.detail,
        "shortfall_date":    a.shortfall_date,
        "days_to_shortfall": a.days_to_shortfall,
        "probability":       float(a.shortfall_probability),
        "color":             a.color,
        "emoji":             a.emoji,
    }


def _fmt_forecast(f, mc):
    bal = f.daily_balance
    inf = f.daily_inflows
    out = f.daily_outflows
    if hasattr(bal, "tolist"): bal = bal.tolist()
    if hasattr(inf, "tolist"): inf = inf.tolist()
    if hasattr(out, "tolist"): out = out.tolist()
    return {
        "dates":              f.dates,
        "daily_balance":      bal,
        "daily_inflows":      inf,
        "daily_outflows":     out,
        "p5":   mc.p5,  "p25": mc.p25,
        "p50":  mc.p50, "p75": mc.p75, "p95": mc.p95,
        "shortfall_prob":     mc.shortfall_prob,
        "first_shortfall":    f.first_shortfall_date,
        "days_to_shortfall":  f.days_to_shortfall,
        "total_ar":           float(f.total_ar),
        "total_ap":           float(f.total_ap),
        "starting_balance":   float(f.starting_balance),
        "ending_balance":     float(f.ending_balance),
        "peak_shortfall_prob": float(mc.peak_shortfall_prob),
        "most_likely_shortfall_date": mc.most_likely_shortfall_date,
    }


def _fmt_suggestions(s):
    return {
        "gap":              float(s.gap),
        "summary":          s.summary,
        "gap_closable":     float(s.gap_coverage),
        "gap_closable_bool": bool(s.gap_closable),
        "financing_needed": float(s.financing_needed),
        "shortfall_date":   s.shortfall_date,
        "invoices": [
            {
                "invoice_id":    inv.invoice_id,
                "customer_name": inv.customer_name,
                "amount":        float(inv.amount),
                "due_date":      inv.due_date,
                "days_overdue":  inv.days_overdue,
                "expected_delay": float(inv.expected_delay),
                "p_late":        float(inv.p_late),
                "expected_risk": float(inv.expected_risk),
                "urgency_weight": float(inv.urgency_weight),
                "confidence":    inv.confidence,
                "action":        inv.action,
                "draft_message": inv.draft_message,
            }
            for inv in s.invoice_suggestions[:20]
        ],
        "payables": [
            {
                "payable_id":     p.payable_id,
                "vendor_name":    p.vendor_name,
                "amount":         float(p.amount),
                "due_date":       p.due_date,
                "days_until_due": p.days_until_due,
                "category":       p.category,
                "action":         p.action,
            }
            for p in s.payable_suggestions
        ],
    }


@app.errorhandler(Exception)
def handle_error(e):
    traceback.print_exc()
    return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════════════
# Health + Dashboard
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/health")
def health():
    with get_connection(DB) as conn:
        inv = conn.execute("SELECT count(*) FROM invoices WHERE status IN ('unpaid','overdue')").fetchone()[0]
        pay = conn.execute("SELECT count(*) FROM payables WHERE status='pending'").fetchone()[0]
        cus = conn.execute("SELECT count(*) FROM customers").fetchone()[0]
    return _ok({"status": "ok", "open_invoices": inv,
                "pending_payables": pay, "customers": cus,
                "timestamp": datetime.utcnow().isoformat() + "Z"})


@app.route("/api/dashboard")
def dashboard():
    balance = float(request.args.get("balance", _get_settings().get("starting_balance", 300000)))
    result  = _run(balance)
    return _ok({
        "forecast":    _fmt_forecast(result.forecast, result.monte_carlo),
        "alert":       _fmt_alert(result.alert),
        "suggestions": _fmt_suggestions(result.suggestions),
    })


# ════════════════════════════════════════════════════════════════════════════
# Invoices
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/invoices", methods=["GET"])
def list_invoices():
    status     = request.args.get("status")
    customer   = request.args.get("customer_id")
    limit      = int(request.args.get("limit", 200))
    offset     = int(request.args.get("offset", 0))
    sort       = request.args.get("sort", "due_date")
    order      = "DESC" if request.args.get("order", "asc").lower() == "desc" else "ASC"

    allowed_sort = {"due_date", "amount", "status", "issue_date"}
    if sort not in allowed_sort:
        sort = "due_date"

    with get_connection(DB) as conn:
        q = """
            SELECT i.id, i.customer_id, i.amount, i.issue_date, i.due_date,
                   i.status, i.paid_date, i.category,
                   c.name AS customer_name, c.phone, c.email, c.industry, c.region,
                   CAST((julianday('now') - julianday(i.due_date)) AS INTEGER) AS days_overdue
            FROM invoices i JOIN customers c ON i.customer_id = c.id
        """
        filters, params = [], []
        if status:
            filters.append("i.status = ?"); params.append(status)
        if customer:
            filters.append("i.customer_id = ?"); params.append(int(customer))
        if filters:
            q += " WHERE " + " AND ".join(filters)
        q += f" ORDER BY i.{sort} {order} LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows  = conn.execute(q, params).fetchall()
        total = conn.execute(
            "SELECT count(*) FROM invoices" + (" WHERE status=?" if status else ""),
            ([status] if status else [])
        ).fetchone()[0]

    return _ok({"invoices": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset})


@app.route("/api/invoices", methods=["POST"])
def create_invoice():
    d = request.get_json(force=True)
    for f in ["customer_id", "amount", "issue_date", "due_date"]:
        if f not in d:
            return _err(f"Missing required field: {f}")

    with get_connection(DB) as conn:
        if not conn.execute("SELECT 1 FROM customers WHERE id=?", (d["customer_id"],)).fetchone():
            return _err(f"customer_id {d['customer_id']} not found", 404)
        cur = conn.execute(
            "INSERT INTO invoices (customer_id, amount, issue_date, due_date, status, category) VALUES (?,?,?,?,?,?)",
            (d["customer_id"], float(d["amount"]), d["issue_date"], d["due_date"],
             d.get("status", "unpaid"), d.get("category", "product"))
        )
        conn.commit()
    return _ok({"invoice_id": cur.lastrowid, "status": "created"}, 201)


@app.route("/api/invoices/<int:iid>", methods=["GET"])
def get_invoice(iid):
    with get_connection(DB) as conn:
        row = conn.execute(
            "SELECT i.*, c.name AS customer_name, c.phone, c.email FROM invoices i "
            "JOIN customers c ON i.customer_id = c.id WHERE i.id=?", (iid,)
        ).fetchone()
    return _ok(dict(row)) if row else _err("Not found", 404)


@app.route("/api/invoices/<int:iid>", methods=["PATCH"])
def update_invoice(iid):
    d = request.get_json(force=True)
    updates = {k: v for k, v in d.items() if k in {"amount","due_date","status","paid_date","category"}}
    if not updates:
        return _err("No valid fields")
    with get_connection(DB) as conn:
        conn.execute(
            "UPDATE invoices SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?",
            list(updates.values()) + [iid]
        )
        conn.commit()
    return _ok({"invoice_id": iid, "updated": list(updates.keys())})


@app.route("/api/invoices/<int:iid>/mark_paid", methods=["POST"])
def api_mark_paid(iid):
    body      = request.get_json(silent=True) or {}
    paid_date = body.get("paid_date") or datetime.today().strftime("%Y-%m-%d")
    mark_invoice_paid(iid, paid_date, DB)
    return _ok({"invoice_id": iid, "status": "paid", "paid_date": paid_date})


@app.route("/api/invoices/<int:iid>/chase-log", methods=["GET"])
def get_chase_log(iid):
    with get_connection(DB) as conn:
        rows = conn.execute(
            "SELECT * FROM chase_log WHERE invoice_id=? ORDER BY sent_at DESC", (iid,)
        ).fetchall()
    return _ok({"chase_log": [dict(r) for r in rows], "total": len(rows)})


@app.route("/api/invoices/<int:iid>/chase", methods=["POST"])
def log_chase(iid):
    d = request.get_json(force=True)
    channel = d.get("channel", "whatsapp")
    message = d.get("message", "")
    if not message:
        return _err("message is required")

    sent_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection(DB) as conn:
        conn.execute(
            "INSERT INTO chase_log (invoice_id, channel, message, sent_at, response) VALUES (?,?,?,?,?)",
            (iid, channel, message, sent_at, d.get("response"))
        )
        conn.commit()
    return _ok({"status": "logged", "invoice_id": iid, "channel": channel, "sent_at": sent_at})


# ════════════════════════════════════════════════════════════════════════════
# Payables
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/payables", methods=["GET"])
def list_payables():
    status = request.args.get("status")
    limit  = int(request.args.get("limit", 200))
    offset = int(request.args.get("offset", 0))

    with get_connection(DB) as conn:
        q = """
            SELECT p.*, v.name AS vendor_name,
                   CAST((julianday(p.due_date) - julianday('now')) AS INTEGER) AS days_until_due
            FROM payables p JOIN vendors v ON p.vendor_id = v.id
        """
        params = []
        if status:
            q += " WHERE p.status = ?"; params.append(status)
        q += " ORDER BY p.due_date LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows  = conn.execute(q, params).fetchall()
        total = conn.execute("SELECT count(*) FROM payables").fetchone()[0]

    return _ok({"payables": [dict(r) for r in rows], "total": total})


@app.route("/api/payables", methods=["POST"])
def create_payable():
    d = request.get_json(force=True)
    for f in ["vendor_id", "amount", "due_date"]:
        if f not in d:
            return _err(f"Missing: {f}")

    with get_connection(DB) as conn:
        if not conn.execute("SELECT 1 FROM vendors WHERE id=?", (d["vendor_id"],)).fetchone():
            return _err(f"vendor_id {d['vendor_id']} not found", 404)
        cur = conn.execute(
            "INSERT INTO payables (vendor_id, amount, due_date, category, status) VALUES (?,?,?,?,?)",
            (d["vendor_id"], float(d["amount"]), d["due_date"],
             d.get("category", "fixed"), d.get("status", "pending"))
        )
        conn.commit()
    return _ok({"payable_id": cur.lastrowid, "status": "created"}, 201)


@app.route("/api/payables/<int:pid>", methods=["GET"])
def get_payable(pid):
    with get_connection(DB) as conn:
        row = conn.execute(
            "SELECT p.*, v.name AS vendor_name FROM payables p "
            "JOIN vendors v ON p.vendor_id = v.id WHERE p.id=?", (pid,)
        ).fetchone()
    return _ok(dict(row)) if row else _err("Not found", 404)


@app.route("/api/payables/<int:pid>", methods=["PATCH"])
def update_payable(pid):
    d = request.get_json(force=True)
    updates = {k: v for k, v in d.items() if k in {"amount","due_date","status","category"}}
    if not updates:
        return _err("No valid fields")
    with get_connection(DB) as conn:
        conn.execute(
            "UPDATE payables SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?",
            list(updates.values()) + [pid]
        )
        conn.commit()
    return _ok({"payable_id": pid, "updated": list(updates.keys())})


@app.route("/api/payables/<int:pid>/mark_paid", methods=["POST"])
def mark_payable_paid(pid):
    with get_connection(DB) as conn:
        conn.execute("UPDATE payables SET status='paid' WHERE id=?", (pid,))
        conn.commit()
    return _ok({"payable_id": pid, "status": "paid"})


# ════════════════════════════════════════════════════════════════════════════
# Customers
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/customers", methods=["GET"])
def list_customers():
    with get_connection(DB) as conn:
        rows = conn.execute("""
            SELECT c.*,
                   COALESCE(SUM(CASE WHEN i.status IN ('unpaid','overdue') THEN i.amount ELSE 0 END),0) AS ar_outstanding,
                   count(CASE WHEN i.status IN ('unpaid','overdue') THEN 1 END) AS open_invoices,
                   count(CASE WHEN i.status='overdue' THEN 1 END) AS overdue_invoices
            FROM customers c LEFT JOIN invoices i ON i.customer_id = c.id
            GROUP BY c.id ORDER BY ar_outstanding DESC
        """).fetchall()
    return _ok({"customers": [dict(r) for r in rows], "total": len(rows)})


@app.route("/api/customers", methods=["POST"])
def create_customer():
    d = request.get_json(force=True)
    if not d.get("name"):
        return _err("name is required")
    with get_connection(DB) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO customers (name, industry, region, size_bracket, phone, email) VALUES (?,?,?,?,?,?)",
                (d["name"], d.get("industry","general"), d.get("region","india"),
                 d.get("size_bracket","small"), d.get("phone"), d.get("email"))
            )
            conn.commit()
        except Exception as e:
            return _err(str(e))
    return _ok({"customer_id": cur.lastrowid, "status": "created"}, 201)


@app.route("/api/customers/<int:cid>", methods=["GET"])
def get_customer(cid):
    with get_connection(DB) as conn:
        row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    return _ok(dict(row)) if row else _err("Not found", 404)


@app.route("/api/customers/<int:cid>", methods=["PATCH"])
def update_customer(cid):
    d = request.get_json(force=True)
    updates = {k: v for k, v in d.items() if k in {"name","industry","region","size_bracket","phone","email"}}
    if not updates:
        return _err("No valid fields")
    with get_connection(DB) as conn:
        conn.execute(
            "UPDATE customers SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?",
            list(updates.values()) + [cid]
        )
        conn.commit()
    return _ok({"customer_id": cid, "updated": list(updates.keys())})


@app.route("/api/customers/<int:cid>/invoices", methods=["GET"])
def customer_invoices(cid):
    with get_connection(DB) as conn:
        invs = conn.execute(
            "SELECT * FROM invoices WHERE customer_id=? ORDER BY due_date DESC", (cid,)
        ).fetchall()
        hist = conn.execute(
            "SELECT * FROM payment_history WHERE customer_id=? ORDER BY issue_date DESC", (cid,)
        ).fetchall()
        cust = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    if not cust:
        return _err("Customer not found", 404)
    return _ok({
        "customer": dict(cust),
        "invoices": [dict(r) for r in invs],
        "payment_history": [dict(r) for r in hist],
    })


@app.route("/api/customers/<int:cid>/profile", methods=["GET"])
def customer_profile(cid):
    from forecasting.behaviour_model import build_lateness_profiles
    import dataclasses
    profiles = build_lateness_profiles(DB)
    p = profiles.get(cid)
    if not p:
        return _err("No ML profile (no open invoices)", 404)
    return _ok(dataclasses.asdict(p))


# ════════════════════════════════════════════════════════════════════════════
# Vendors
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/vendors", methods=["GET"])
def list_vendors():
    with get_connection(DB) as conn:
        rows = conn.execute("""
            SELECT v.*,
                   COALESCE(SUM(CASE WHEN p.status='pending' THEN p.amount ELSE 0 END),0) AS ap_outstanding,
                   count(CASE WHEN p.status='pending' THEN 1 END) AS open_payables
            FROM vendors v LEFT JOIN payables p ON p.vendor_id = v.id
            GROUP BY v.id ORDER BY ap_outstanding DESC
        """).fetchall()
    return _ok({"vendors": [dict(r) for r in rows], "total": len(rows)})


@app.route("/api/vendors", methods=["POST"])
def create_vendor():
    d = request.get_json(force=True)
    if not d.get("name"):
        return _err("name is required")
    with get_connection(DB) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO vendors (name, category) VALUES (?,?)",
                (d["name"], d.get("category","general"))
            )
            conn.commit()
        except Exception as e:
            return _err(str(e))
    return _ok({"vendor_id": cur.lastrowid, "status": "created"}, 201)


@app.route("/api/vendors/<int:vid>", methods=["GET"])
def get_vendor(vid):
    with get_connection(DB) as conn:
        row = conn.execute("SELECT * FROM vendors WHERE id=?", (vid,)).fetchone()
    return _ok(dict(row)) if row else _err("Not found", 404)


# ════════════════════════════════════════════════════════════════════════════
# Alerts / Message Center
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/alerts/message-center")
def message_center():
    """All overdue + unpaid invoices with chase status and draft messages."""
    balance = float(request.args.get("balance", _get_settings().get("starting_balance", 300000)))
    result  = _run(balance)

    invoices = get_unpaid_invoices(DB)
    today    = datetime.today()

    # Build chase count per invoice
    with get_connection(DB) as conn:
        chase_counts = {
            r["invoice_id"]: r["cnt"]
            for r in conn.execute(
                "SELECT invoice_id, count(*) AS cnt FROM chase_log GROUP BY invoice_id"
            ).fetchall()
        }
        customers = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM customers").fetchall()}

    items = []
    for inv in invoices:
        due     = datetime.strptime(inv["due_date"], "%Y-%m-%d")
        overdue = (today - due).days

        cust    = customers.get(inv["customer_id"], {})
        phone   = cust.get("phone") or ""
        email   = cust.get("email") or ""
        name    = inv.get("customer_name", "Customer")
        amount  = inv["amount"]

        # Build message templates
        if overdue > 0:
            wa_text = (f"Hi {name}, your Invoice #{inv['id']} (₹{amount:,.0f}) "
                       f"is {overdue} days overdue. Please arrange payment at your earliest. "
                       f"Thank you!")
            email_subject = f"Payment Overdue — Invoice #{inv['id']}"
            email_body    = (f"Dear {name},\n\nWe hope this message finds you well.\n\n"
                             f"Invoice #{inv['id']} for ₹{amount:,.0f} (due {inv['due_date']}) "
                             f"is currently {overdue} days overdue.\n\n"
                             f"We request you to please clear this at the earliest to avoid any disruption.\n\n"
                             f"If payment has already been made, please share the transaction details.\n\n"
                             f"Best regards")
        else:
            days_left = abs(overdue)
            wa_text = (f"Hi {name}, a friendly reminder that Invoice #{inv['id']} "
                       f"(₹{amount:,.0f}) is due in {days_left} days on {inv['due_date']}. "
                       f"Please let us know if you need anything!")
            email_subject = f"Payment Reminder — Invoice #{inv['id']}"
            email_body    = (f"Dear {name},\n\nThis is a friendly reminder that "
                             f"Invoice #{inv['id']} for ₹{amount:,.0f} is due on {inv['due_date']}.\n\n"
                             f"Please arrange payment before the due date.\n\nBest regards")

        wa_link    = f"https://wa.me/91{phone.replace(' ','').replace('-','')}?text={wa_text.replace(' ', '%20')}" if phone else None
        mailto_link = f"mailto:{email}?subject={email_subject.replace(' ', '%20')}&body={email_body.replace(chr(10), '%0A').replace(' ', '%20')}" if email else None

        items.append({
            "invoice_id":       inv["id"],
            "customer_id":      inv["customer_id"],
            "customer_name":    name,
            "customer_phone":   phone,
            "customer_email":   email,
            "amount":           float(amount),
            "due_date":         inv["due_date"],
            "status":           inv["status"],
            "days_overdue":     overdue,
            "chase_count":      chase_counts.get(inv["id"], 0),
            "wa_message":       wa_text,
            "wa_link":          wa_link,
            "email_subject":    email_subject,
            "email_body":       email_body,
            "mailto_link":      mailto_link,
        })

    items.sort(key=lambda x: x["days_overdue"], reverse=True)

    return _ok({
        "items":     items,
        "total":     len(items),
        "alert":     _fmt_alert(result.alert),
    })


# ════════════════════════════════════════════════════════════════════════════
# Analytics
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/analytics/summary")
def analytics_summary():
    with get_connection(DB) as conn:
        total_ar     = conn.execute("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status IN ('unpaid','overdue')").fetchone()[0]
        total_ap     = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payables WHERE status='pending'").fetchone()[0]
        overdue_cnt  = conn.execute("SELECT count(*) FROM invoices WHERE status='overdue'").fetchone()[0]
        overdue_val  = conn.execute("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status='overdue'").fetchone()[0]
        paid_30d     = conn.execute("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status='paid' AND paid_date >= date('now','-30 days')").fetchone()[0]
        breakdown    = conn.execute("SELECT status, count(*) n, COALESCE(SUM(amount),0) val FROM invoices GROUP BY status").fetchall()
        rev_90d      = conn.execute("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE paid_date >= date('now','-90 days')").fetchone()[0]
        monthly      = conn.execute("""
            SELECT strftime('%Y-%m', issue_date) AS month,
                   COALESCE(SUM(amount),0) AS invoiced,
                   COALESCE(SUM(CASE WHEN status='paid' THEN amount ELSE 0 END),0) AS collected
            FROM invoices WHERE issue_date >= date('now','-6 months')
            GROUP BY month ORDER BY month
        """).fetchall()
        aging        = conn.execute("""
            SELECT
              COALESCE(SUM(CASE WHEN julianday('now')-julianday(due_date) <= 30 THEN amount END),0) AS age_0_30,
              COALESCE(SUM(CASE WHEN julianday('now')-julianday(due_date) BETWEEN 31 AND 60 THEN amount END),0) AS age_31_60,
              COALESCE(SUM(CASE WHEN julianday('now')-julianday(due_date) BETWEEN 61 AND 90 THEN amount END),0) AS age_61_90,
              COALESCE(SUM(CASE WHEN julianday('now')-julianday(due_date) > 90 THEN amount END),0) AS age_90_plus
            FROM invoices WHERE status IN ('unpaid','overdue')
        """).fetchone()

    dso = round(float(total_ar) / float(rev_90d) * 90, 1) if rev_90d > 0 else None
    return _ok({
        "total_ar":      float(total_ar),
        "total_ap":      float(total_ap),
        "overdue_count": overdue_cnt,
        "overdue_value": float(overdue_val),
        "collected_30d": float(paid_30d),
        "dso_days":      dso,
        "invoice_breakdown": [dict(r) for r in breakdown],
        "monthly_trend": [dict(r) for r in monthly],
        "aging_buckets": dict(aging) if aging else {},
    })


@app.route("/api/analytics/cashflow")
def analytics_cashflow():
    balance = float(request.args.get("balance", _get_settings().get("starting_balance", 300000)))
    days    = int(request.args.get("days", 30))
    result  = _run(balance)
    f       = result.forecast
    mc      = result.monte_carlo
    bal  = f.daily_balance if isinstance(f.daily_balance, list) else f.daily_balance.tolist()
    inf  = f.daily_inflows  if isinstance(f.daily_inflows, list)  else f.daily_inflows.tolist()
    out  = f.daily_outflows if isinstance(f.daily_outflows, list) else f.daily_outflows.tolist()
    data = [
        {"date": f.dates[i], "balance": round(bal[i],2), "inflow": round(inf[i],2),
         "outflow": round(out[i],2), "net": round(inf[i]-out[i],2),
         "p25": round(mc.p25[i],2), "p75": round(mc.p75[i],2)}
        for i in range(min(days, len(f.dates)))
    ]
    return _ok({"cashflow": data})


@app.route("/api/analytics/customers")
def analytics_customers():
    from forecasting.behaviour_model import build_lateness_profiles
    profiles = build_lateness_profiles(DB)
    with get_connection(DB) as conn:
        rows = conn.execute("""
            SELECT c.id, c.name, c.industry, c.region,
                   COALESCE(SUM(CASE WHEN i.status IN ('unpaid','overdue') THEN i.amount ELSE 0 END),0) AS ar_outstanding,
                   count(CASE WHEN i.status IN ('unpaid','overdue') THEN 1 END) AS open_invoices,
                   count(CASE WHEN i.status='overdue' THEN 1 END) AS overdue_invoices
            FROM customers c LEFT JOIN invoices i ON i.customer_id = c.id
            GROUP BY c.id ORDER BY ar_outstanding DESC
        """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        p = profiles.get(r["id"])
        d.update({
            "p_late":         round(p.p_late, 4) if p else None,
            "expected_delay": round(p.expected_delay_days, 1) if p else None,
            "confidence":     p.confidence if p else "none",
            "profile_tier":   p.tier if p else 0,
        })
        result.append(d)
    return _ok({"customers": result})


# ════════════════════════════════════════════════════════════════════════════
# Settings
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return _ok(_get_settings())


@app.route("/api/settings", methods=["POST"])
def save_settings():
    d = request.get_json(force=True)
    allowed = set(_DEFAULT_SETTINGS.keys())
    with get_connection(DB) as conn:
        for k, v in d.items():
            if k in allowed:
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)",
                    (k, str(v))
                )
        conn.commit()
    return _ok({"status": "saved", "updated": [k for k in d if k in allowed]})


# ════════════════════════════════════════════════════════════════════════════
# Export
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/export/invoices.csv")
def export_invoices():
    with get_connection(DB) as conn:
        rows = conn.execute("""
            SELECT i.id, c.name AS customer, i.amount, i.issue_date, i.due_date,
                   i.status, i.paid_date, i.category
            FROM invoices i JOIN customers c ON i.customer_id=c.id ORDER BY i.due_date
        """).fetchall()
    output = io.StringIO()
    w = csv.DictWriter(output, fieldnames=["id","customer","amount","issue_date","due_date","status","paid_date","category"])
    w.writeheader()
    for r in rows: w.writerow(dict(r))
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=invoices.csv"})


@app.route("/api/export/payables.csv")
def export_payables():
    with get_connection(DB) as conn:
        rows = conn.execute("""
            SELECT p.id, v.name AS vendor, p.amount, p.due_date, p.category, p.status
            FROM payables p JOIN vendors v ON p.vendor_id=v.id ORDER BY p.due_date
        """).fetchall()
    output = io.StringIO()
    w = csv.DictWriter(output, fieldnames=["id","vendor","amount","due_date","category","status"])
    w.writeheader()
    for r in rows: w.writerow(dict(r))
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=payables.csv"})


# ════════════════════════════════════════════════════════════════════════════
# Ingestion
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/ingest/seed", methods=["POST"])
def ingest_seed():
    load_sample_data(DB)
    return _ok({"status": "seeded"})


# ── Smart Import ─────────────────────────────────────────────────────────────

@app.route("/api/ingest/smart", methods=["POST"])
def ingest_smart_extract():
    """
    Accept one or more uploaded files (WhatsApp .txt, PDF, JPG/PNG),
    run the appropriate parser, and return a preview list of extracted rows.
    Does NOT write to the DB — that happens in /api/ingest/smart/confirm.
    """
    import tempfile
    from ingestion.whatsapp_parser import parse_whatsapp_txt
    from ingestion.document_parser  import parse_document

    files = request.files.getlist("files")
    if not files:
        return _err("No files uploaded", 400)

    all_rows = []
    for f in files:
        filename = f.filename or "upload"
        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext == ".txt":
                content = f.read().decode("utf-8", errors="ignore")
                rows = parse_whatsapp_txt(content, source_filename=filename)
                all_rows.extend(rows)

            elif ext in (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                # Write to a temp file so pdfplumber / pytesseract can open it
                suffix = ext
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    f.save(tmp.name)
                    tmp_path = tmp.name
                try:
                    rows = parse_document(tmp_path, source_filename=filename)
                    all_rows.extend(rows)
                finally:
                    os.unlink(tmp_path)

            else:
                all_rows.append({
                    "source": "unknown",
                    "filename": filename,
                    "error": f"Unsupported file type: {ext}",
                    "confidence": "none",
                })

        except Exception as e:
            all_rows.append({
                "source": ext.lstrip(".") or "unknown",
                "filename": filename,
                "error": str(e),
                "confidence": "none",
            })

    # Assign a stable preview id so the frontend can key rows
    for i, row in enumerate(all_rows):
        row["_id"] = i

    return _ok({"rows": all_rows, "total": len(all_rows)})


@app.route("/api/ingest/smart/confirm", methods=["POST"])
def ingest_smart_confirm():
    """
    Commit user-confirmed rows to the DB.

    Body (JSON):
        { "rows": [ { party, amount, date, type, category }, ... ] }

    type must be "invoice" | "payable" | "payment".
    Returns counts of inserted records.
    """
    from datetime import datetime as dt
    from ingestion.fuzzy_match import get_or_create_customer, get_or_create_vendor

    body = request.get_json(force=True) or {}
    rows = body.get("rows", [])
    if not rows:
        return _err("No rows to import", 400)

    counts = {"invoice": 0, "payable": 0, "payment": 0, "skipped": 0}
    errors = []

    with get_connection(DB) as conn:
        for row in rows:
            try:
                rtype    = str(row.get("type", "invoice")).lower()
                party    = str(row.get("party") or "").strip()
                amount   = float(row.get("amount") or 0)
                date_str = str(row.get("date") or dt.today().strftime("%Y-%m-%d"))
                category = str(row.get("category") or "general")

                if not party or amount <= 0:
                    counts["skipped"] += 1
                    continue

                if rtype == "invoice" or rtype == "receipt" or rtype == "payment":
                    cid = get_or_create_customer(party, conn)
                    # Default due_date = issue_date + 30 days
                    try:
                        issue_dt = dt.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        issue_dt = dt.today()
                    from datetime import timedelta
                    due_date = (issue_dt + timedelta(days=30)).strftime("%Y-%m-%d")
                    status   = "paid" if rtype == "payment" else "unpaid"
                    paid_date = date_str if rtype == "payment" else None
                    conn.execute(
                        "INSERT INTO invoices (customer_id, amount, issue_date, due_date, status, paid_date, category) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (cid, amount, date_str, due_date, status, paid_date, category)
                    )
                    counts["invoice"] += 1

                elif rtype == "payable":
                    vid = get_or_create_vendor(party, conn)
                    conn.execute(
                        "INSERT INTO payables (vendor_id, amount, due_date, category, status) VALUES (?,?,?,?,?)",
                        (vid, amount, date_str, category, "pending")
                    )
                    counts["payable"] += 1

                else:
                    counts["skipped"] += 1

            except Exception as e:
                errors.append(str(e))
                counts["skipped"] += 1

        conn.commit()

    return _ok({"counts": counts, "errors": errors[:10]})


# ════════════════════════════════════════════════════════════════════════════
# Bootstrap
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db(DB)
    print("[Flask] Starting API server on http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=True)
