# config.py — Single source of truth for all tunable thresholds
# Never hardcode constants in logic modules; import from here instead.

# ── Forecast & simulation ─────────────────────────────────────────────────────
FORECAST_HORIZON_DAYS = 90          # How many days ahead to project cash position
MONTE_CARLO_RUNS = 2000             # Number of simulation paths to run
GRACE_PERIOD_DAYS = 3               # Days after due date before flagging as late

# ── Alert windows (days until shortfall triggers each tier) ───────────────────
ALERT_CRITICAL_DAYS = 7             # Red   — shortfall within N days
ALERT_WARNING_DAYS  = 14            # Orange — shortfall within N days
ALERT_INFO_DAYS     = 21            # Yellow — shortfall within N days

# ── Alert probability thresholds (Monte Carlo P(balance<0)) ──────────────────
ALERT_CRITICAL_PROB = 0.70          # Need ≥70% probability to fire CRITICAL
ALERT_WARNING_PROB  = 0.50          # Need ≥50% probability to fire WARNING
ALERT_INFO_PROB     = 0.30          # Need ≥30% probability to fire INFO

# ── Behaviour model ───────────────────────────────────────────────────────────
FUZZY_MATCH_THRESHOLD = 0.85        # difflib similarity ratio for name resolution
MIN_INVOICES_PERSONAL = 5           # Below this → use cohort prior
MIN_INVOICES_MATURE   = 30          # Above this → full hazard model eligible
SHRINKAGE_STRENGTH    = 0.40        # Bayesian shrinkage weight toward cohort mean
                                    # 0 = full personal, 1 = full cohort
RECENCY_HALF_LIFE     = 6           # Invoices older than N months get down-weighted

# ── Suggestion & optimization engine ─────────────────────────────────────────
CHASE_COST_DEFAULT          = 0.05  # Effort/relationship penalty per chase action
FINANCING_COST_DEFAULT      = 0.02  # Interest/fee fraction of credit drawn
P_ACCELERATED_SUCCESS_DEFAULT = 0.60  # P(chase actually pulls payment forward)
URGENCY_WINDOW_DAYS         = 7     # Days-to-payroll/deadline for urgency spike

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = "cashflow.db"
SAMPLE_CSV_PATH = "data/sample_transactions.csv"

# ── Invoice defaults ──────────────────────────────────────────────────────────
DEFAULT_PAYMENT_TERMS_DAYS = 30     # Net-30 if due_date not provided

# ── Message templates ─────────────────────────────────────────────────────────
CHASE_MESSAGE_TEMPLATE = (
    "Hi {customer_name}, following up on Invoice #{invoice_id} "
    "(₹{amount:,.0f}, due {days_overdue} days ago). "
    "Could you confirm an expected payment date? Thank you!"
)

UPCOMING_CHASE_TEMPLATE = (
    "Hi {customer_name}, a friendly reminder that Invoice #{invoice_id} "
    "(₹{amount:,.0f}) is due on {due_date}. "
    "Please let us know if you have any questions. Thank you!"
)
