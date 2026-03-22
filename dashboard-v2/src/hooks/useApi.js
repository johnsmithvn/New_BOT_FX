/**
 * TanStack Query hooks for all API endpoints.
 * Auto-refetch every 30s by default.
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

const REFETCH = 30_000; // 30 seconds

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: api.overview,
    refetchInterval: REFETCH,
  });
}

export function useDailyPnl(days = 30) {
  return useQuery({
    queryKey: ['daily-pnl', days],
    queryFn: () => api.dailyPnl(days),
    refetchInterval: REFETCH,
  });
}

export function useChannels() {
  return useQuery({
    queryKey: ['channels'],
    queryFn: api.channels,
    refetchInterval: REFETCH,
  });
}

export function useChannelDailyPnl(id, days = 30) {
  return useQuery({
    queryKey: ['channel-daily-pnl', id, days],
    queryFn: () => api.channelDailyPnl(id, days),
    enabled: !!id,
    refetchInterval: REFETCH,
  });
}

export function useTrades(params = {}) {
  return useQuery({
    queryKey: ['trades', params],
    queryFn: () => api.trades(params),
    refetchInterval: REFETCH,
  });
}

export function useActive() {
  return useQuery({
    queryKey: ['active'],
    queryFn: api.active,
    refetchInterval: REFETCH,
  });
}

export function useEquityCurve(days = 365) {
  return useQuery({
    queryKey: ['equity-curve', days],
    queryFn: () => api.equityCurve(days),
    refetchInterval: REFETCH,
  });
}

export function useSymbolStats() {
  return useQuery({
    queryKey: ['symbol-stats'],
    queryFn: api.symbolStats,
    refetchInterval: REFETCH,
  });
}

export function useSymbols() {
  return useQuery({
    queryKey: ['symbols'],
    queryFn: api.symbols,
  });
}

export function useChannelList() {
  return useQuery({
    queryKey: ['channel-list'],
    queryFn: api.channelList,
  });
}

export function usePnlHeatmap(days = 365) {
  return useQuery({
    queryKey: ['pnl-heatmap', days],
    queryFn: () => api.pnlHeatmap(days),
    refetchInterval: 60_000,
  });
}

export function useDrawdown(days = 365) {
  return useQuery({
    queryKey: ['drawdown', days],
    queryFn: () => api.drawdown(days),
    refetchInterval: 60_000,
  });
}

export function usePnlDistribution() {
  return useQuery({
    queryKey: ['pnl-distribution'],
    queryFn: api.pnlDistribution,
    refetchInterval: 60_000,
  });
}
