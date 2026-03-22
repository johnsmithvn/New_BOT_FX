import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api } from '../../src/api/client.js';

/* ─── Module-level mocks must be set before importing ───── */
beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

/* ─── fetchApi internal behavior (tested through api methods) ─── */
describe('api methods — URL construction', () => {
  it('api.overview calls /api/overview', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ net_pnl: 100 }),
    });
    globalThis.fetch = mockFetch;

    await api.overview();

    expect(mockFetch).toHaveBeenCalledOnce();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toBe('/api/overview');
  });

  it('api.dailyPnl passes days param', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    });
    globalThis.fetch = mockFetch;

    await api.dailyPnl(7);

    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/daily-pnl');
    expect(url).toContain('days=7');
  });

  it('api.trades passes multiple params, skips empty', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ trades: [] }),
    });
    globalThis.fetch = mockFetch;

    await api.trades({ channel: '123', symbol: '', page: 2 });

    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('channel=123');
    expect(url).toContain('page=2');
    expect(url).not.toContain('symbol=');
  });

  it('api.channelDailyPnl includes channel id in path', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    });
    globalThis.fetch = mockFetch;

    await api.channelDailyPnl('abc123', 14);

    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/channels/abc123/daily-pnl');
    expect(url).toContain('days=14');
  });

  it('api.signalDetail encodes fingerprint in URL', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    globalThis.fetch = mockFetch;

    await api.signalDetail('abc:123');

    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/signals/abc%3A123');
  });
});

/* ─── Error handling ──────────────────────────────────────── */
describe('api — error handling', () => {
  it('throws on non-OK response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    await expect(api.overview()).rejects.toThrow('API 500');
  });
});

/* ─── API Key header ──────────────────────────────────────── */
describe('api — API key', () => {
  it('sends X-API-Key header when set in localStorage', async () => {
    localStorage.setItem('dashboard_api_key', 'my-secret-key');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    globalThis.fetch = mockFetch;

    await api.channels();

    const opts = mockFetch.mock.calls[0][1];
    expect(opts.headers['X-API-Key']).toBe('my-secret-key');
  });

  it('does not send X-API-Key when not set', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    globalThis.fetch = mockFetch;

    await api.channels();

    const opts = mockFetch.mock.calls[0][1];
    expect(opts.headers['X-API-Key']).toBeUndefined();
  });
});

/* ─── DELETE methods ──────────────────────────────────────── */
describe('api — DELETE methods', () => {
  it('api.deleteSignal sends DELETE method', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    });
    globalThis.fetch = mockFetch;

    await api.deleteSignal('fp123');

    const opts = mockFetch.mock.calls[0][1];
    expect(opts.method).toBe('DELETE');
  });

  it('api.clearAll sends DELETE to /api/data/all', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    });
    globalThis.fetch = mockFetch;

    await api.clearAll();

    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/data/all');
    expect(mockFetch.mock.calls[0][1].method).toBe('DELETE');
  });
});

/* ─── exportCsvUrl (synchronous) ──────────────────────────── */
describe('api.exportCsvUrl', () => {
  it('builds URL with params', () => {
    const url = api.exportCsvUrl({ channel: 'ch1', from: '2026-01-01' });
    expect(url).toBe('/api/export/csv?channel=ch1&from=2026-01-01');
  });

  it('returns base URL when no params', () => {
    const url = api.exportCsvUrl({});
    expect(url).toBe('/api/export/csv');
  });
});
