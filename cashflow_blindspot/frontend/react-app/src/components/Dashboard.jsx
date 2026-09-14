import React, { useEffect, useState } from 'react';
import { fetchForecast, fetchAlerts, fetchSuggestions, markInvoicePaid } from '../api';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area, ComposedChart } from 'recharts';
import { AlertCircle, TrendingDown, Bell, CheckCircle2, Send, Clock, Wallet } from 'lucide-react';

export default function Dashboard() {
  const [balance, setBalance] = useState(300000);
  const [forecast, setForecast] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [suggestions, setSuggestions] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [fData, aData, sData] = await Promise.all([
        fetchForecast(balance),
        fetchAlerts(balance),
        fetchSuggestions(balance)
      ]);
      setForecast(fData);
      setAlerts(aData);
      setSuggestions(sData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [balance]);

  const handleMarkPaid = async (id) => {
    await markInvoicePaid(id);
    loadData(); // refresh
  };

  if (loading || !forecast) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl text-muted animate-pulse">Loading intelligence...</div>
      </div>
    );
  }

  // Combine dates and daily balance into chart data
  const chartData = forecast.dates.map((date, idx) => ({
    name: date,
    Balance: forecast.daily_balance[idx],
    p25: forecast.p25 ? forecast.p25[idx] : null,
    p75: forecast.p75 ? forecast.p75[idx] : null,
    Band: forecast.p25 && forecast.p75 ? [forecast.p25[idx], forecast.p75[idx]] : null,
    ZeroLine: 0
  }));

  const formatCurrency = (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

  return (
    <div className="p-6 max-w-7xl mx-auto animate-fade-in">
      <header className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Wallet className="text-accent" /> CashFlow Blindspot
          </h1>
          <p className="text-muted">Predictive liquidity intelligence</p>
        </div>
        
        <div className="flex items-center gap-4">
          <label className="text-sm text-muted">Starting Balance:</label>
          <input 
            type="number" 
            value={balance} 
            onChange={(e) => setBalance(Number(e.target.value))}
            className="bg-transparent border border-[var(--border-color)] text-white px-3 py-1 rounded-md w-32 focus:outline-none focus:border-[var(--primary)] transition-colors"
          />
        </div>
      </header>

      {/* Alert Banner */}
      {alerts && alerts.tier > 0 && (
        <div className={`alert-banner alert-tier-${alerts.tier}`}>
          {alerts.tier === 1 ? <AlertCircle size={28} /> : <Bell size={28} />}
          <div>
            <h3 className="font-bold text-lg">{alerts.headline}</h3>
            <p className="opacity-90">{alerts.detail}</p>
          </div>
        </div>
      )}

      {/* Top Metrics Row */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="glass-panel">
          <p className="text-sm text-muted text-transform-uppercase mb-2 flex items-center gap-2"><Clock size={16}/> Runway</p>
          <p className="text-2xl font-bold">{forecast.days_to_shortfall !== null ? `${forecast.days_to_shortfall} Days` : '90+ Days'}</p>
        </div>
        <div className="glass-panel">
          <p className="text-sm text-muted text-transform-uppercase mb-2">Total Receivables (AR)</p>
          <p className="text-2xl font-bold text-green-400">{formatCurrency(forecast.total_ar)}</p>
        </div>
        <div className="glass-panel">
          <p className="text-sm text-muted text-transform-uppercase mb-2">Total Payables (AP)</p>
          <p className="text-2xl font-bold text-red-400">{formatCurrency(forecast.total_ap)}</p>
        </div>
        <div className="glass-panel">
          <p className="text-sm text-muted text-transform-uppercase mb-2">Shortfall Probability</p>
          <p className="text-2xl font-bold">{alerts ? (alerts.probability * 100).toFixed(1) : 0}%</p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Chart */}
        <div className="glass-panel" style={{ height: '400px' }}>
          <h3 className="text-xl font-bold mb-4">90-Day Liquidity Forecast</h3>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
              <XAxis dataKey="name" stroke="rgba(255,255,255,0.5)" tick={{fill: 'rgba(255,255,255,0.5)'}} minTickGap={30} />
              <YAxis stroke="rgba(255,255,255,0.5)" tick={{fill: 'rgba(255,255,255,0.5)'}} tickFormatter={(val) => `₹${val/1000}k`} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'rgba(26, 29, 36, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                itemStyle={{ color: '#fff' }}
              />
              <Area type="monotone" dataKey="Band" stroke="none" fill="rgba(59, 130, 246, 0.15)" />
              <Area type="monotone" dataKey="ZeroLine" stroke="none" fill="rgba(239, 68, 68, 0.1)" fillOpacity={1} />
              <Line type="monotone" dataKey="Balance" stroke="var(--primary)" strokeWidth={3} dot={false} activeDot={{ r: 8 }} />
              <Line type="step" dataKey="ZeroLine" stroke="rgba(239, 68, 68, 0.5)" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* AI Suggestions Row */}
      {suggestions && suggestions.gap > 0 && (
        <div className="glass-panel mb-6 border-[var(--primary)]" style={{borderWidth: '2px', borderStyle: 'dashed'}}>
          <h3 className="text-xl font-bold flex items-center gap-2 mb-2"><TrendingDown className="text-accent" /> AI Action Plan</h3>
          <p className="text-muted mb-4">{suggestions.summary}</p>
          <div className="flex gap-4">
            <div className="p-4 bg-[rgba(255,255,255,0.05)] rounded-lg flex-1 border border-[var(--border-color)]">
              <p className="text-sm text-muted">Projected Gap</p>
              <p className="text-xl font-bold">{formatCurrency(suggestions.gap)}</p>
            </div>
            <div className="p-4 bg-[rgba(255,255,255,0.05)] rounded-lg flex-1 border border-[var(--border-color)]">
              <p className="text-sm text-muted">Closable via Actions</p>
              <p className="text-xl font-bold text-green-400">{formatCurrency(suggestions.gap_closable)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Data Tables */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '1.5rem' }}>
        
        {/* Invoices */}
        <div className="glass-panel" style={{ overflowX: 'auto' }}>
          <h3 className="text-xl font-bold mb-4 flex items-center justify-between">
            High-Risk Invoices 
            <span className="text-sm font-normal text-muted bg-[rgba(255,255,255,0.1)] px-2 py-1 rounded">Ranked by Expected Risk</span>
          </h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Amount</th>
                <th>P(Late)</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {suggestions && suggestions.invoices.map(inv => (
                <tr key={inv.invoice_id}>
                  <td>
                    <p className="font-bold">{inv.customer_name}</p>
                    <p className="text-xs text-muted">{inv.days_overdue} days overdue</p>
                  </td>
                  <td className="font-bold">{formatCurrency(inv.amount)}</td>
                  <td>
                    <span className={`px-2 py-1 rounded text-xs ${inv.p_late > 0.5 ? 'bg-[rgba(239,68,68,0.2)] text-red-400' : 'bg-[rgba(245,158,11,0.2)] text-orange-400'}`}>
                      {(inv.p_late * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-2">
                      <button className="btn btn-secondary" onClick={() => {
                        alert(inv.draft_message);
                      }} title="Copy WhatsApp Draft">
                        <Send size={16} />
                      </button>
                      <button className="btn" onClick={() => handleMarkPaid(inv.invoice_id)} title="Mark Paid">
                        <CheckCircle2 size={16} /> Paid
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {(!suggestions || suggestions.invoices.length === 0) && (
                <tr><td colSpan="4" className="text-center text-muted">No high-risk invoices to chase.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Payables */}
        <div className="glass-panel" style={{ overflowX: 'auto' }}>
          <h3 className="text-xl font-bold mb-4">Delayable Payables</h3>
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
              {suggestions && suggestions.payables.map(pay => (
                <tr key={pay.payable_id}>
                  <td className="font-bold">{pay.vendor_name}</td>
                  <td className="font-bold">{formatCurrency(pay.amount)}</td>
                  <td className="text-orange-400">{pay.days_until_due} days</td>
                  <td>
                    <button className="btn btn-secondary">Request Extension</button>
                  </td>
                </tr>
              ))}
              {(!suggestions || suggestions.payables.length === 0) && (
                <tr><td colSpan="4" className="text-center text-muted">No payables recommended for delay.</td></tr>
              )}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
}
