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

  async delete(path) {
    const res = await fetch(this.base + path, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) throw new Error(`DELETE ${path} → ${res.status}`);
    if (res.status === 204) return null;
    return res.json();
  },

  // ── Schedules ──────────────────────────────────────────────────────────────
  schedules:  (params = '') => API.get(`/api/schedules${params}`),
  schedule:   (id)          => API.get(`/api/schedules/${id}`),
  syncOrders: ()            => API.post('/api/orders/sync', {}),
  markArrived:(id)          => API.patch(`/api/schedules/${id}/arrived`, {}),

  // ── Allocations (new dispatcher workflow) ─────────────────────────────────
  allocations:       (params = '')       => API.get(`/api/allocations${params}`),
  allocation:        (id)                => API.get(`/api/allocations/${id}`),
  createAllocation:  (body)              => API.post('/api/allocations', body),
  addItem:           (id, item)          => API.post(`/api/allocations/${id}/items`, item),
  removeItem:        (id, itemId)        => API.delete(`/api/allocations/${id}/items/${itemId}`),
  loadAllocation:    (id, by = 'dispatcher') =>
    API.patch(`/api/allocations/${id}/load`, { released_by: by }),
  releaseAllocation: (id, by = 'dispatcher') =>
    API.loadAllocation(id, by),
  markLoaded:        (id)                => API.patch(`/api/allocations/${id}/loaded`, {}),
  revertAllocation:  (id)               => API.patch(`/api/allocations/${id}/revert`, {}),
  setRemarks:        (id, text)          => API.patch(`/api/allocations/${id}/remarks`, { remarks: text }),

  // ── Misc ──────────────────────────────────────────────────────────────────
  summary: () => API.get('/api/savings/summary'),
  health:  () => API.get('/api/health'),
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
