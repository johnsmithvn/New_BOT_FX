/**
 * Analytics.helpers.js
 *
 * Pure data-transformation functions used by Analytics.jsx charts.
 * Extracted so both production code and tests share the same source of truth.
 */

/**
 * Group daily PnL into weekly wins/losses/net (last 12 weeks).
 * @param {Array<{date: string, net_pnl?: number}>} data
 * @returns {Array<{week: string, wins: number, losses: number, net: number}>}
 */
export function aggregateWeekly(data) {
  if (!data.length) return [];
  const weeks = {};
  data.forEach(d => {
    // Parse YYYY-MM-DD as UTC to avoid timezone shifts
    const parts = d.date.split('-');
    const dt = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2]));
    const day = dt.getUTCDay();
    const diff = dt.getUTCDate() - day + (day === 0 ? -6 : 1);
    dt.setUTCDate(diff);
    const weekStart = dt.toISOString().slice(0, 10);
    if (!weeks[weekStart]) weeks[weekStart] = { week: weekStart, wins: 0, losses: 0, net: 0 };
    const pnl = d.net_pnl || 0;
    if (pnl >= 0) weeks[weekStart].wins += pnl;
    else weeks[weekStart].losses += Math.abs(pnl);
    weeks[weekStart].net += pnl;
  });
  return Object.values(weeks).slice(-12);
}

/**
 * Build a histogram from PnL data with configurable bucket size.
 * @param {Array<{net_pnl?: number, pnl?: number}>} data
 * @param {number} bucketSize
 * @returns {Array<{bucket: number, count: number}>}
 */
export function buildHistogram(data, bucketSize = 50) {
  const histogram = {};
  data.forEach(d => {
    const val = d.net_pnl || d.pnl || 0;
    const bucket = Math.round(val / bucketSize) * bucketSize;
    histogram[bucket] = (histogram[bucket] || 0) + 1;
  });
  return Object.entries(histogram)
    .map(([k, v]) => ({ bucket: Number(k), count: v }))
    .sort((a, b) => a.bucket - b.bucket);
}

/**
 * Calculate drawdown series from equity curve data.
 * @param {Array<{date: string, cumulative_pnl?: number}>} data
 * @returns {Array<{date: string, drawdown: number, equity: number}>}
 */
export function calculateDrawdown(data) {
  let peak = 0;
  return data.map(d => {
    const eq = d.cumulative_pnl || 0;
    if (eq > peak) peak = eq;
    const drawdown = peak > 0 ? ((eq - peak) / peak) * 100 : 0;
    return { date: d.date, drawdown: Math.min(drawdown, 0), equity: eq };
  });
}

/**
 * Enrich daily data with cumulative trade count.
 * @param {Array<{date: string, trades?: number}>} data
 * @returns {Array}
 */
export function enrichWithCumulative(data) {
  let cumCount = 0;
  return data.map(d => {
    cumCount += (d.trades || 0);
    return { ...d, cumTrades: cumCount };
  });
}
