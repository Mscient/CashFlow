import { useState, useEffect, useCallback } from 'react';
import { TrendingUp, TrendingDown, Clock, AlertTriangle, RefreshCw, Zap } from 'lucide-react';
import { fetchDashboard, fetchCashflow } from '../api';
import { MetricCard, SectionHeader, Badge, Spinner, EmptyState, fmtCurrency, fmtDate } from '../components/shared';

const BALANCE_KEY = 'cf_balance';

function CashflowChart({ data }) {
  if (!data || data.length === 0) return null;
  const vals  = data.map(d => d.balance);
  const min   = Math.min(...vals);
  const max   = Math.max(...vals);
  const range = max - min || 1;
  const W = 600, H = 180, PAD = 40;
  const pts = data.map((d, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2);
    const y = PAD + (1 - (d.balance - min) / range) * (H - PAD * 2);
    return `${x},${y}`;
  }).join(' ');
  const area = `M${pts.split(' ').join(' L')} L${W - PAD},${H - PAD} L${PAD},${H - PAD} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: '100%' }} className="cashflow-svg">
      <defs>
        <linearGradient id="cgGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#cgGrad)" />
      <polyline points={pts} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinejoin="round" />
      {data.filter((_, i) => i % Math.ceil(data.length / 6) === 0 || i === data.length - 1).map((d, i) => {
        const idx = data.indexOf(d);
        const x = PAD + (idx / (data.length - 1)) * (W - PAD * 2);
        return (
          <text key={i} x={x} y={H - 8} textAnchor="middle" fontSize="10" fill="var(--text-muted)">
            {fmtDate(d.date)}
          </text>
        );
      })}
      {[min, (min + max) / 2, max].map((v, i) => (
        <text key={i} x={PAD - 4} y={PAD + (1 - (v - min) / range) * (H - PAD * 2) + 4}
          textAnchor="end" fontSize="9" fill="var(--text-muted)">
          {fmtCurrency(v, 0)}
        </text>
      ))}
    </svg>
  );
}

function SuggestionCard({ s }) {
  const color = s.priority === 'HIGH' ? 'var(--red)' : s.priority === 'MEDIUM' ? 'var(--orange)' : 'var(--green)';
  return (
    <div className="card" style={{ borderLeft: `3px solid ${color}`, marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p style={{ fontWeight: 600, marginBottom: 4 }}>{s.title}</p>
          <p className="text-muted text-sm">{s.description}</p>
        </div>
        <Badge label={s.priority} type={s.priority === 'HIGH' ? 'danger' : s.priority === 'MEDIUM' ? 'warning' : 'success'} />
      </div>
      {s.amount > 0 && (
        <p style={{ marginTop: 8, color: 'var(--green)', fontSize: 13, fontWeight: 500 }}>
          Potential uplift: {fmtCurrency(s.amount)}
        </p>
      )}
    </div>
  );
}

export default function Overview() {
  const [balance, setBalance] = useState(() => Number(localStorage.getItem(BALANCE_KEY) || 300000));
  const [input,   setInput]   = useState(balance);
  const [dash,    setDash]    = useState(null);
  const [chart,   setChart]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const load = useCallback(async (bal) => {
    setLoading(true); setError(null);
    try {
      const [d, c] = await Promise.all([fetchDashboard(bal), fetchCashflow(bal, 90)]);
      setDash(d);
      setChart(c.cashflow || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(balance); }, [balance, load]);

  const handleRefresh = () => {
    const b = Number(input) || 0;
    localStorage.setItem(BALANCE_KEY, b);
    setBalance(b);
  };

  if (loading) return <div className="page-center"><Spinner /></div>;
  if (error)   return <EmptyState icon={AlertTriangle} title="API Error" subtitle={error} />;

  const metrics = dash?.metrics || {};
  const alerts  = dash?.alerts  || [];
  const suggsRaw = dash?.suggestions || {};
  const suggs = [
    ...(suggsRaw.invoices || []).map(i => ({
      title: `Chase ${i.customer_name}`,
      description: i.draft_message || `Action: ${i.action}`,
      priority: i.confidence === 'high' ? 'HIGH' : i.confidence === 'medium' ? 'MEDIUM' : 'LOW',
      amount: i.amount
    })),
    ...(suggsRaw.payables || []).map(p => ({
      title: `Delay ${p.vendor_name}`,
      description: `Action: ${p.action} - due in ${p.days_until_due} days`,
      priority: 'MEDIUM',
      amount: p.amount
    }))
  ];

  return (
    <div className="page">
      {/* Balance input */}
      <div className="card" style={{ display:'flex', alignItems:'center', gap:12, marginBottom:24 }}>
        <Zap size={18} color="var(--primary)" />
        <span style={{ fontWeight:500 }}>Opening Bank Balance</span>
        <input
          type="number" className="input" value={input}
          onChange={e => setInput(e.target.value)}
          style={{ width:160 }} placeholder="₹300000"
        />
        <button className="btn" onClick={handleRefresh}>
          <RefreshCw size={14} /> Refresh Forecast
        </button>
      </div>

      {/* KPI row */}
      <div className="grid-4" style={{ marginBottom:24 }}>
        <MetricCard
          icon={Clock} title="Cash Runway"
          value={metrics.cash_runway_days >= 90 ? '90+ days' : `${metrics.cash_runway_days} days`}
          sub="Before cash runs out" color="var(--green)" />
        <MetricCard
          icon={TrendingUp} title="Total Receivables"
          value={fmtCurrency(metrics.total_receivables_due)}
          sub={`${metrics.invoices_overdue} overdue`} color="var(--primary)" />
        <MetricCard
          icon={TrendingDown} title="Total Payables"
          value={fmtCurrency(metrics.total_payables_due)}
          sub="Upcoming obligations" color="var(--orange)" />
        <MetricCard
          icon={AlertTriangle} title="Peak Shortfall"
          value={metrics.peak_shortfall < 0 ? fmtCurrency(metrics.peak_shortfall) : '—'}
          sub="Worst projected day" color="var(--red)" />
      </div>

      {/* Chart */}
      <div className="card" style={{ marginBottom:24 }}>
        <SectionHeader title="90-Day Cash Forecast" sub="Projected daily balance" />
        <div style={{ height:180 }}>
          <CashflowChart data={chart} />
        </div>
      </div>

      {/* Alerts + Suggestions */}
      <div className="grid-2">
        <div>
          <SectionHeader title="Active Alerts" sub={`${alerts.length} items`} />
          {alerts.length === 0
            ? <EmptyState icon={TrendingUp} title="All clear" subtitle="No alerts at this time" />
            : alerts.map((a, i) => (
              <div key={i} className="card alert-card" style={{ marginBottom:10, borderLeft: `3px solid ${a.severity === 'HIGH' ? 'var(--red)' : a.severity === 'MEDIUM' ? 'var(--orange)' : 'var(--green)'}` }}>
                <div style={{ display:'flex', justifyContent:'space-between' }}>
                  <span style={{ fontWeight:600 }}>{a.title}</span>
                  <Badge label={a.severity} type={a.severity === 'HIGH' ? 'danger' : a.severity === 'MEDIUM' ? 'warning' : 'success'} />
                </div>
                <p className="text-muted text-sm" style={{ marginTop:4 }}>{a.message}</p>
              </div>
            ))
          }
        </div>
        <div>
          <SectionHeader title="AI Suggestions" sub={`${suggs.length} recommendations`} />
          {suggs.length === 0
            ? <EmptyState icon={Zap} title="No suggestions" subtitle="Financials look healthy" />
            : suggs.map((s, i) => <SuggestionCard key={i} s={s} />)
          }
        </div>
      </div>
    </div>
  );
}
