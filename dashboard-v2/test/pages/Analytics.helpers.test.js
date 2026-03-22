/**
 * Tests for data transformation functions used in Analytics.jsx.
 *
 * Imports the PRODUCTION helpers (single source of truth).
 */
import { describe, it, expect } from 'vitest';
import {
  aggregateWeekly,
  buildHistogram,
  calculateDrawdown,
  enrichWithCumulative,
} from '../../src/pages/Analytics.helpers';

describe('aggregateWeekly (Analytics WinLossStackedBars)', () => {
  it('groups by week correctly', () => {
    const data = [
      { date: '2026-03-16', net_pnl: 50 },  // Monday
      { date: '2026-03-17', net_pnl: -20 }, // Tuesday (same week)
      { date: '2026-03-23', net_pnl: 30 },  // Next Monday
    ];
    const result = aggregateWeekly(data);
    expect(result).toHaveLength(2);
    expect(result[0].wins).toBe(50);
    expect(result[0].losses).toBe(20);
    expect(result[0].net).toBe(30);
    expect(result[1].wins).toBe(30);
  });

  it('returns empty for empty data', () => {
    expect(aggregateWeekly([])).toEqual([]);
  });

  it('limits to last 12 weeks', () => {
    const data = [];
    for (let w = 0; w < 15; w++) {
      const dt = new Date(Date.UTC(2026, 0, 5 + w * 7));
      data.push({ date: dt.toISOString().slice(0, 10), net_pnl: 10 });
    }
    const result = aggregateWeekly(data);
    expect(result.length).toBeLessThanOrEqual(12);
  });
});

describe('buildHistogram (Analytics PnlDistributionChart)', () => {
  it('buckets data correctly with size 50', () => {
    const data = [
      { net_pnl: 10 },   // bucket 0
      { net_pnl: 30 },   // bucket 50  (round(30/50)=1 → 50)
      { net_pnl: 60 },   // bucket 50  (round(60/50)=1 → 50)
      { net_pnl: -80 },  // bucket -100 (round(-80/50)=-2 → -100)
      { net_pnl: 120 },  // bucket 100
    ];
    const result = buildHistogram(data);
    expect(result[0].bucket).toBeLessThan(0);  // -100
    expect(result.length).toBeGreaterThan(0);
  });

  it('returns empty array for empty data', () => {
    expect(buildHistogram([])).toEqual([]);
  });

  it('sorts by bucket ascending', () => {
    const data = [
      { net_pnl: 100 },
      { net_pnl: -100 },
      { net_pnl: 0 },
    ];
    const result = buildHistogram(data);
    for (let i = 1; i < result.length; i++) {
      expect(result[i].bucket).toBeGreaterThanOrEqual(result[i - 1].bucket);
    }
  });
});

describe('calculateDrawdown (Analytics DrawdownChart)', () => {
  it('calculates drawdown from peak', () => {
    const data = [
      { date: '2026-01-01', cumulative_pnl: 100 },
      { date: '2026-01-02', cumulative_pnl: 150 }, // new peak
      { date: '2026-01-03', cumulative_pnl: 120 }, // drawdown from 150
      { date: '2026-01-04', cumulative_pnl: 160 }, // new peak
    ];
    const result = calculateDrawdown(data);
    expect(result[0].drawdown).toBe(0); // first data = peak
    expect(result[1].drawdown).toBe(0); // new peak
    expect(result[2].drawdown).toBeCloseTo(-20, 1); // (120-150)/150 * 100 = -20%
    expect(result[3].drawdown).toBe(0); // new peak
  });

  it('drawdown is always <= 0', () => {
    const data = [
      { date: '2026-01-01', cumulative_pnl: 100 },
      { date: '2026-01-02', cumulative_pnl: 50 },
    ];
    const result = calculateDrawdown(data);
    result.forEach(d => {
      expect(d.drawdown).toBeLessThanOrEqual(0);
    });
  });

  it('handles all-zero data', () => {
    const data = [
      { date: '2026-01-01', cumulative_pnl: 0 },
      { date: '2026-01-02', cumulative_pnl: 0 },
    ];
    const result = calculateDrawdown(data);
    result.forEach(d => expect(d.drawdown).toBe(0));
  });

  it('handles missing cumulative_pnl', () => {
    const data = [{ date: '2026-01-01' }];
    const result = calculateDrawdown(data);
    expect(result[0].drawdown).toBe(0);
    expect(result[0].equity).toBe(0);
  });
});

describe('enrichWithCumulative (Analytics TradingActivity)', () => {
  it('adds cumulative trade count', () => {
    const data = [
      { date: '2026-01-01', trades: 3 },
      { date: '2026-01-02', trades: 5 },
      { date: '2026-01-03', trades: 2 },
    ];
    const result = enrichWithCumulative(data);
    expect(result[0].cumTrades).toBe(3);
    expect(result[1].cumTrades).toBe(8);
    expect(result[2].cumTrades).toBe(10);
  });

  it('handles missing trades as 0', () => {
    const data = [{ date: '2026-01-01' }];
    const result = enrichWithCumulative(data);
    expect(result[0].cumTrades).toBe(0);
  });
});
