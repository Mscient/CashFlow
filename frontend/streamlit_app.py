"""
streamlit_app.py — Cash-Flow Blindspot Dashboard (Phase 6 / P6)

Premium dark-mode dashboard with:
  ✦ Glassmorphism alert banner (colour-coded by tier)
  ✦ Monte Carlo probability band chart (Plotly)
  ✦ Expected-Risk ranked invoice table with one-tap message drafts
  ✦ Delayable payables panel
  ✦ Real-time metrics row (shortfall prob, runway, AR, AP)
  ✦ Mark-as-paid action → st.rerun() loops the pipeline
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import os
import sys
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_root, "backend"))

from config import DB_PATH, SAMPLE_CSV_PATH
from db.database import init_db, load_sample_data, mark_invoice_paid, get_connection
from scheduler.daily_job import run_daily_job

DB = os.path.join(_root, DB_PATH)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CashFlow Blindspot | MSME Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS — dark glassmorphism theme ─────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark background */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0f1629 50%, #0a1220 100%);
    color: #e8eaf6;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: rgba(15, 22, 45, 0.95);
    border-right: 1px solid rgba(99, 120, 255, 0.2);
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px 24px;
    backdrop-filter: blur(10px);
    transition: transform 0.2s ease, border-color 0.2s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    border-color: rgba(99, 120, 255, 0.4);
}

/* Alert banner */
.alert-banner {
    border-radius: 16px;
    padding: 20px 28px;
    margin: 16px 0;
    backdrop-filter: blur(12px);
    border: 1px solid;
    animation: fadeIn 0.5s ease;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-8px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* Suggestion card */
.suggestion-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 18px 22px;
    margin-bottom: 12px;
    transition: all 0.2s ease;
}
.suggestion-card:hover {
    background: rgba(99, 120, 255, 0.08);
    border-color: rgba(99, 120, 255, 0.3);
    transform: translateX(4px);
}

/* Message box */
.message-box {
    background: rgba(52, 199, 89, 0.08);
    border: 1px solid rgba(52, 199, 89, 0.3);
    border-radius: 10px;
    padding: 14px 18px;
    font-family: monospace;
    font-size: 0.88rem;
    color: #a8f0b8;
    margin-top: 10px;
    white-space: pre-wrap;
}

/* Section headers */
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #c5cae9;
    letter-spacing: 0.5px;
    margin: 24px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}

/* Confidence badge */
.badge-high   { background: rgba(52,199,89,0.15);  color:#34c759; border: 1px solid rgba(52,199,89,0.4);  border-radius:6px; padding:2px 8px; font-size:0.78rem; }
.badge-medium { background: rgba(255,149,0,0.15);  color:#ff9500; border: 1px solid rgba(255,149,0,0.4);  border-radius:6px; padding:2px 8px; font-size:0.78rem; }
.badge-low    { background: rgba(255,59,48,0.15);  color:#ff3b30; border: 1px solid rgba(255,59,48,0.4);  border-radius:6px; padding:2px 8px; font-size:0.78rem; }

/* Overdue badge */
.overdue { color: #ff6b6b; font-weight: 600; }
.upcoming { color: #ffd93d; }

/* Logo area */
.logo-text {
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, #6378ff, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* Plotly chart background */
.js-plotly-plot .plotly .main-svg {
    border-radius: 16px;
}

/* Button styling */
.stButton > button {
    background: linear-gradient(135deg, rgba(99,120,255,0.2), rgba(167,139,250,0.2));
    border: 1px solid rgba(99,120,255,0.4);
    color: #c5cae9;
    border-radius: 10px;
    font-weight: 500;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, rgba(99,120,255,0.35), rgba(167,139,250,0.35));
    border-color: rgba(99,120,255,0.7);
    transform: translateY(-1px);
}

/* Divider */
hr { border-color: rgba(255,255,255,0.08); }

/* Hide Streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Database initialisation ───────────────────────────────────────────────────
@st.cache_resource
def setup_db():
    init_db(DB)
    # Load sample data if DB is empty
    conn = get_connection(DB)
    count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    conn.close()
    if count == 0:
        csv_path = os.path.join(_root, SAMPLE_CSV_PATH)
        load_sample_data(DB, csv_path)
    return True

setup_db()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="logo-text">💰 CashFlow Blindspot</div>', unsafe_allow_html=True)
    st.markdown("*MSME Cash Intelligence Dashboard*")
    st.markdown("---")

    st.markdown("### ⚙️ Settings")
    starting_balance = st.number_input(
        "Current Bank Balance (₹)",
        min_value=0,
        max_value=10_000_000,
        value=350_000,
        step=10_000,
        format="%d",
        help="Enter your current cash/bank balance"
    )

    st.markdown("---")
    st.markdown("### 📊 About")
    st.markdown("""
    **3-Layer AI Engine:**
    - 🧠 Survival-based payment model
    - 📈 Monte Carlo simulation (2,000 paths)
    - ⚡ Expected-Risk optimizer

    Built by **PVPIT CE Dept.**
    """)

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── Run pipeline ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def get_job_result(balance: float):
    return run_daily_job(balance, DB)

with st.spinner("Running AI pipeline…"):
    result = get_job_result(starting_balance)

forecast    = result.forecast
mc          = result.monte_carlo
alert       = result.alert
suggestions = result.suggestions
profiles    = result.profiles


# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_date = st.columns([3, 1])
with col_title:
    st.markdown("## 💰 Cash-Flow Blindspot")
    st.markdown("*Proactive cash intelligence for your MSME*")
with col_date:
    st.markdown(f"<br><div style='text-align:right; color:#6b7280; font-size:0.85rem;'>📅 {datetime.today().strftime('%d %B %Y')}</div>", unsafe_allow_html=True)

st.markdown("---")


# ── Alert Banner ──────────────────────────────────────────────────────────────
color       = alert.color
tier        = alert.tier
tier_opacity_map = {"CRITICAL":"22","WARNING":"18","INFO":"15","NONE":"12"}
bg_opacity  = tier_opacity_map.get(tier, "12")

st.markdown(f"""
<div class="alert-banner" style="
    background: {color}{bg_opacity};
    border-color: {color}66;
    box-shadow: 0 0 30px {color}22;
">
    <div style="font-size:1.5rem; font-weight:700; color:{color};">
        {alert.emoji} &nbsp; {alert.headline}
    </div>
    <div style="margin-top:8px; color:#c5cae9; font-size:0.95rem; line-height:1.6;">
        {alert.detail}
    </div>
</div>
""", unsafe_allow_html=True)


# ── Metrics Row ───────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)

runway = forecast.days_to_shortfall
shortfall_pct = f"{mc.peak_shortfall_prob:.0%}"

with m1:
    st.metric("💳 Balance", f"₹{starting_balance:,.0f}")
with m2:
    st.metric("📥 AR Outstanding", f"₹{forecast.total_ar:,.0f}")
with m3:
    st.metric("📤 AP Pending", f"₹{forecast.total_ap:,.0f}")
with m4:
    st.metric("⚠️ Shortfall Risk", shortfall_pct,
              delta=f"{runway}d runway" if runway else "Safe",
              delta_color="inverse" if runway and runway < 14 else "normal")
with m5:
    net_pos = forecast.ending_balance
    st.metric("📊 90d Net Position", f"₹{net_pos:,.0f}",
              delta_color="normal" if net_pos > 0 else "inverse")

st.markdown("---")


# ── Monte Carlo Chart ─────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📈 Cash Position Forecast (90-Day Monte Carlo)</div>',
            unsafe_allow_html=True)

dates      = mc.dates
fig = go.Figure()

# P5-P95 confidence band
fig.add_trace(go.Scatter(
    x=dates + dates[::-1],
    y=mc.p95 + mc.p5[::-1],
    fill='toself',
    fillcolor='rgba(99,120,255,0.08)',
    line=dict(color='rgba(255,255,255,0)'),
    showlegend=True,
    name='P5–P95 band',
    hoverinfo='skip',
))

# P25-P75 band
fig.add_trace(go.Scatter(
    x=dates + dates[::-1],
    y=mc.p75 + mc.p25[::-1],
    fill='toself',
    fillcolor='rgba(99,120,255,0.15)',
    line=dict(color='rgba(255,255,255,0)'),
    showlegend=True,
    name='P25–P75 band',
    hoverinfo='skip',
))

# Median line
fig.add_trace(go.Scatter(
    x=dates, y=mc.p50,
    mode='lines',
    line=dict(color='#6378ff', width=2.5),
    name='Median (P50)',
))

# Deterministic best-estimate
fig.add_trace(go.Scatter(
    x=forecast.dates, y=forecast.daily_balance,
    mode='lines',
    line=dict(color='#a78bfa', width=1.5, dash='dot'),
    name='Best Estimate',
))

# Zero line
fig.add_hline(y=0, line_color='rgba(255,59,48,0.6)', line_width=1.5,
              line_dash='dash', annotation_text='Zero balance',
              annotation_font_color='#ff3b30', annotation_position='bottom right')

# Shortfall marker
if forecast.first_shortfall_date:
    fig.add_vline(
        x=forecast.first_shortfall_date,
        line_color=alert.color, line_width=1.5, line_dash='dash',
        annotation_text=f"⚠ {alert.tier}",
        annotation_font_color=alert.color,
    )

fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(255,255,255,0.02)',
    font=dict(family='Inter', color='#c5cae9', size=13),
    legend=dict(
        orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
        bgcolor='rgba(0,0,0,0)', font=dict(size=12),
    ),
    xaxis=dict(
        showgrid=True, gridcolor='rgba(255,255,255,0.05)',
        tickfont=dict(size=11), tickangle=-30,
    ),
    yaxis=dict(
        showgrid=True, gridcolor='rgba(255,255,255,0.05)',
        tickformat='₹,.0f', tickprefix='',
        tickfont=dict(size=11),
        title='Cash Balance (₹)',
    ),
    hovermode='x unified',
    margin=dict(l=20, r=20, t=40, b=20),
    height=420,
)

# Format Y axis in lakhs
fig.update_yaxes(tickformat=',.0f')

st.plotly_chart(fig, use_container_width=True)


# ── Suggestions & Ranked Invoices ─────────────────────────────────────────────
st.markdown("---")
left_col, right_col = st.columns([3, 2])

with left_col:
    st.markdown('<div class="section-header">⚡ Recommended Actions</div>',
                unsafe_allow_html=True)

    if suggestions.gap > 0:
        st.markdown(f"""
        <div style="background:rgba(255,149,0,0.08); border:1px solid rgba(255,149,0,0.3);
                    border-radius:12px; padding:14px 18px; margin-bottom:16px;">
            💡 <b>Gap to close: ₹{suggestions.gap:,.0f}</b> &nbsp;|&nbsp;
            {suggestions.summary}
        </div>
        """, unsafe_allow_html=True)

    # Invoice suggestions
    for i, inv in enumerate(suggestions.invoice_suggestions[:8]):
        overdue_class = "overdue" if inv.days_overdue > 0 else "upcoming"
        overdue_text  = (f"<span class='{overdue_class}'>{inv.days_overdue}d overdue</span>"
                         if inv.days_overdue > 0
                         else f"<span class='upcoming'>due {inv.due_date}</span>")
        conf_badge    = f'<span class="badge-{inv.confidence}">{inv.confidence}</span>'

        with st.expander(
            f"#{i+1}  {inv.customer_name}  —  ₹{inv.amount:,.0f}  |  "
            f"Risk score: {inv.expected_risk:,.0f}",
            expanded=(i < 2)
        ):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Status:** {overdue_text}", unsafe_allow_html=True)
            c2.markdown(f"**P(late):** {inv.p_late:.0%}")
            c3.markdown(f"**Confidence:** {conf_badge}", unsafe_allow_html=True)

            st.markdown(f"**Invoice #{inv.invoice_id}** · Expected delay: {inv.expected_delay:+.0f} days")

            st.markdown(f"""
            <div class="message-box">📱 Draft message:\n\n{inv.draft_message}</div>
            """, unsafe_allow_html=True)

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button(f"✅ Mark as Paid", key=f"paid_{inv.invoice_id}"):
                    mark_invoice_paid(inv.invoice_id, db_path=DB)
                    st.cache_data.clear()
                    st.success(f"Invoice #{inv.invoice_id} marked paid!")
                    st.rerun()
            with btn_col2:
                st.button(f"📋 Copy Message", key=f"copy_{inv.invoice_id}",
                          help=inv.draft_message)


with right_col:
    st.markdown('<div class="section-header">🔄 Deferrable Payables</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:0.82rem; color:#6b7280; margin-bottom:12px;">
        Discretionary payables that can be safely delayed without damaging supplier relationships.
    </div>
    """, unsafe_allow_html=True)

    if suggestions.payable_suggestions:
        for pay in suggestions.payable_suggestions:
            due_in = pay.days_until_due
            urgency_color = "#ff6b6b" if due_in <= 3 else "#ffd93d" if due_in <= 7 else "#a8f0b8"
            st.markdown(f"""
            <div class="suggestion-card">
                <div style="font-weight:600; color:#c5cae9;">{pay.vendor_name}</div>
                <div style="font-size:1.1rem; font-weight:700; color:#6378ff; margin:4px 0;">
                    ₹{pay.amount:,.0f}
                </div>
                <div style="font-size:0.82rem; color:{urgency_color};">
                    Due in {due_in}d &nbsp;·&nbsp; {pay.category.title()}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No discretionary payables found.")

    # ── Customer Profiles ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🧠 Customer Risk Profiles</div>',
                unsafe_allow_html=True)

    if profiles:
        profile_data = []
        for p in profiles.values():
            profile_data.append({
                "Customer":     p.customer_name,
                "Avg Delay":    f"{p.expected_delay_days:+.0f}d",
                "P(Late)":      f"{p.p_late:.0%}",
                "Tier":         f"T{p.tier}",
                "Confidence":   p.confidence.title(),
                "History":      f"{p.invoice_count} inv",
            })

        df_profiles = pd.DataFrame(profile_data)
        st.dataframe(
            df_profiles,
            use_container_width=True,
            hide_index=True,
        )


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#374151; font-size:0.8rem; padding:12px 0;">
    Cash-Flow Blindspot · PVPIT Computer Engineering Department ·
    Built for MSME cash intelligence hackathon
</div>
""", unsafe_allow_html=True)
