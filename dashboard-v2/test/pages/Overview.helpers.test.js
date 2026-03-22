/**
 * Tests for data transformation functions used in Overview.jsx.
 *
 * Imports the PRODUCTION helpers (single source of truth).
 */
import { describe, it, expect } from 'vitest';
import {
  aggregateByWeekday,
  mergeDailyAndEquity,
  aggregateMonthly,
} from '../../src/pages/Overview.helpers';

describe('aggregateByWeekday (Overview PnlByWeekday)', () => {
  it('aggregates PnL by weekday', () => {
    const data = [
      { date: '2026-03-16', net_pnl: 50 },  // Monday
      { date: '2026-03-17', net_pnl: -30 }, // Tuesday
      { date: '2026-03-18', net_pnl: 20 },  // Wednesday
    ];
    const result = aggregateByWeekday(data);
    expect(result).toHaveLength(5);
    expect(result[0].day).toBe('Mon');
    expect(result[0].pnl).toBe(50);
    expect(result[1].day).toBe('Tue');
    expect(result[1].pnl).toBe(-30);
    expect(result[2].pnl).toBe(20);
  });

  it('returns zeros for empty data', () => {
    const result = aggregateByWeekday([]);
    expect(result).toHaveLength(5);
    result.forEach(d => {
      expect(d.pnl).toBe(0);
      expect(d.count).toBe(0);
    });
  });

  it('skips entries without date', () => {
    const data = [
      { net_pnl: 100 },
      { date: '2026-03-16', net_pnl: 50 },
    ];
    const result = aggregateByWeekday(data);
    const totalCount = result.reduce((s, d) => s + d.count, 0);
    expect(totalCount).toBe(1);
  });

  it('accumulates multiple entries for same weekday', () => {
    const data = [
      { date: '2026-03-16', net_pnl: 30 },  // Mon
      { date: '2026-03-23', net_pnl: 70 },  // Mon (next week)
    ];
    const result = aggregateByWeekday(data);
    expect(result[0].pnl).toBe(100);
    expect(result[0].count).toBe(2);
  });
});

describe('mergeDailyAndEquity (Overview ComboPnlChart)', () => {
  it('merges daily and equity data by date', () => {
    const daily = [
      { date: '2026-03-01', net_pnl: 10 },
      { date: '2026-03-02', net_pnl: -5 },
    ];
    const equity = [
      { date: '2026-03-01', cumulative_pnl: 10 },
      { date: '2026-03-02', cumulative_pnl: 5 },
    ];
    const result = mergeDailyAndEquity(daily, equity);
    expect(result[0].cumulative).toBe(10);
    expect(result[1].cumulative).toBe(5);
  });

  it('returns null cumulative for unmatched dates', () => {
    const daily = [{ date: '2026-03-01', net_pnl: 10 }];
    const equity = [{ date: '2026-03-02', cumulative_pnl: 20 }];
    const result = mergeDailyAndEquity(daily, equity);
    expect(result[0].cumulative).toBeNull();
  });

  it('handles null inputs', () => {
    expect(mergeDailyAndEquity(null, null)).toEqual([]);
    expect(mergeDailyAndEquity([], null)).toEqual([]);
  });
});

describe('aggregateMonthly (Overview MonthlyWinLossGrouped)', () => {
  it('groups daily data by month', () => {
    const data = [
      { date: '2026-01-05', net_pnl: 100 },
      { date: '2026-01-15', net_pnl: -30 },
      { date: '2026-02-10', net_pnl: 50 },
    ];
    const result = aggregateMonthly(data);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ month: '2026-01', wins: 100, losses: 30 });
    expect(result[1]).toEqual({ month: '2026-02', wins: 50, losses: 0 });
  });

  it('returns empty for empty data', () => {
    expect(aggregateMonthly([])).toEqual([]);
  });

  it('limits to last 6 months', () => {
    const data = [];
    for (let m = 1; m <= 8; m++) {
      data.push({ date: `2026-${String(m).padStart(2, '0')}-01`, net_pnl: 10 });
    }
    const result = aggregateMonthly(data);
    expect(result).toHaveLength(6);
    expect(result[0].month).toBe('2026-03');
  });
});
