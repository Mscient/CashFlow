import { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw, CheckCircle, Bell, Mail, Clock, Database } from 'lucide-react';
import { fetchSettings, saveSettings } from '../api';
import { SectionHeader, Spinner } from '../components/shared';

const DEFAULTS = {
  company_name:          'My Company',
  base_currency:         'INR',
  overdue_alert_days:    0,
  high_risk_threshold:   50,
  email_chase_enabled:   true,
  whatsapp_chase_enabled:false,
  reminder_days_before:  3,
  smtp_host:             '',
  smtp_port:             587,
  smtp_user:             '',
  smtp_pass:             '',
  from_email:            '',
  openai_key:            '',
};

function Toggle({ value, onChange }) {
  return (
    <div
      onClick={() => onChange(!value)}
      style={{
        width:44, height:24, borderRadius:12, cursor:'pointer',
        background: value ? 'var(--primary)' : 'var(--border)',
        position:'relative', transition:'background 0.2s',
        flexShrink:0,
      }}
    >
      <div style={{
        position:'absolute', top:3, left: value ? 23 : 3,
        width:18, height:18, borderRadius:'50%', background:'#fff',
        transition:'left 0.2s',
      }} />
    </div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <div className="card" style={{ marginBottom:20 }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:18, paddingBottom:12, borderBottom:'1px solid var(--border)' }}>
        <Icon size={16} color="var(--primary)" />
        <span style={{ fontWeight:600, fontSize:15 }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const [form,    setForm]    = useState(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [saved,   setSaved]   = useState(false);
  const [err,     setErr]     = useState('');

  useEffect(() => {
    fetchSettings()
      .then(d => setForm({ ...DEFAULTS, ...(d.settings || d) }))
      .catch(() => setForm(DEFAULTS))
      .finally(() => setLoading(false));
  }, []);

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const setNum = k => e => setForm(f => ({ ...f, [k]: Number(e.target.value) }));
  const setBool = k => v => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    setSaving(true); setErr(''); setSaved(false);
    try {
      await saveSettings(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch(e) { setErr(e.message); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="page-center"><Spinner /></div>;

  return (
    <div className="page">
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:24 }}>
        <SectionHeader title="Settings" sub="Configure your CashFlow Blindspot AI" />
        <button className="btn" disabled={saving} onClick={handleSave}>
          {saved ? <><CheckCircle size={14} /> Saved!</> : saving ? <><RefreshCw size={14} className="spin" /> Saving…</> : <><Save size={14} /> Save Settings</>}
        </button>
      </div>
      {err && <p style={{ color:'var(--red)', marginBottom:12, fontSize:13 }}>{err}</p>}

      {/* General */}
      <Section title="General" icon={Settings}>
        <div className="form-grid">
          <div>
            <label className="form-label">Company Name</label>
            <input className="input" value={form.company_name} onChange={set('company_name')} />
          </div>
          <div>
            <label className="form-label">Currency</label>
            <select className="input" value={form.base_currency} onChange={set('base_currency')}>
              <option value="INR">INR — Indian Rupee</option>
              <option value="USD">USD — US Dollar</option>
              <option value="EUR">EUR — Euro</option>
              <option value="GBP">GBP — British Pound</option>
            </select>
          </div>
        </div>
      </Section>

      {/* Alerts */}
      <Section title="Alert Thresholds" icon={Bell}>
        <div className="form-grid">
          <div>
            <label className="form-label">Overdue Alert After (days)</label>
            <input className="input" type="number" min={0} value={form.overdue_alert_days} onChange={setNum('overdue_alert_days')} />
            <p className="text-muted text-sm" style={{ marginTop:4 }}>0 = alert on due date</p>
          </div>
          <div>
            <label className="form-label">High Risk Score Threshold</label>
            <input className="input" type="number" min={0} max={100} value={form.high_risk_threshold} onChange={setNum('high_risk_threshold')} />
            <p className="text-muted text-sm" style={{ marginTop:4 }}>Customers below this score are flagged</p>
          </div>
          <div>
            <label className="form-label">Reminder Days Before Due</label>
            <input className="input" type="number" min={0} value={form.reminder_days_before} onChange={setNum('reminder_days_before')} />
          </div>
        </div>
      </Section>

      {/* Email / WhatsApp */}
      <Section title="Communication Channels" icon={Mail}>
        <div style={{ display:'flex', gap:16, marginBottom:16, flexWrap:'wrap' }}>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <Toggle value={form.email_chase_enabled} onChange={setBool('email_chase_enabled')} />
            <span>Email Reminders Enabled</span>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <Toggle value={form.whatsapp_chase_enabled} onChange={setBool('whatsapp_chase_enabled')} />
            <span>WhatsApp Reminders Enabled</span>
          </div>
        </div>

        <div className="form-grid">
          <div>
            <label className="form-label">SMTP Host</label>
            <input className="input" placeholder="smtp.gmail.com" value={form.smtp_host} onChange={set('smtp_host')} />
          </div>
          <div>
            <label className="form-label">SMTP Port</label>
            <input className="input" type="number" value={form.smtp_port} onChange={setNum('smtp_port')} />
          </div>
          <div>
            <label className="form-label">SMTP Username</label>
            <input className="input" placeholder="user@company.com" value={form.smtp_user} onChange={set('smtp_user')} />
          </div>
          <div>
            <label className="form-label">SMTP Password</label>
            <input className="input" type="password" placeholder="••••••••" value={form.smtp_pass} onChange={set('smtp_pass')} />
          </div>
          <div style={{ gridColumn:'1/-1' }}>
            <label className="form-label">From Email</label>
            <input className="input" placeholder="billing@yourcompany.com" value={form.from_email} onChange={set('from_email')} />
          </div>
        </div>
      </Section>

      {/* AI */}
      <Section title="AI Configuration" icon={Database}>
        <div>
          <label className="form-label">OpenAI API Key (for AI suggestions)</label>
          <input className="input" type="password" placeholder="sk-…" value={form.openai_key} onChange={set('openai_key')} />
          <p className="text-muted text-sm" style={{ marginTop:4 }}>Optional — AI suggestions work without this key using rule-based analysis.</p>
        </div>
      </Section>

      <div style={{ display:'flex', justifyContent:'flex-end' }}>
        <button className="btn" disabled={saving} onClick={handleSave} style={{ minWidth:160 }}>
          {saved ? <><CheckCircle size={14} /> Saved!</> : saving ? 'Saving…' : <><Save size={14} /> Save All Settings</>}
        </button>
      </div>
    </div>
  );
}
