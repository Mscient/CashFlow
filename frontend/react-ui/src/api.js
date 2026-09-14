const BASE = 'http://localhost:5000/api';

const req = async (path, opts = {}) => {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
  return json;
};

// Dashboard
export const fetchDashboard = (balance) => req(`/dashboard?balance=${balance}`);

// Invoices
export const fetchInvoices  = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return req(`/invoices?${q}`);
};
export const createInvoice  = (data)       => req('/invoices', { method:'POST', body:JSON.stringify(data) });
export const updateInvoice  = (id, data)   => req(`/invoices/${id}`, { method:'PATCH', body:JSON.stringify(data) });
export const markInvoicePaid = (id, paid_date) =>
  req(`/invoices/${id}/mark_paid`, { method:'POST', body:JSON.stringify({ paid_date }) });
export const fetchChaseLog  = (id)         => req(`/invoices/${id}/chase-log`);
export const logChase       = (id, data)   => req(`/invoices/${id}/chase`, { method:'POST', body:JSON.stringify(data) });

// Payables
export const fetchPayables  = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return req(`/payables?${q}`);
};
export const createPayable  = (data)       => req('/payables', { method:'POST', body:JSON.stringify(data) });
export const updatePayable  = (id, data)   => req(`/payables/${id}`, { method:'PATCH', body:JSON.stringify(data) });
export const markPayablePaid = (id)        => req(`/payables/${id}/mark_paid`, { method:'POST', body:'{}' });

// Customers
export const fetchCustomers    = ()        => req('/customers');
export const createCustomer    = (data)    => req('/customers', { method:'POST', body:JSON.stringify(data) });
export const updateCustomer    = (id,data) => req(`/customers/${id}`, { method:'PATCH', body:JSON.stringify(data) });
export const fetchCustomerDetail = (id)   => req(`/customers/${id}/invoices`);
export const fetchCustomerProfile = (id)  => req(`/customers/${id}/profile`);

// Vendors
export const fetchVendors   = ()           => req('/vendors');
export const createVendor   = (data)       => req('/vendors', { method:'POST', body:JSON.stringify(data) });

// Analytics
export const fetchSummary   = ()           => req('/analytics/summary');
export const fetchCashflow  = (balance, days) => req(`/analytics/cashflow?balance=${balance}&days=${days}`);

// Message center
export const fetchMessageCenter = (balance) => req(`/alerts/message-center?balance=${balance}`);

// Settings
export const fetchSettings  = ()           => req('/settings');
export const saveSettings   = (data)       => req('/settings', { method:'POST', body:JSON.stringify(data) });

// Export
export const exportInvoicesUrl  = () => `${BASE}/export/invoices.csv`;
export const exportPayablesUrl  = () => `${BASE}/export/payables.csv`;

// Health
export const fetchHealth    = ()           => req('/health');

// Smart Import
export const smartIngest = (formData) => {
  return fetch(`${BASE}/ingest/smart`, {
    method: 'POST',
    body: formData,          // multipart – no Content-Type header (browser sets boundary)
  }).then(async (res) => {
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
    return json;
  });
};

export const smartConfirm = (rows) =>
  req('/ingest/smart/confirm', { method: 'POST', body: JSON.stringify({ rows }) });
