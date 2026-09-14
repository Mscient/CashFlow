import { useState, useEffect, useCallback } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  AlertTriangle, CheckCircle, Bell, Wallet,
  TrendingUp, TrendingDown, Clock, MessageSquare,
  RefreshCw, ChevronRight, ShieldAlert, Activity,
} from 'lucide-react';
import { fetchDashboard, markInvoicePaid } from '../api';

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const INR = (v) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 0,
  }).format(v);

const pct = (v) => `${(v * 100).toFixed(1)}%`;

const TIER_STYLES = {
  0: { cls: 'alert-ok',     icon: CheckCircle,    label: 'Healthy' },
  1: { cls: 'alert-red',    icon: ShieldAlert,    label: 'Critical' },
  2: { cls: 'alert-orange', icon: AlertTriangle,  label: 'Warning' },
  NONE: { cls: 'alert-ok',  icon: CheckCircle,    label: 'Healthy' },
};

/* ── Custom chart tooltip ────────────────────────────────────────────────── */
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__date">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color || p.stroke || '#fff' }}>
          {p.name}: <strong>{INR(p.value)}</strong>
        </p>
      ))}
    </div>
  );
};

/* ── Metric Card ─────────────────────────────────────────────────────────── */
function MetricCard({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className={`metric-card ${accent ? `metric-card--${accent}` : ''}`}>
      <div className="metric-card__icon"><Icon size={20} /></div>
      <div>
        <p className="metric-card__label">{label}</p>
        <p className="metric-card__value">{value}</p>
        {sub && <p className="metric-card__sub">{sub}</p>}
      </div>
    </div>
  );
}

/* ── Invoice Row ─────────────────────────────────────────────────────────── */
function InvoiceRow({ inv, onPaid, onMessage }) {
  const [paying, setPaying] = useState(false);
  const risk = inv.p_late > 0.65 ? 'high' : inv.p_late > 0.35 ? 'mid' : 'low';

  const handlePay = async () => {
    setPaying(true);
    try { await onPaid(inv.invoice_id); } finally { setPaying(false); }
  };

  return (
    <tr className="table-row">
      <td>
        <p className="fw-600">{inv.customer_name}</p>
        <p className="text-muted text-sm">
          {inv.days_overdue > 0 ? `${inv.days_overdue}d overdue` : `due ${inv.due_date}`}
        </p>
      </td>
      <td className="fw-600">{INR(inv.amount)}</td>
      <td>
        <span className={`badge badge--${risk}`}>{pct(inv.p_late)}</span>
      </td>
      <td>{INR(inv.expected_risk)}</td>
      <td>
        <div className="row-actions">
          <button
            className="btn btn--ghost btn--sm"
            title="Draft message"
            onClick={() => onMessage(inv.draft_message)}
          >
            <MessageSquare size={14} />
          </button>
          <button
            className={`btn btn--primary btn--sm ${paying ? 'btn--loading' : ''}`}
            onClick={handlePay}
            disabled={paying}
          >
            {paying ? <RefreshCw size={14} className="spin" /> : <CheckCircle size={14} />}
            {paying ? 'Saving…' : 'Mark Paid'}
          </button>
        </div>
      </td>
    </tr>
  );
}

/* ── Message Modal ───────────────────────────────────────────────────────── */
function MessageModal({ message, onClose }) {
  if (!message) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal__title">📲 Draft WhatsApp / SMS</h3>
        <pre className="modal__body">{message}</pre>
        <div className="modal__actions">
          <button className="btn btn--ghost" onClick={onClose}>Close</button>
          <button className="btn btn--primary" onClick={() => {
            navigator.clipboard?.writeText(message);
          }}>Copy to Clipboard</button>
        </div>
      </div>
    </div>
  );
}

/* ── Main Dashboard ──────────────────────────────────────────────────────── */
export default function Dashboard() {
  const [balance, setBalance] = useState(300000);
  const [inputBalance, setInputBalance] = useState('300000');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [draftMsg, setDraftMsg] = useState(null);

  const load = useCallback(async (bal) => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchDashboard(bal);
      setData(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(balance); }, [balance, load]);

  const handleMarkPaid = async (id) => {
    await markInvoicePaid(id);
    load(balance);
  };

  const applyBalance = () => {
    const v = parseFloat(inputBalance);
    if (!isNaN(v) && v >= 0) setBalance(v);
  };

  /* chart data */
  const chartData = data
    ? data.forecast.dates.map((date, i) => ({
        date,
        Balance: data.forecast.daily_balance[i],
        P25:     data.forecast.p25[i],
        P75:     data.forecast.p75[i],
        P5:      data.forecast.p5[i],
        P95:     data.forecast.p95[i],
      }))
    : [];

  const tier = data?.alert?.tier ?? 'NONE';
  const tierStyle = TIER_STYLES[tier] ?? TIER_STYLES.NONE;
  const TierIcon = tierStyle.icon;

  /* ── Render ─────────────────────────────────────────────────────────────── */
  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar__logo">
          <Wallet size={28} className="sidebar__logo-icon" />
          <div>
            <p className="sidebar__title">CashFlow</p>
            <p className="sidebar__sub">Blindspot AI</p>
          </div>
        </div>

        <nav className="sidebar__nav">
          <a className="sidebar__link sidebar__link--active" href="#">
            <Activity size={16} /> Overview
          </a>
          <a className="sidebar__link" href="#">
            <TrendingUp size={16} /> Receivables
          </a>
          <a className="sidebar__link" href="#">
            <TrendingDown size={16} /> Payables
          </a>
          <a className="sidebar__link" href="#">
            <Bell size={16} /> Alerts
          </a>
        </nav>

        <div className="sidebar__balance-input">
          <label>Starting Balance (₹)</label>
          <input
            type="number"
            value={inputBalance}
            onChange={(e) => setInputBalance(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applyBalance()}
          />
          <button className="btn btn--primary btn--full" onClick={applyBalance}>
            <RefreshCw size={14} /> Refresh Forecast
          </button>
        </div>

        <div className="sidebar__status">
          <span className={`status-dot status-dot--${tierStyle.cls}`} />
          <span>{tierStyle.label}</span>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        {/* Header */}
        <header className="page-header">
          <div>
            <h1 className="page-header__title">Liquidity Dashboard</h1>
            <p className="page-header__sub">90-day Monte Carlo cash-flow forecast</p>
          </div>
          {loading && (
            <div className="loading-badge">
              <RefreshCw size={14} className="spin" /> Computing…
            </div>
          )}
        </header>

        {error && (
          <div className="error-banner">
            <AlertTriangle size={20} />
            <span>API Error: {error}. Is the Flask backend running on port 5000?</span>
          </div>
        )}

        {/* Alert Banner */}
        {data && tier !== 0 && tier !== 'NONE' && (
          <div className={`alert-banner ${tierStyle.cls}`}>
            <TierIcon size={24} />
            <div>
              <p className="alert-banner__headline">{data.alert.headline}</p>
              <p className="alert-banner__detail">{data.alert.detail}</p>
            </div>
            <div className="alert-banner__meta">
              <span>P(shortfall)</span>
              <strong>{pct(data.alert.probability)}</strong>
            </div>
          </div>
        )}

        {/* Metric Cards */}
        <div className="metrics-grid">
          <MetricCard
            icon={Clock}
            label="Cash Runway"
            value={data?.forecast.days_to_shortfall != null
              ? `${data.forecast.days_to_shortfall} days`
              : '90+ days'}
            sub="until shortfall"
          />
          <MetricCard
            icon={TrendingUp}
            label="Total Receivables"
            value={data ? INR(data.forecast.total_ar) : '—'}
            sub="unpaid invoices"
            accent="green"
          />
          <MetricCard
            icon={TrendingDown}
            label="Total Payables"
            value={data ? INR(data.forecast.total_ap) : '—'}
            sub="pending bills"
            accent="red"
          />
          <MetricCard
            icon={Activity}
            label="Peak Shortfall Prob."
            value={data ? pct(data.forecast.peak_shortfall_prob) : '—'}
            sub="across 90-day horizon"
            accent={data?.forecast.peak_shortfall_prob > 0.5 ? 'red' : 'green'}
          />
        </div>

        {/* Forecast Chart */}
        <div className="glass-card">
          <div className="card-header">
            <h2 className="card-title">90-Day Liquidity Forecast</h2>
            <div className="chart-legend">
              <span className="legend-item legend-item--blue">P25–P75 band</span>
              <span className="legend-item legend-item--primary">Median (P50)</span>
              <span className="legend-item legend-item--danger">Zero line</span>
            </div>
          </div>

          <div className="chart-wrap">
            {loading || !data ? (
              <div className="chart-skeleton" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                  <defs>
                    <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="p95Grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.08} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.00} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={28}
                  />
                  <YAxis
                    tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <ReferenceLine y={0} stroke="rgba(239,68,68,0.6)" strokeDasharray="4 3" strokeWidth={2} />
                  {/* Bands */}
                  <Area dataKey="P95" stroke="none" fill="url(#p95Grad)" isAnimationActive={false} />
                  <Area dataKey="P75" stroke="none" fill="url(#bandGrad)" isAnimationActive={false} />
                  <Area dataKey="P25" stroke="none" fill="var(--bg-base)" fillOpacity={1} isAnimationActive={false} />
                  {/* Lines */}
                  <Line dataKey="Balance" stroke="#60a5fa" strokeWidth={2.5} dot={false} activeDot={{ r: 5, fill: '#60a5fa' }} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Bottom Row */}
        <div className="bottom-grid">
          {/* Invoices Table */}
          <div className="glass-card">
            <div className="card-header">
              <h2 className="card-title">
                <TrendingUp size={18} /> High-Risk Invoices
              </h2>
              <span className="tag">Ranked by Expected Risk</span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Amount</th>
                    <th>P(Late)</th>
                    <th>Exp. Risk</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={5} className="text-center text-muted">Loading…</td></tr>
                  ) : data?.suggestions.invoices.length ? (
                    data.suggestions.invoices.map((inv) => (
                      <InvoiceRow
                        key={inv.invoice_id}
                        inv={inv}
                        onPaid={handleMarkPaid}
                        onMessage={setDraftMsg}
                      />
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="empty-state">
                        <CheckCircle size={24} /> All invoices on track!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Gap summary */}
            {data?.suggestions.gap > 0 && (
              <div className="gap-banner">
                <div>
                  <p className="text-muted text-sm">Projected Cash Gap</p>
                  <p className="fw-600 text-lg">{INR(data.suggestions.gap)}</p>
                </div>
                <ChevronRight size={16} className="text-muted" />
                <div>
                  <p className="text-muted text-sm">Closable via Actions</p>
                  <p className="fw-600 text-lg text-green">{INR(data.suggestions.gap_closable)}</p>
                </div>
                <ChevronRight size={16} className="text-muted" />
                <div>
                  <p className="text-muted text-sm">External Financing Needed</p>
                  <p className="fw-600 text-lg text-red">{INR(data.suggestions.financing_needed)}</p>
                </div>
              </div>
            )}
          </div>

          {/* Payables Table */}
          <div className="glass-card">
            <div className="card-header">
              <h2 className="card-title">
                <TrendingDown size={18} /> Delayable Payables
              </h2>
              <span className="tag">Discretionary only</span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Vendor</th>
                    <th>Amount</th>
                    <th>Due In</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={4} className="text-center text-muted">Loading…</td></tr>
                  ) : data?.suggestions.payables.length ? (
                    data.suggestions.payables.map((p) => (
                      <tr key={p.payable_id} className="table-row">
                        <td className="fw-600">{p.vendor_name}</td>
                        <td>{INR(p.amount)}</td>
                        <td>
                          <span className={`badge badge--${p.days_until_due < 10 ? 'high' : 'mid'}`}>
                            {p.days_until_due}d
                          </span>
                        </td>
                        <td>
                          <button className="btn btn--ghost btn--sm">Request Extension</button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="empty-state">
                        <CheckCircle size={24} /> No payables to delay
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>

      <MessageModal message={draftMsg} onClose={() => setDraftMsg(null)} />
    </div>
  );
}
