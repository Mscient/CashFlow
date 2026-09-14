import { useState, useEffect, useCallback } from 'react';
import { Plus, Search, Users, TrendingUp, Clock, ChevronRight } from 'lucide-react';
import { fetchCustomers, createCustomer, fetchCustomerProfile } from '../api';
import { SectionHeader, Badge, Spinner, EmptyState, fmtCurrency, fmtDate, Modal } from '../components/shared';

function RiskBadge({ score }) {
  if (score >= 80) return <Badge label="Low Risk"   type="success" />;
  if (score >= 50) return <Badge label="Medium Risk" type="warning" />;
  return <Badge label="High Risk" type="danger" />;
}

function CustomerProfile({ customerId, onClose }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCustomerProfile(customerId)
      .then(d => setProfile(d))
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [customerId]);

  return (
    <Modal title="Customer Profile" onClose={onClose} wide>
      {loading ? <Spinner /> : !profile ? <p className="text-muted">Failed to load profile.</p> : (
        <div>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
            <div>
              <h2 style={{ fontSize:22, fontWeight:700 }}>{profile.customer?.name}</h2>
              <p className="text-muted text-sm">{profile.customer?.email}</p>
            </div>
            <RiskBadge score={profile.risk_score ?? 75} />
          </div>
          <div className="grid-3" style={{ marginBottom:20 }}>
            <div className="card stat-mini">
              <p className="stat-label">Total Invoiced</p>
              <p className="stat-value" style={{ color:'var(--primary)' }}>{fmtCurrency(profile.total_invoiced)}</p>
            </div>
            <div className="card stat-mini">
              <p className="stat-label">Total Paid</p>
              <p className="stat-value" style={{ color:'var(--green)' }}>{fmtCurrency(profile.total_paid)}</p>
            </div>
            <div className="card stat-mini">
              <p className="stat-label">Outstanding</p>
              <p className="stat-value" style={{ color:'var(--orange)' }}>{fmtCurrency(profile.total_outstanding)}</p>
            </div>
          </div>
          <div className="card stat-mini" style={{ marginBottom:20 }}>
            <p className="stat-label">Avg Payment Delay</p>
            <p className="stat-value">{profile.avg_payment_delay_days ?? 0} days</p>
          </div>
          <h4 style={{ marginBottom:12, fontWeight:600 }}>Invoice History</h4>
          <table className="table">
            <thead><tr><th>Invoice #</th><th>Amount</th><th>Due</th><th>Paid</th><th>Status</th></tr></thead>
            <tbody>
              {(profile.invoices || []).map(inv => (
                <tr key={inv.id} className="table-row">
                  <td>{inv.invoice_number || `INV-${inv.id}`}</td>
                  <td style={{ fontWeight:600 }}>{fmtCurrency(inv.amount)}</td>
                  <td>{fmtDate(inv.due_date)}</td>
                  <td>{inv.paid_date ? fmtDate(inv.paid_date) : '—'}</td>
                  <td><Badge label={inv.status} type={inv.status === 'paid' ? 'success' : inv.status === 'overdue' ? 'danger' : 'info'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}

function AddCustomerModal({ onClose, onSaved }) {
  const [form, setForm] = useState({ name:'', email:'', phone:'', address:'', payment_terms_days:30 });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const save = async () => {
    if (!form.name) { setErr('Name is required'); return; }
    setSaving(true);
    try { await createCustomer({ ...form, payment_terms_days: Number(form.payment_terms_days) }); onSaved(); }
    catch(e) { setErr(e.message); setSaving(false); }
  };
  return (
    <Modal title="New Customer" onClose={onClose}>
      {err && <p style={{ color:'var(--red)', marginBottom:8, fontSize:13 }}>{err}</p>}
      <div className="form-grid">
        <div style={{ gridColumn:'1/-1' }}>
          <label className="form-label">Company / Name *</label>
          <input className="input" placeholder="Acme Corp" value={form.name} onChange={set('name')} />
        </div>
        <div>
          <label className="form-label">Email</label>
          <input className="input" type="email" placeholder="billing@acme.com" value={form.email} onChange={set('email')} />
        </div>
        <div>
          <label className="form-label">Phone</label>
          <input className="input" placeholder="+91 98765 43210" value={form.phone} onChange={set('phone')} />
        </div>
        <div>
          <label className="form-label">Payment Terms (days)</label>
          <input className="input" type="number" value={form.payment_terms_days} onChange={set('payment_terms_days')} />
        </div>
        <div style={{ gridColumn:'1/-1' }}>
          <label className="form-label">Address</label>
          <input className="input" placeholder="123 Business Park, Mumbai" value={form.address} onChange={set('address')} />
        </div>
      </div>
      <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:16 }}>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn" disabled={saving} onClick={save}>{saving ? 'Saving...' : 'Add Customer'}</button>
      </div>
    </Modal>
  );
}

export default function Customers() {
  const [customers, setCustomers] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [search,    setSearch]    = useState('');
  const [showAdd,   setShowAdd]   = useState(false);
  const [profileId, setProfileId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await fetchCustomers();
      setCustomers(d.customers || []);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = customers.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    (c.email || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page">
      <SectionHeader title="Customers" sub="Manage your client relationships" />

      <div className="grid-3" style={{ marginBottom:24 }}>
        <div className="card stat-mini">
          <p className="stat-label">Total Customers</p>
          <p className="stat-value">{customers.length}</p>
        </div>
        <div className="card stat-mini">
          <p className="stat-label">Active</p>
          <p className="stat-value" style={{ color:'var(--green)' }}>
            {customers.filter(c => c.status === 'active').length}
          </p>
        </div>
        <div className="card stat-mini">
          <p className="stat-label">High Risk</p>
          <p className="stat-value" style={{ color:'var(--red)' }}>
            {customers.filter(c => (c.risk_score || 75) < 50).length}
          </p>
        </div>
      </div>

      <div className="toolbar" style={{ marginBottom:16 }}>
        <div className="search-wrap">
          <Search size={14} className="search-icon" />
          <input className="input search-input" placeholder="Search customers…" value={search}
            onChange={e => setSearch(e.target.value)} />
        </div>
        <button className="btn" onClick={() => setShowAdd(true)}>
          <Plus size={14} /> Add Customer
        </button>
      </div>

      {loading ? <Spinner /> : (
        <div className="card" style={{ padding:0, overflow:'hidden' }}>
          <table className="table">
            <thead>
              <tr><th>Name</th><th>Email</th><th>Phone</th><th>Payment Terms</th><th>Risk</th><th>Total Billed</th><th></th></tr>
            </thead>
            <tbody>
              {filtered.length === 0
                ? <tr><td colSpan={7}><EmptyState icon={Users} title="No customers" subtitle="Click + Add Customer to get started" /></td></tr>
                : filtered.map(c => (
                  <tr key={c.id} className="table-row" onClick={() => setProfileId(c.id)} style={{ cursor:'pointer' }}>
                    <td style={{ fontWeight:600 }}>{c.name}</td>
                    <td className="text-muted">{c.email || '—'}</td>
                    <td className="text-muted">{c.phone || '—'}</td>
                    <td>{c.payment_terms_days || 30} days</td>
                    <td><RiskBadge score={c.risk_score ?? 75} /></td>
                    <td style={{ fontWeight:600 }}>{fmtCurrency(c.total_invoiced || 0)}</td>
                    <td><ChevronRight size={14} color="var(--text-muted)" /></td>
                  </tr>
                ))
              }
            </tbody>
          </table>
        </div>
      )}

      {showAdd   && <AddCustomerModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load(); }} />}
      {profileId && <CustomerProfile customerId={profileId} onClose={() => setProfileId(null)} />}
    </div>
  );
}
