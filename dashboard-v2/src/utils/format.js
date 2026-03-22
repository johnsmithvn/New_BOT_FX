/**
 * Shared formatting utilities for Dashboard V2.
 *
 * Currency convention: suffix $ (e.g. "0.12 $", "-615.5K $")
 */

/**
 * Format a number as currency with $ suffix.
 * @param {number} n — numeric value
 * @param {object} opts — { compact: bool, decimals: number }
 * @returns {string} e.g. "-0.12 $", "1.2K $"
 */
export function fmtCcy(n, { compact = true, decimals = 2 } = {}) {
  if (n == null || isNaN(n)) return `0.00 $`;
  const abs = Math.abs(n);
  let str;
  if (compact && abs >= 1000) {
    str = `${(abs / 1000).toFixed(1)}K`;
  } else {
    str = abs.toFixed(decimals);
  }
  return `${n < 0 ? '-' : ''}${str} $`;
}

/**
 * Short currency for axis ticks — e.g. "0.1 $"
 */
export function tickCcy(v) {
  if (v == null) return '0 $';
  const abs = Math.abs(v);
  let str;
  if (abs >= 1000) str = `${(abs / 1000).toFixed(0)}K`;
  else if (abs >= 100) str = `${abs.toFixed(0)}`;
  else if (abs >= 1) str = `${abs.toFixed(1)}`;
  else str = `${abs.toFixed(2)}`;
  return `${v < 0 ? '-' : ''}${str} $`;
}

/**
 * Format number for tooltip — e.g. "-0.12 $"
 */
export function tooltipCcy(v) {
  if (v == null) return '0.00 $';
  return `${v.toFixed(2)} $`;
}

/**
 * Build a channel name lookup map from channelList.
 * @param {Array} channelList — [{id, name}]
 * @returns {Object} { [id]: name }
 */
export function buildChannelMap(channelList) {
  const map = {};
  (channelList || []).forEach(c => {
    map[String(c.id)] = c.name || String(c.id);
  });
  return map;
}

/**
 * Resolve channel ID to display name.
 * Priority: channelMap name > fallback last 8 chars
 */
export function resolveChannelName(channelId, channelMap) {
  if (!channelId) return '—';
  const name = channelMap[String(channelId)];
  if (name && name !== String(channelId)) return name;
  // Fallback: show shortened ID
  const id = String(channelId);
  return id.length > 10 ? `…${id.slice(-8)}` : id;
}
