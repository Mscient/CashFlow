const API_BASE = 'http://localhost:5000/api';

export const fetchForecast = async (balance) => {
  const res = await fetch(`${API_BASE}/forecast?balance=${balance}`);
  if (!res.ok) throw new Error('Failed to fetch forecast');
  return res.json();
};

export const fetchAlerts = async (balance) => {
  const res = await fetch(`${API_BASE}/alerts?balance=${balance}`);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
};

export const fetchSuggestions = async (balance) => {
  const res = await fetch(`${API_BASE}/suggestions?balance=${balance}`);
  if (!res.ok) throw new Error('Failed to fetch suggestions');
  return res.json();
};

export const markInvoicePaid = async (invoiceId) => {
  const res = await fetch(`${API_BASE}/invoices/${invoiceId}/mark_paid`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  });
  if (!res.ok) throw new Error('Failed to mark invoice as paid');
  return res.json();
};
