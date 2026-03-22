import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock the api client
vi.mock('../../src/api/client', () => ({
  api: {
    overview: vi.fn().mockResolvedValue({ net_pnl: 100 }),
    dailyPnl: vi.fn().mockResolvedValue([]),
    channels: vi.fn().mockResolvedValue([]),
    channelDailyPnl: vi.fn().mockResolvedValue([]),
    trades: vi.fn().mockResolvedValue({ trades: [] }),
    active: vi.fn().mockResolvedValue([]),
    equityCurve: vi.fn().mockResolvedValue([]),
    symbolStats: vi.fn().mockResolvedValue([]),
    symbols: vi.fn().mockResolvedValue([]),
    channelList: vi.fn().mockResolvedValue([]),
    pnlHeatmap: vi.fn().mockResolvedValue([]),
    drawdown: vi.fn().mockResolvedValue([]),
    pnlDistribution: vi.fn().mockResolvedValue([]),
    signals: vi.fn().mockResolvedValue({ signals: [] }),
    signalDetail: vi.fn().mockResolvedValue({}),
    tableCounts: vi.fn().mockResolvedValue({}),
    signalStatusCounts: vi.fn().mockResolvedValue({}),
  },
}));

import {
  useOverview,
  useDailyPnl,
  useChannels,
  useChannelDailyPnl,
  useTrades,
  useActive,
  useEquityCurve,
  useSymbolStats,
  useSymbols,
  useChannelList,
  usePnlHeatmap,
  useDrawdown,
  usePnlDistribution,
  useSignals,
  useSignalDetail,
  useTableCounts,
  useSignalStatusCounts,
} from '../../src/hooks/useApi';
import { api } from '../../src/api/client';

/* ─── Test wrapper ────────────────────────────────────────── */
function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

/* ─── Hook tests ──────────────────────────────────────────── */
describe('useOverview', () => {
  it('calls api.overview and returns data', async () => {
    const { result } = renderHook(() => useOverview(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.overview).toHaveBeenCalledOnce();
    expect(result.current.data).toEqual({ net_pnl: 100 });
  });
});

describe('useDailyPnl', () => {
  it('passes days parameter to api.dailyPnl', async () => {
    const { result } = renderHook(() => useDailyPnl(7), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.dailyPnl).toHaveBeenCalledWith(7);
  });

  it('defaults to 30 days', async () => {
    const { result } = renderHook(() => useDailyPnl(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.dailyPnl).toHaveBeenCalledWith(30);
  });
});

describe('useChannels', () => {
  it('calls api.channels', async () => {
    const { result } = renderHook(() => useChannels(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.channels).toHaveBeenCalledOnce();
  });
});

describe('useChannelDailyPnl', () => {
  it('is disabled when id is falsy', () => {
    const { result } = renderHook(() => useChannelDailyPnl(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('calls api when id is provided', async () => {
    const { result } = renderHook(() => useChannelDailyPnl('ch1', 14), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.channelDailyPnl).toHaveBeenCalledWith('ch1', 14);
  });
});

describe('useTrades', () => {
  it('passes params to api.trades', async () => {
    const params = { channel: '123', page: 2 };
    const { result } = renderHook(() => useTrades(params), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.trades).toHaveBeenCalledWith(params);
  });
});

describe('useActive', () => {
  it('calls api.active', async () => {
    const { result } = renderHook(() => useActive(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.active).toHaveBeenCalledOnce();
  });
});

describe('useEquityCurve', () => {
  it('defaults to 365 days', async () => {
    const { result } = renderHook(() => useEquityCurve(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.equityCurve).toHaveBeenCalledWith(365);
  });
});

describe('useSymbolStats', () => {
  it('calls api.symbolStats', async () => {
    const { result } = renderHook(() => useSymbolStats(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.symbolStats).toHaveBeenCalledOnce();
  });
});

describe('useSymbols', () => {
  it('calls api.symbols (no refetch interval)', async () => {
    const { result } = renderHook(() => useSymbols(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.symbols).toHaveBeenCalledOnce();
  });
});

describe('useChannelList', () => {
  it('calls api.channelList', async () => {
    const { result } = renderHook(() => useChannelList(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.channelList).toHaveBeenCalledOnce();
  });
});

describe('usePnlHeatmap', () => {
  it('passes days to api.pnlHeatmap', async () => {
    const { result } = renderHook(() => usePnlHeatmap(90), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.pnlHeatmap).toHaveBeenCalledWith(90);
  });
});

describe('useDrawdown', () => {
  it('passes days to api.drawdown', async () => {
    const { result } = renderHook(() => useDrawdown(180), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.drawdown).toHaveBeenCalledWith(180);
  });
});

describe('usePnlDistribution', () => {
  it('calls api.pnlDistribution', async () => {
    const { result } = renderHook(() => usePnlDistribution(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.pnlDistribution).toHaveBeenCalledOnce();
  });
});

describe('useSignals', () => {
  it('passes params to api.signals', async () => {
    const params = { status: 'executed', page: 1 };
    const { result } = renderHook(() => useSignals(params), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.signals).toHaveBeenCalledWith(params);
  });
});

describe('useSignalDetail', () => {
  it('is disabled when fingerprint is falsy', () => {
    const { result } = renderHook(() => useSignalDetail(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('calls api when fingerprint is provided', async () => {
    const { result } = renderHook(() => useSignalDetail('fp123'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.signalDetail).toHaveBeenCalledWith('fp123');
  });
});

describe('useTableCounts', () => {
  it('calls api.tableCounts', async () => {
    const { result } = renderHook(() => useTableCounts(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.tableCounts).toHaveBeenCalledOnce();
  });
});

describe('useSignalStatusCounts', () => {
  it('calls api.signalStatusCounts', async () => {
    const { result } = renderHook(() => useSignalStatusCounts(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.signalStatusCounts).toHaveBeenCalledOnce();
  });
});
