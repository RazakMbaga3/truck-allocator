/**
 * schedule-feed.js — SSE client for live truck schedule updates.
 *
 * Listens to GET /api/schedules/feed and handles:
 *   truck_allocated   → remove truck row from available list, move to allocated
 *   truck_arrived     → update row status badge
 *   truck_dispatched  → update row status badge
 *   proposals_updated → refresh proposals column for that truck
 *   schedule_updated  → refresh truck plate / status
 *   heartbeat         → no-op (keeps connection alive)
 */

class ScheduleFeed {
  constructor(onEvent) {
    this.onEvent = onEvent;  // callback(eventType, data)
    this.es = null;
    this.reconnectDelay = 3000;
    this.connected = false;
  }

  connect() {
    if (this.es) this.es.close();

    this.es = new EventSource('/api/schedules/feed');

    this.es.onopen = () => {
      this.connected = true;
      this.reconnectDelay = 3000;
      this._updateIndicator(true);
    };

    this.es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type !== 'heartbeat') {
          this.onEvent(data.type, data);
        }
      } catch (err) {
        console.warn('SSE parse error:', err);
      }
    };

    this.es.onerror = () => {
      this.connected = false;
      this._updateIndicator(false);
      this.es.close();
      // Exponential backoff reconnect
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 30000);
    };
  }

  disconnect() {
    if (this.es) { this.es.close(); this.es = null; }
  }

  _updateIndicator(connected) {
    const dot = document.querySelector('.live-dot');
    const label = document.getElementById('sse-status');
    if (dot) dot.style.background = connected ? 'var(--green-light)' : 'var(--gray-400)';
    if (label) label.textContent = connected ? 'LIVE' : 'Reconnecting…';
  }
}
