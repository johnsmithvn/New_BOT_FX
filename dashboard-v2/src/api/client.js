/**
 * API client — fetch wrapper + TanStack Query config.
 *
 * In dev mode, Vite proxy forwards /api/* to http://localhost:8000.
 * In production, set VITE_API_URL to the dashboard v1 address.
 */

const BASE = import.meta.env.VITE_API_URL || '';

async function fetchApi(endpoint, params = {}, options = {}) {
  const { method = 'GET' } = options;
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== '') {
      query.set(k, String(v));
    }
  }
  const qs = query.toString();
  const url = `${BASE}/api${endpoint}${qs ? `?${qs}` : ''}`;

  const headers = {};
  const apiKey = localStorage.getItem('dashboard_api_key');
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const res = await fetch(url, { method, headers });

  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ── Typed API methods ────────────────────────────────────────

export const api = {
  overview:       ()                     => fetchApi('/overview'),
  dailyPnl:       (days = 30)            => fetchApi('/daily-pnl', { days }),
  channels:       ()                     => fetchApi('/channels'),
  channelDailyPnl:(id, days = 30)        => fetchApi(`/channels/${id}/daily-pnl`, { days }),
  trades:         (params = {})          => fetchApi('/trades', params),
  active:         ()                     => fetchApi('/active'),
  equityCurve:    (days = 365)           => fetchApi('/equity-curve', { days }),
  symbolStats:    ()                     => fetchApi('/symbol-stats'),
  symbols:        ()                     => fetchApi('/symbols'),
  channelList:    ()                     => fetchApi('/channel-list'),
  pnlHeatmap:     (days = 365)           => fetchApi('/pnl-heatmap', { days }),
  drawdown:       (days = 365)           => fetchApi('/drawdown', { days }),
  pnlDistribution:()                    => fetchApi('/pnl-distribution'),
  exportCsvUrl:   (params = {})          => {
    const query = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v) query.set(k, v);
    }
    const qs = query.toString();
    return `${BASE}/api/export/csv${qs ? `?${qs}` : ''}`;
  },

  // Signal Lifecycle
  signals:         (params = {})          => fetchApi('/signals', params),
  signalDetail:    (fp)                   => fetchApi(`/signals/${encodeURIComponent(fp)}`),
  deleteSignal:    (fp)                   => fetchApi(`/signals/${encodeURIComponent(fp)}`, {}, { method: 'DELETE' }),
  deleteOrder:     (id)                   => fetchApi(`/orders/${id}`, {}, { method: 'DELETE' }),
  deleteTrade:     (id)                   => fetchApi(`/trades/${id}`, {}, { method: 'DELETE' }),

  // Data Management
  tableCounts:     ()                     => fetchApi('/data/counts'),
  clearTable:      (table)                => fetchApi(`/data/${table}`, {}, { method: 'DELETE' }),
  clearAll:        ()                     => fetchApi('/data/all', {}, { method: 'DELETE' }),
};
