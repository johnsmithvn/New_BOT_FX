/**
 * Overview.helpers.js
 *
 * Pure data-transformation functions used by Overview.jsx charts.
 * Extracted so both production code and tests share the same source of truth.
 */

/**
 * Aggregate daily PnL entries by weekday (Mon–Fri).
 * @param {Array<{date: string, net_pnl?: number}>} dailyData
 * @returns {Array<{day: string, pnl: number, count: number}>}
 */
export function aggregateByWeekday(dailyData) {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const agg = days.map(d => ({ day: d, pnl: 0, count: 0 }));
  dailyData.forEach(d => {
    if (!d.date) return;
    const dow = new Date(d.date).getDay();
    agg[dow].pnl += (d.net_pnl || 0);
    agg[dow].count++;
  });
  // Trading days only (Mon-Fri)
  return agg.slice(1, 6);
}

/**
 * Merge daily PnL with equity curve by date, adding a `cumulative` field.
 * @param {Array} dailyData
 * @param {Array} equityData
 * @returns {Array}
 */
export function mergeDailyAndEquity(dailyData, equityData) {
  const eqMap = {};
  (equityData || []).forEach(d => { eqMap[d.date] = d.cumulative_pnl; });
  return (dailyData || []).map(d => ({
    ...d,
    cumulative: eqMap[d.date] ?? null,
  }));
}

/**
 * Aggregate daily PnL into monthly win/loss buckets (last 6 months).
 * @param {Array<{date: string, net_pnl?: number}>} data
 * @returns {Array<{month: string, wins: number, losses: number}>}
 */
export function aggregateMonthly(data) {
  if (!data.length) return [];
  const months = {};
  data.forEach(d => {
    const month = d.date?.slice(0, 7);
    if (!month) return;
    if (!months[month]) months[month] = { month, wins: 0, losses: 0 };
    const pnl = d.net_pnl || 0;
    if (pnl >= 0) months[month].wins += pnl;
    else months[month].losses += Math.abs(pnl);
  });
  return Object.values(months).slice(-6);
}
