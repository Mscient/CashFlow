import React from 'react';
import { X } from 'lucide-react';

// ── Formatters ─────────────────────────────────────────────────────────────
export const fmtCurrency = (v, dec = 0) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: dec,
  }).format(v ?? 0);

export const fmtDate = (d) => {
  if (!d) return '—';
  const dt = new Date(d);
  return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
};

export const INR = fmtCurrency;
export const pct = (v) => `${((v ?? 0) * 100).toFixed(1)}%`;

// ── Badge ──────────────────────────────────────────────────────────────────
const BADGE_STYLES = {
  success: { bg: 'var(--green-dim)',   color: 'var(--green)'   },
  danger:  { bg: 'var(--red-dim)',     color: 'var(--red)'     },
  warning: { bg: 'var(--orange-dim)',  color: 'var(--orange)'  },
  info:    { bg: 'var(--primary-dim)', color: 'var(--primary)' },
};

export function Badge({ label, type = 'info' }) {
  const s = BADGE_STYLES[type] || BADGE_STYLES.info;
  return (
    <span style={{
      background: s.bg, color: s.color,
      padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
      whiteSpace: 'nowrap', textTransform: 'uppercase', letterSpacing: '0.04em',
    }}>
      {label}
    </span>
  );
}

// ── StatusBadge (legacy) ───────────────────────────────────────────────────
const LEGACY_MAP = {
  unpaid: 'warning', overdue: 'danger', paid: 'success',
  pending: 'info', delayed: 'danger', fixed: 'success', discretionary: 'warning',
};
export function StatusBadge({ status }) {
  return <Badge label={status} type={LEGACY_MAP[status] || 'info'} />;
}

// ── MetricCard ─────────────────────────────────────────────────────────────
export function MetricCard({ icon: Icon, title, label, value, sub, color }) {
  const displayTitle = title || label;
  return (
    <div className="card" style={{ display:'flex', alignItems:'flex-start', gap:14 }}>
      <div style={{
        width:40, height:40, borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center',
        background: color ? `${color}20` : 'var(--primary-dim)', flexShrink:0,
      }}>
        {Icon && <Icon size={18} color={color || 'var(--primary)'} />}
      </div>
      <div>
        <p className="text-muted text-sm" style={{ marginBottom:4 }}>{displayTitle}</p>
        <p style={{ fontWeight:700, fontSize:20 }}>{value}</p>
        {sub && <p className="text-muted text-sm" style={{ marginTop:2 }}>{sub}</p>}
      </div>
    </div>
  );
}

// ── SectionHeader ──────────────────────────────────────────────────────────
export function SectionHeader({ title, sub, children }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:16 }}>
      <div>
        <h2 style={{ fontWeight:700, fontSize:22 }}>{title}</h2>
        {sub && <p className="text-muted text-sm" style={{ marginTop:2 }}>{sub}</p>}
      </div>
      {children}
    </div>
  );
}

// PageHeader alias
export function PageHeader({ title, sub, children }) {
  return <SectionHeader title={title} sub={sub}>{children}</SectionHeader>;
}

// ── Spinner ────────────────────────────────────────────────────────────────
export function Spinner() {
  return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', padding:40 }}>
      <div className="spinner" />
    </div>
  );
}

// ── EmptyState ─────────────────────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, subtitle }) {
  return (
    <div style={{ textAlign:'center', padding:'48px 24px' }}>
      {Icon && <Icon size={40} color="var(--text-muted)" style={{ marginBottom:12 }} />}
      <p style={{ fontWeight:600, marginBottom:6 }}>{title}</p>
      {subtitle && <p className="text-muted text-sm">{subtitle}</p>}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, wide }) {
  // Support both controlled (open prop) and always-visible usage
  if (open === false) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: wide ? 780 : 520 }}
      >
        <div className="modal__header">
          <h3 className="modal__title">{title}</h3>
          <button
            onClick={onClose}
            style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-muted)', padding:4 }}
          >
            <X size={18} />
          </button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>
  );
}

// ── Legacy table helpers ───────────────────────────────────────────────────
export function LoadingRow({ cols = 4 }) {
  return (
    <tr>
      <td colSpan={cols} style={{ textAlign:'center', padding:'2rem', color:'var(--text-muted)' }}>
        Loading…
      </td>
    </tr>
  );
}

export function EmptyRow({ cols = 4, message = 'No records found.' }) {
  return (
    <tr>
      <td colSpan={cols} style={{ textAlign:'center', padding:'2rem', color:'var(--text-muted)' }}>
        {message}
      </td>
    </tr>
  );
}

// ── useAsync hook ──────────────────────────────────────────────────────────
export function useAsync(fn, deps = []) {
  const [data,    setData]    = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error,   setError]   = React.useState(null);

  const run = React.useCallback(async (...args) => {
    setLoading(true); setError(null);
    try   { const d = await fn(...args); setData(d); return d; }
    catch (e) { setError(e.message); }
    finally   { setLoading(false); }
  }, deps); // eslint-disable-line

  return { data, loading, error, run };
}
