import { useState, useEffect, useCallback } from 'react';
import { Bell, Mail, MessageSquare, Phone, AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react';
import { fetchMessageCenter } from '../api';
import { SectionHeader, Badge, Spinner, EmptyState, fmtCurrency, fmtDate } from '../components/shared';

const BALANCE_KEY = 'cf_balance';

const METHOD_ICON = {
  Email:     Mail,
  WhatsApp:  MessageSquare,
  Phone:     Phone,
  Letter:    Bell,
};

function AlertCard({ alert }) {
  const color = alert.severity === 'HIGH'   ? 'var(--red)'
              : alert.severity === 'MEDIUM' ? 'var(--orange)'
              : 'var(--green)';
  const Icon  = alert.severity === 'HIGH'   ? AlertTriangle
              : alert.severity === 'MEDIUM' ? Clock
              : CheckCircle;
  return (
    <div className="card" style={{ borderLeft:`3px solid ${color}`, marginBottom:10 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div style={{ display:'flex', gap:10, alignItems:'center' }}>
          <Icon size={16} color={color} />
          <div>
            <p style={{ fontWeight:600 }}>{alert.title}</p>
            <p className="text-muted text-sm" style={{ marginTop:3 }}>{alert.message}</p>
          </div>
        </div>
        <Badge label={alert.severity} type={alert.severity === 'HIGH' ? 'danger' : alert.severity === 'MEDIUM' ? 'warning' : 'success'} />
      </div>
      {alert.action_items && alert.action_items.length > 0 && (
        <ul style={{ marginTop:10, paddingLeft:20 }}>
          {alert.action_items.map((a, i) => (
            <li key={i} className="text-sm text-muted" style={{ marginBottom:3 }}>{a}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ChaseItem({ item }) {
  const Icon = METHOD_ICON[item.method] || Bell;
  const daysOverdue = Math.floor((Date.now() - new Date(item.due_date)) / 86400000);
  return (
    <div className="card" style={{ marginBottom:10 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div>
          <p style={{ fontWeight:600 }}>{item.customer_name}</p>
          <p className="text-muted text-sm">
            Invoice {fmtCurrency(item.amount)} · Due {fmtDate(item.due_date)}
            {daysOverdue > 0 && <span style={{ color:'var(--red)', marginLeft:6 }}>{daysOverdue}d overdue</span>}
          </p>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <Icon size={14} color="var(--text-muted)" />
          <Badge label={item.last_chase_method || 'Not chased'} type={item.last_chase_method ? 'info' : 'warning'} />
        </div>
      </div>
      <div style={{ marginTop:10, display:'flex', gap:8 }}>
        <button className="btn btn-sm">
          <Mail size={12} /> Send Email Reminder
        </button>
        <button className="btn btn-sm btn-ghost">
          <MessageSquare size={12} /> WhatsApp
        </button>
        <button className="btn btn-sm btn-ghost">
          <Phone size={12} /> Call Log
        </button>
      </div>
    </div>
  );
}

function SuggestionItem({ s }) {
  const color = s.priority === 'HIGH' ? 'var(--red)' : s.priority === 'MEDIUM' ? 'var(--orange)' : 'var(--green)';
  return (
    <div className="card" style={{ borderLeft:`3px solid ${color}`, marginBottom:10 }}>
      <div style={{ display:'flex', justifyContent:'space-between' }}>
        <p style={{ fontWeight:600 }}>{s.title}</p>
        <Badge label={s.priority} type={s.priority === 'HIGH' ? 'danger' : s.priority === 'MEDIUM' ? 'warning' : 'success'} />
      </div>
      <p className="text-muted text-sm" style={{ marginTop:4 }}>{s.description}</p>
      {s.amount > 0 && (
        <p style={{ marginTop:6, color:'var(--green)', fontSize:13, fontWeight:500 }}>
          <Zap size={12} style={{ marginRight:4 }} />
          Potential impact: {fmtCurrency(s.amount)}
        </p>
      )}
    </div>
  );
}

export default function Alerts() {
  const balance = Number(localStorage.getItem(BALANCE_KEY) || 300000);
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab,     setTab]     = useState('alerts');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await fetchMessageCenter(balance);
      setData(d);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [balance]);

  useEffect(() => { load(); }, [load]);

  const alerts      = data?.alerts       || [];
  const chaseItems  = data?.chase_queue  || [];
  const suggestions = data?.suggestions  || [];
  const summary     = data?.summary      || {};

  const TABS = [
    { id:'alerts',      label:`Alerts (${alerts.length})` },
    { id:'chase',       label:`Chase Queue (${chaseItems.length})` },
    { id:'suggestions', label:`AI Tips (${suggestions.length})` },
  ];

  return (
    <div className="page">
      <SectionHeader title="Messages & Alerts" sub="Your cash flow action center" />

      {/* Summary strip */}
      {!loading && (
        <div className="card" style={{ display:'flex', gap:24, flexWrap:'wrap', marginBottom:24 }}>
          <div>
            <p className="stat-label">Total Overdue</p>
            <p style={{ fontWeight:700, color:'var(--red)', fontSize:18 }}>{fmtCurrency(summary.total_overdue_amount || 0)}</p>
          </div>
          <div>
            <p className="stat-label">Overdue Invoices</p>
            <p style={{ fontWeight:700, fontSize:18 }}>{summary.overdue_invoices || 0}</p>
          </div>
          <div>
            <p className="stat-label">Upcoming Due (7d)</p>
            <p style={{ fontWeight:700, color:'var(--orange)', fontSize:18 }}>{fmtCurrency(summary.upcoming_payables_7d || 0)}</p>
          </div>
          <div>
            <p className="stat-label">Cash Runway</p>
            <p style={{ fontWeight:700, color:'var(--green)', fontSize:18 }}>
              {summary.cash_runway_days >= 90 ? '90+ days' : `${summary.cash_runway_days || 0} days`}
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom:16 }}>
        {TABS.map(t => (
          <button key={t.id} className={`tab-btn${tab === t.id ? ' tab-btn--active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? <Spinner /> : (
        <>
          {tab === 'alerts' && (
            alerts.length === 0
              ? <EmptyState icon={CheckCircle} title="All clear!" subtitle="No alerts at the moment" />
              : alerts.map((a, i) => <AlertCard key={i} alert={a} />)
          )}
          {tab === 'chase' && (
            chaseItems.length === 0
              ? <EmptyState icon={CheckCircle} title="Nothing to chase" subtitle="All invoices are on track" />
              : chaseItems.map((c, i) => <ChaseItem key={i} item={c} />)
          )}
          {tab === 'suggestions' && (
            suggestions.length === 0
              ? <EmptyState icon={Zap} title="No suggestions" subtitle="Financials look healthy" />
              : suggestions.map((s, i) => <SuggestionItem key={i} s={s} />)
          )}
        </>
      )}
    </div>
  );
}
