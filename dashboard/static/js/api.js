/**
 * api.js — Shared API client for the Return Truck Allocator dashboard.
 * Base URL: window.location.origin (same server as FastAPI)
 */

const API = {
  base: '',

  async get(path) {
    const res = await fetch(this.base + path);
    if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
    return res.json();
  },

  async post(path, body = {}) {
    const res = await fetch(this.base + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
    return res.json();
  },

  async patch(path, body = {}) {
    const res = await fetch(this.base + path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`);
    return res.json();
  },

  // Convenience methods
  schedules:  (params = '') => API.get(`/api/schedules${params}`),
  schedule:   (id)          => API.get(`/api/schedules/${id}`),
  proposals:  (params = '') => API.get(`/api/proposals${params}`),
  proposal:   (id)          => API.get(`/api/proposals/${id}`),
  orders:     (params = '') => API.get(`/api/orders${params}`),
  summary:    ()            => API.get('/api/savings/summary'),
  health:     ()            => API.get('/api/health'),

  confirmProposal: (id, confirmedBy = 'dispatcher') =>
    API.patch(`/api/proposals/${id}/confirm`, { confirmed_by: confirmedBy }),

  rejectProposal: (id) =>
    API.patch(`/api/proposals/${id}/reject`, {}),

  markArrived:  (id) => API.patch(`/api/schedules/${id}/arrived`, {}),
  markDispatch: (id) => API.patch(`/api/schedules/${id}/dispatch`, {}),
  rematch:      (id) => API.post(`/api/schedules/${id}/rematch`, {}),
  syncOrders:   ()   => API.post('/api/orders/sync', {}),
};

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtTZS(n) {
  if (!n || n === 0) return '—';
  if (n >= 1_000_000) return `TZS ${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)    return `TZS ${Math.round(n / 1000)}K`;
  return `TZS ${Math.round(n).toLocaleString()}`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const diffH = (d - now) / 3600000;

  if (diffH < -24)   return d.toLocaleDateString('en-GB', {day:'numeric', month:'short'});
  if (diffH < 0)     return 'Overdue';
  if (diffH < 24)    return 'TODAY ' + d.toLocaleTimeString('en-GB', {hour:'2-digit', minute:'2-digit'});
  if (diffH < 48)    return 'TOMORROW';
  return d.toLocaleDateString('en-GB', {weekday:'short', day:'numeric', month:'short'});
}

function fmtStatus(status) {
  const map = {
    EXPECTED:      ['expected',   'Expected'],
    PRE_CONFIRMED: ['pre',        'Pre-Confirmed'],
    ARRIVED:       ['arrived',    'Arrived'],
    ALLOCATED:     ['allocated',  'Allocated ✓'],
    DISPATCHED:    ['dispatched', 'Dispatched'],
    PROPOSED:      ['proposed',   'Proposed'],
    CONFIRMED:     ['confirmed',  'Confirmed ✓'],
    UNALLOCATED:   ['expected',   'Unallocated'],
  };
  const [cls, label] = map[status] || ['expected', status];
  return `<span class="badge badge-${cls}">${label}</span>`;
}

// ── Toast notifications ────────────────────────────────────────────────────────

function showToast(message, type = '') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
