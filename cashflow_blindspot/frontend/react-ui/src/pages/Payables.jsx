import { useState, useEffect, useCallback } from 'react';
import { Plus, Search, CheckCircle, AlertTriangle, Download } from 'lucide-react';
import {
  fetchPayables, createPayable, markPayablePaid,
  fetchVendors, createVendor, exportPayablesUrl
} from '../api';
import { Badge, SectionHeader, Spinner, EmptyState, fmtCurrency, fmtDate, Modal } from '../components/shared';

const STATUS_COLORS = { paid: 'success', scheduled: 'info', overdue: 'danger', pending: 'warning' };

function AddPayableModal({ onClose, onSaved, vendors }) {
  const [form, setForm] = useState({ vendor_id:'', amount:'', due_date:'', description:'', reference_number:'' });
  const [newVendor, setNewVendor] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));

  const save = async () => {
    if (!form.amount || !form.due_date) { setErr('Amount and due date required'); return; }
    setSaving(true);
    try {
      let vid = form.vendor_id;
      if (!vid && newVendor) {
        const res = await createVendor({ name: newVendor });
        vid = res.vendor?.id || res.id;
      }
      await createPayable({ ...form, vendor_id: vid ? Number(vid) : null, amount: Number(form.amount) });
      onSaved();
    } catch(e) { setErr(e.message); setSaving(false); }
  };

  return (
    <Modal title="New Payable / Bill" onClose={onClose}>
      {err && <p style={{ color:'var(--red)', marginBottom:8, fontSize:13 }}>{err}</p>}
      <div className="form-grid">
        <div>
          <label className="form-label">Vendor (existing)</label>
          <select className="input" value={form.vendor_id} onChange={set('vendor_id')}>
            <option value="">— pick vendor —</option>
            {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </div>
        <div>
          <label className="form-label">Or add new vendor</label>
          <input className="input" placeholder="Vendor name" value={newVendor}
            onChange={e => { setNewVendor(e.target.value); setForm(f => ({ ...f, vendor_id:'' })); }} />
        </div>
        <div>
          <label className="form-label">Amount (₹) *</label>
          <input className="input" type="number" placeholder="25000" value={form.amount} onChange={set('amount')} />
        </div>
        <div>
          <label className="form-label">Due Date *</label>
          <input className="input" type="date" value={form.due_date} onChange={set('due_date')} />
        </div>
        <div>
          <label className="form-label">Ref / Bill #</label>
          <input className="input" placeholder="BILL-2024-001" value={form.reference_number} onChange={set('reference_number')} />
        </div>
        <div style={{ gridColumn:'1/-1' }}>
          <label className="form-label">Description</label>
          <input className="input" placeholder="Office rent, AWS bill…" value={form.description} onChange={set('description')} />
        </div>
      </div>
      <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:16 }}>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn" disabled={saving} onClick={save}>{saving ? 'Saving...' : 'Add Bill'}</button>
      </div>
    </Modal>
  );
}

export default function Payables() {
  const [payables, setPayables] = useState([]);
  const [vendors,  setVendors]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [search,   setSearch]   = useState('');
  const [status,   setStatus]   = useState('');
  const [showAdd,  setShowAdd]  = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, v] = await Promise.all([fetchPayables({ status, limit:200 }), fetchVendors()]);
      setPayables(p.payables || []);
      setVendors(v.vendors || []);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const handleMarkPaid = async (id) => {
    await markPayablePaid(id);
    load();
  };

  const filtered = payables.filter(p =>
    (p.vendor_name || p.description || '').toLowerCase().includes(search.toLowerCase()) ||
    (p.reference_number || '').toLowerCase().includes(search.toLowerCase())
  );

  const totalDue    = filtered.filter(p => p.status !== 'paid').reduce((s, p) => s + p.amount, 0);
  const overdueAmt  = filtered.filter(p => p.status === 'overdue').reduce((s, p) => s + p.amount, 0);
  const upcoming7   = filtered.filter(p => {
    const days = (new Date(p.due_date) - Date.now()) / 86400000;
    return p.status !== 'paid' && days >= 0 && days <= 7;
  }).reduce((s, p) => s + p.amount, 0);

  return (
    <div className="page">
      <SectionHeader title="Payables" sub="Track bills & supplier payments" />

      <div className="grid-3" style={{ marginBottom:24 }}>
        <div className="card stat-mini">
          <p className="stat-label">Total Outstanding</p>
          <p className="stat-value" style={{ color:'var(--orange)' }}>{fmtCurrency(totalDue)}</p>
        </div>
        <div className="card stat-mini">
          <p className="stat-label">Overdue</p>
          <p className="stat-value" style={{ color:'var(--red)' }}>{fmtCurrency(overdueAmt)}</p>
        </div>
        <div className="card stat-mini">
          <p className="stat-label">Due this week</p>
          <p className="stat-value" style={{ color:'var(--orange)' }}>{fmtCurrency(upcoming7)}</p>
        </div>
      </div>

      <div className="toolbar" style={{ marginBottom:16 }}>
        <div className="search-wrap">
          <Search size={14} className="search-icon" />
          <input className="input search-input" placeholder="Search bills…" value={search}
            onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="input" style={{ width:140 }} value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="scheduled">Scheduled</option>
          <option value="overdue">Overdue</option>
          <option value="paid">Paid</option>
        </select>
        <a className="btn btn-ghost" href={exportPayablesUrl()} download>
          <Download size={14} /> Export CSV
        </a>
        <button className="btn" onClick={() => setShowAdd(true)}>
          <Plus size={14} /> Add Bill
        </button>
      </div>

      {loading ? <Spinner /> : (
        <div className="card" style={{ padding:0, overflow:'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Vendor</th><th>Description</th><th>Ref #</th><th>Amount</th>
                <th>Due Date</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0
                ? <tr><td colSpan={7}><EmptyState icon={AlertTriangle} title="No bills" subtitle="Click + Add Bill to log a payable" /></td></tr>
                : filtered.map(p => {
                  const days = Math.floor((new Date(p.due_date) - Date.now()) / 86400000);
                  return (
                    <tr key={p.id} className="table-row">
                      <td style={{ fontWeight:500 }}>{p.vendor_name || '—'}</td>
                      <td className="text-muted">{p.description || '—'}</td>
                      <td className="text-muted">{p.reference_number || '—'}</td>
                      <td style={{ fontWeight:600 }}>{fmtCurrency(p.amount)}</td>
                      <td>
                        {fmtDate(p.due_date)}
                        {p.status !== 'paid' && days < 0 && <span style={{ color:'var(--red)', marginLeft:6, fontSize:12 }}>{Math.abs(days)}d ago</span>}
                        {p.status !== 'paid' && days >= 0 && days <= 7 && <span style={{ color:'var(--orange)', marginLeft:6, fontSize:12 }}>in {days}d</span>}
                      </td>
                      <td><Badge label={p.status} type={STATUS_COLORS[p.status] || 'info'} /></td>
                      <td>
                        {p.status !== 'paid' && (
                          <button className="btn btn-sm btn-success" onClick={() => handleMarkPaid(p.id)}>
                            <CheckCircle size={12} /> Mark Paid
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              }
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddPayableModal vendors={vendors} onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load(); }} />}
    </div>
  );
}
