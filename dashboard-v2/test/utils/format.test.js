import { describe, it, expect } from 'vitest';
import { fmtCcy, tickCcy, tooltipCcy, buildChannelMap, resolveChannelName } from '../../src/utils/format';

/* ─── fmtCcy ───────────────────────────────────────────────── */
describe('fmtCcy', () => {
  it('formats positive number with $ suffix', () => {
    expect(fmtCcy(123.456)).toBe('123.46 $');
  });

  it('formats negative number with - prefix', () => {
    expect(fmtCcy(-42.7)).toBe('-42.70 $');
  });

  it('formats zero', () => {
    expect(fmtCcy(0)).toBe('0.00 $');
  });

  it('returns 0.00 $ for null', () => {
    expect(fmtCcy(null)).toBe('0.00 $');
  });

  it('returns 0.00 $ for undefined', () => {
    expect(fmtCcy(undefined)).toBe('0.00 $');
  });

  it('returns 0.00 $ for NaN', () => {
    expect(fmtCcy(NaN)).toBe('0.00 $');
  });

  it('compacts values >= 1000 to K', () => {
    expect(fmtCcy(1500)).toBe('1.5K $');
  });

  it('compacts negative values >= 1000', () => {
    expect(fmtCcy(-2500)).toBe('-2.5K $');
  });

  it('disables compact when compact=false', () => {
    expect(fmtCcy(1500, { compact: false })).toBe('1500.00 $');
  });

  it('uses custom decimals', () => {
    expect(fmtCcy(3.14159, { compact: false, decimals: 4 })).toBe('3.1416 $');
  });

  it('does not compact values < 1000', () => {
    expect(fmtCcy(999.99)).toBe('999.99 $');
  });
});

/* ─── tickCcy ──────────────────────────────────────────────── */
describe('tickCcy', () => {
  it('formats >= 1000 as K (integer)', () => {
    expect(tickCcy(2500)).toBe('3K $');  // toFixed(0) on 2.5 = 3 — actually 2500/1000=2.5 → "3K"
    expect(tickCcy(5000)).toBe('5K $');
  });

  it('formats >= 100 as integer', () => {
    expect(tickCcy(150)).toBe('150 $');
  });

  it('formats >= 1 with 1 decimal', () => {
    expect(tickCcy(3.75)).toBe('3.8 $');
  });

  it('formats < 1 with 2 decimals', () => {
    expect(tickCcy(0.123)).toBe('0.12 $');
  });

  it('handles negative values', () => {
    expect(tickCcy(-500)).toBe('-500 $');
  });

  it('returns 0 $ for null', () => {
    expect(tickCcy(null)).toBe('0 $');
  });
});

/* ─── tooltipCcy ───────────────────────────────────────────── */
describe('tooltipCcy', () => {
  it('formats positive with 2 decimals', () => {
    expect(tooltipCcy(12.345)).toBe('12.35 $');
  });

  it('formats negative', () => {
    expect(tooltipCcy(-7.5)).toBe('-7.50 $');
  });

  it('returns 0.00 $ for null', () => {
    expect(tooltipCcy(null)).toBe('0.00 $');
  });
});

/* ─── buildChannelMap ──────────────────────────────────────── */
describe('buildChannelMap', () => {
  it('builds map from channel list', () => {
    const list = [
      { id: 123, name: 'Channel A' },
      { id: 456, name: 'Channel B' },
    ];
    const map = buildChannelMap(list);
    expect(map).toEqual({ '123': 'Channel A', '456': 'Channel B' });
  });

  it('uses stringified id as fallback when name is missing', () => {
    const list = [{ id: 789 }];
    const map = buildChannelMap(list);
    expect(map).toEqual({ '789': '789' });
  });

  it('returns empty object for null input', () => {
    expect(buildChannelMap(null)).toEqual({});
  });

  it('returns empty object for empty array', () => {
    expect(buildChannelMap([])).toEqual({});
  });
});

/* ─── resolveChannelName ───────────────────────────────────── */
describe('resolveChannelName', () => {
  const channelMap = { '123': 'Signal Pro', '456': '456' };

  it('returns mapped name', () => {
    expect(resolveChannelName('123', channelMap)).toBe('Signal Pro');
  });

  it('returns shortened ID for unknown channel (long ID)', () => {
    const longId = '1234567890123';
    expect(resolveChannelName(longId, channelMap)).toBe('…67890123');
  });

  it('returns full short ID for unknown channel', () => {
    expect(resolveChannelName('999', channelMap)).toBe('999');
  });

  it('returns em-dash for null/empty channelId', () => {
    expect(resolveChannelName(null, channelMap)).toBe('—');
    expect(resolveChannelName('', channelMap)).toBe('—');
  });

  it('returns shortened ID when map value equals stringified ID', () => {
    // channelMap['456'] = '456' (same as ID), so fallback to shortened
    expect(resolveChannelName('456', channelMap)).toBe('456');
  });
});
