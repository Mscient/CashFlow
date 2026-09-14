import { useState, useEffect, useCallback } from 'react';
import { Plus, Search, CheckCircle, Clock, AlertTriangle, Upload, Download, Mail, ChevronDown, ChevronUp, X } from 'lucide-react';
import {
  fetchInvoices, createInvoice, markInvoicePaid,
  fetchCustomers, logChase, fetchChaseLog, exportInvoicesUrl
} from '../api';
import { Badge, SectionHeader, Spinner, EmptyState, fmtCurrency, fmtDate, Modal } from '../components/shared';

const STATUS_COLORS = { paid: 'success', pending: 'info', overdue: 'danger' };

function InvoiceRow({ inv, onMarkPaid, onChase, expanded, onToggle }) {
  const daysOverdue = inv.status === 'overdue'
    ? Math.floor((Date.now() - new Date(inv.due_date)) / 86400000)
    : 0;
  return (
    <>
      <tr className="table-row" onClick={onToggle} style={{ cursor:'pointer' }}>
        <td>{inv.invoice_number || `INV-${inv.id}`}</td>
        <td>{inv.customer_name}</td>
        <td style={{ fontWeight:600 }}>{fmtCurrency(inv.amount)}</td>
        <td>{fmtDate(inv.due_date)}</td>
        <td><Badge label={inv.status} type={STATUS_COLORS[inv.status] || 'info'} /></td>
        <td>{daysOverdue > 0 ? <span style={{ color:'var(--red)', fontWeight:600 }}>{daysOverdue}d overdue</span> : '—'}</td>
        <td>
          <div style={{ display:'flex', gap:6 }}>
            {inv.status !== 'paid' && (
              <button className="btn btn-sm btn-success" onClick={e => { e.stopPropagation(); onMarkPaid(inv.id); }}>
                <CheckCircle size={12} /> Paid
              </button>
            )}
            {inv.status === 'overdue' && (
              <button className="btn btn-sm" onClick={e => { e.stopPropagation(); onChase(inv); }}>
                <Mail size={12} /> Chase
              </button>
            )}
          </div>
        </td>
        <td>{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={8} style={{ padding:'0 0 8px' }}>
            <ChaseLogPanel invoiceId={inv.id} />
          </td>
        </tr>
      )}
    </>
  );
}

function ChaseLogPanel({ invoiceId }) {
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetchChaseLog(invoiceId)
      .then(d => setLog(d.chase_log || []))
      .catch(() => setLog([]))
      .finally(() => setLoading(false));
  }, [invoiceId]);
  if (loading) return <Spinner />;
  if (log.length === 0) return <p className="text-muted text-sm" style={{ padding:'8px 16px' }}>No chase history yet.</p>;
  return (
    <div style={{ background:'var(--bg-card)', borderRadius:8, padding:'10px 16px', margin:'0 8px' }}>
      {log.map((l, i) => (
        <div key={i} style={{ borderBottom: i < log.length - 1 ? '1px solid var(--border)' : 'none', padding:'6px 0' }}>
          <span className="text-sm" style={{ fontWeight:600 }}>{l.method}</span>
          <span className="text-muted text-sm" style={{ marginLeft:8 }}>{fmtDate(l.sent_at)}</span>
          {l.notes && <p className="text-sm text-muted" style={{ marginTop:2 }}>{l.notes}</p>}
        </div>
      ))}
    </div>
  );
}

function AddInvoiceModal({ onClose, onSaved, customers }) {
  const [form, setForm] = useState({ customer_id:'', amount:'', due_date:'', invoice_number:'', description:'' });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async () => {
    if (!form.customer_id || !form.amount || !form.due_date) { setErr('Fill required fields'); return; }
    setSaving(true);
    try {
      await createInvoice({ ...form, amount: Number(form.amount) });
      onSaved();
    } catch(e) { setErr(e.message); setSaving(false); }
  };
  return (
    <Modal title="New Invoice" onClose={onClose}>
      {err && <p style={{ color:'var(--red)', marginBottom:8, fontSize:13 }}>{err}</p>}
      <div className="form-grid">
        <div>
          <label className="form-label">Customer *</label>
          <select className="input" value={form.customer_id} onChange={set('customer_id')}>
            <option value="">— select —</option>
            {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="form-label">Invoice # </label>
          <input className="input" placeholder="INV-001" value={form.invoice_number} onChange={set('invoice_number')} />
        </div>
        <div>
          <label className="form-label">Amount (₹) *</label>
          <input className="input" type="number" placeholder="50000" value={form.amount} onChange={set('amount')} />
        </div>
        <div>
          <label className="form-label">Due Date *</label>
          <input className="input" type="date" value={form.due_date} onChange={set('due_date')} />
        </div>
        <div style={{ gridColumn:'1/-1' }}>
          <label className="form-label">Description</label>
          <input className="input" placeholder="Services for Q3..." value={form.description} onChange={set('description')} />
        </div>
      </div>
      <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:16 }}>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn" disabled={saving} onClick={save}>{saving ? 'Saving...' : 'Create Invoice'}</button>
      </div>
    </Modal>
  );
}

function ChaseModal({ invoice, onClose, onSent }) {
  const [form, setForm] = useState({ method:'Email', notes:'' });
  const [saving, setSaving] = useState(false);
  const send = async () => {
    setSaving(true);
    try { await logChase(invoice.id, form); onSent(); }
    catch(e) { setSaving(false); }
  };
  return (
    <Modal title={`Chase: ${invoice.customer_name}`} onClose={onClose}>
      <p className="text-muted text-sm" style={{ marginBottom:12 }}>
        Invoice <strong>{fmtCurrency(invoice.amount)}</strong> was due {fmtDate(invoice.due_date)}.
      </p>
      <div className="form-grid">
        <div>
          <label className="form-label">Contact Method</label>
          <select className="input" value={form.method} onChange={e => setForm(f => ({ ...f, method: e.target.value }))}>
            <option>Email</option><option>WhatsApp</option><option>Phone</option><option>Letter</option>
          </select>
        </div>
        <div style={{ gridColumn:'1/-1' }}>
          <label className="form-label">Notes</label>
          <textarea className="input" rows={3} style={{ resize:'vertical' }}
            placeholder="Customer promised payment by..."
            value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
        </div>
      </div>
      <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:16 }}>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn" disabled={saving} onClick={send}>{saving ? 'Sending...' : 'Log Chase'}</button>
      </div>
    </Modal>
  );
}

export default function Receivables() {
  const [invoices,  setInvoices]  = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [search,    setSearch]    = useState('');
  const [status,    setStatus]    = useState('');
  const [showAdd,   setShowAdd]   = useState(false);
  const [chasing,   setChasing]   = useState(null);
  const [expanded,  setExpanded]  = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [inv, cust] = await Promise.all([fetchInvoices({ status, limit:200 }), fetchCustomers()]);
      setInvoices(inv.invoices || []);
      setCustomers(cust.customers || []);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const handleMarkPaid = async (id) => {
    const today = new Date().toISOString().slice(0, 10);
    await markInvoicePaid(id, today);
    load();
  };

  const filtered = invoices.filter(inv =>
    (inv.customer_name || '').toLowerCase().includes(search.toLowerCase()) ||
    (inv.invoice_number || '').toLowerCase().includes(search.toLowerCase())
  );

  const total    = filtered.reduce((s, i) => s + (i.status !== 'paid' ? i.amount : 0), 0);
  const overdue  = filtered.filter(i => i.status === 'overdue');
  const overdueAmt = overdue.reduce((s, i) => s + i.amount, 0);

  return (
    <div className="page">
      <SectionHeader title="Receivables" sub="Manage your invoices & collections" />

      {/* Stats */}
      <div className="grid-3" style={{ marginBottom:24 }}>
        <div className="card stat-mini">
          <p className="stat-label">Outstanding</p>
          <p className="stat-value" style={{ color:'var(--primary)' }}>{fmtCurrency(total)}</p>
        </div>
        <div className="card stat-mini">
          <p className="stat-label">Overdue</p>
          <p className="stat-value" style={{ color:'var(--red)' }}>{fmtCurrency(overdueAmt)}</p>
        </div>
        <div className="card stat-mini">
          <p className="stat-label">Invoices</p>
          <p className="stat-value">{filtered.length}</p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="toolbar" style={{ marginBottom:16 }}>
        <div className="search-wrap">
          <Search size={14} className="search-icon" />
          <input className="input search-input" placeholder="Search invoices…" value={search}
            onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="input" style={{ width:140 }} value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="overdue">Overdue</option>
          <option value="paid">Paid</option>
        </select>
        <a className="btn btn-ghost" href={exportInvoicesUrl()} download>
          <Download size={14} /> Export CSV
        </a>
        <button className="btn" onClick={() => setShowAdd(true)}>
          <Plus size={14} /> New Invoice
        </button>
      </div>

      {/* Table */}
      {loading ? <Spinner /> : (
        <div className="card" style={{ padding:0, overflow:'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Invoice #</th><th>Customer</th><th>Amount</th><th>Due Date</th>
                <th>Status</th><th>Aging</th><th>Actions</th><th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0
                ? <tr><td colSpan={8}><EmptyState icon={Clock} title="No invoices" subtitle="Click + New Invoice to get started" /></td></tr>
                : filtered.map(inv => (
                  <InvoiceRow key={inv.id} inv={inv}
                    onMarkPaid={handleMarkPaid}
                    onChase={setChasing}
                    expanded={expanded === inv.id}
                    onToggle={() => setExpanded(expanded === inv.id ? null : inv.id)}
                  />
                ))
              }
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddInvoiceModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load(); }} customers={customers} />}
      {chasing  && <ChaseModal invoice={chasing} onClose={() => setChasing(null)} onSent={() => { setChasing(null); load(); }} />}
    </div>
  );
}
