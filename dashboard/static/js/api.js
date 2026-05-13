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
  schedules:    (params = '') => API.get(`/api/schedules${params}`),
  schedule:     (id)          => API.get(`/api/schedules/${id}`),
  syncOrders:   ()            => API.post('/api/orders/sync', {}),
  markArrived:  (id)          => API.patch(`/api/schedules/${id}/arrived`, {}),
  rematch:      (id)          => API.post(`/api/schedules/${id}/rematch`, {}),
  odooConfig:   ()            => API.get('/api/schedules/odoo-config'),
  orderStatus:  ()            => API.get('/api/schedules/order-status'),
  liveStatus:       (days = 7)              => API.get(`/api/orders/live-status?days=${days}`),
  liveStatusExport: (days = 7, status = '') => `/api/orders/live-status/export?days=${days}${status ? '&status='+encodeURIComponent(status) : ''}`,
  finalStatus:      (days = 30)             => API.get(`/api/orders/final-status?days=${days}`),

  // ── Proposals (AI matching workflow) ──────────────────────────────────────
  proposals:       (params = '') => API.get(`/api/proposals${params}`),
  proposal:        (id)          => API.get(`/api/proposals/${id}`),
  confirmProposal: (id, by = 'dispatcher') =>
    API.patch(`/api/proposals/${id}/confirm`, { confirmed_by: by }),
  rejectProposal:  (id, reason = '') =>
    API.patch(`/api/proposals/${id}/reject`, { reject_reason: reason }),

  // ── Allocations (dispatcher workflow) ─────────────────────────────────────
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
  revertAllocation:  (id)                => API.patch(`/api/allocations/${id}/revert`, {}),
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

// ── Branded confirm dialog ─────────────────────────────────────────────────────
// Returns Promise<boolean>. Drop-in replacement for window.confirm().
//
// Usage:
//   if (!await showDialog({ title, message, confirmText, variant })) return;
//
// variant: 'green' | 'danger' | 'navy' | 'orange'  (default: 'navy')

function showDialog({
  title        = 'Confirm',
  message      = '',
  confirmText  = 'Confirm',
  cancelText   = 'Cancel',
  variant      = 'navy',
} = {}) {
  return new Promise(resolve => {
    const ICONS = {
      green:  '✓',
      danger: '!',
      navy:   '?',
      orange: '⚠',
    };

    const overlay = document.createElement('div');
    overlay.className = 'dialog-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');

    // Build message HTML — support \n as paragraph breaks
    const paragraphs = String(message).split('\n').filter(Boolean)
      .map(p => `<p>${p}</p>`).join('');

    overlay.innerHTML = `
      <div class="dialog-box">
        <div class="dialog-header">
          <div class="dialog-icon ${variant}">${ICONS[variant] || '?'}</div>
          <div class="dialog-title">${title}</div>
        </div>
        ${paragraphs ? `<div class="dialog-body">${paragraphs}</div>` : ''}
        <div class="dialog-footer">
          <button class="btn btn-outline btn-sm" id="dlg-cancel">${cancelText}</button>
          <button class="btn btn-${variant === 'green' ? 'green' : variant === 'danger' ? 'danger' : variant === 'orange' ? 'orange' : 'primary'} btn-sm" id="dlg-confirm">${confirmText}</button>
        </div>
      </div>`;

    const close = (result) => {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.15s';
      setTimeout(() => overlay.remove(), 150);
      resolve(result);
    };

    overlay.querySelector('#dlg-confirm').addEventListener('click', () => close(true));
    overlay.querySelector('#dlg-cancel').addEventListener('click',  () => close(false));

    // Close on backdrop click
    overlay.addEventListener('click', e => { if (e.target === overlay) close(false); });

    // Close on Escape
    const onKey = (e) => {
      if (e.key === 'Escape') { document.removeEventListener('keydown', onKey); close(false); }
    };
    document.addEventListener('keydown', onKey);

    document.body.appendChild(overlay);

    // Auto-focus confirm button
    setTimeout(() => overlay.querySelector('#dlg-confirm')?.focus(), 50);
  });
}
