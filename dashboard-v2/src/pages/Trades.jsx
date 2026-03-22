import { useState, useMemo } from 'react';
import { Download, ChevronLeft, ChevronRight } from 'lucide-react';
import ChartCard from '../components/ChartCard';
import { useTrades, useChannelList, useSymbols } from '../hooks/useApi';
import { api } from '../api/client';
import { fmtCcy, buildChannelMap, resolveChannelName } from '../utils/format';

export default function Trades() {
  const [filters, setFilters] = useState({
    channel: '', symbol: '', from: '', to: '', outcome: '', page: 1, per_page: 20,
  });

  const { data, isLoading } = useTrades(filters);
  const { data: channelList } = useChannelList();
  const { data: symbolList } = useSymbols();

  const trades = data?.trades || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / filters.per_page);

  // Build channel name lookup map
  const channelMap = useMemo(() => buildChannelMap(channelList), [channelList]);

  const update = (key, val) => setFilters(f => ({ ...f, [key]: val, page: 1 }));

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Trade Journal</h1>
        <p>Full trade history with advanced filtering</p>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          <select className="select" value={filters.channel} onChange={e => update('channel', e.target.value)}>
            <option value="">All Channels</option>
            {(channelList || []).map(c => (
              <option key={c.id} value={c.id}>{c.name || c.id}</option>
            ))}
          </select>

          <select className="select" value={filters.symbol} onChange={e => update('symbol', e.target.value)}>
            <option value="">All Symbols</option>
            {(symbolList || []).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <input type="date" className="input" value={filters.from} onChange={e => update('from', e.target.value)} />
          <input type="date" className="input" value={filters.to} onChange={e => update('to', e.target.value)} />

          <select className="select" value={filters.outcome} onChange={e => update('outcome', e.target.value)}>
            <option value="">All Outcomes</option>
            <option value="win">Wins</option>
            <option value="loss">Losses</option>
          </select>

          <button
            className="btn btn-primary"
            onClick={() => window.open(api.exportCsvUrl(filters), '_blank')}
          >
            <Download size={14} /> CSV
          </button>
        </div>
      </div>

      {/* Summary Bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '0.75rem 1.25rem' }}>
        <div style={{ display: 'flex', gap: '2rem', fontSize: '0.8125rem' }}>
          <span className="text-muted">{total} trades</span>
          <span>
            Total: <span style={{ color: (data?.total_pnl || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
              {fmtCcy(data?.total_pnl)}
            </span>
          </span>
          <span>
            Avg: <span style={{ color: (data?.avg_pnl || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
              {fmtCcy(data?.avg_pnl)}
            </span>
          </span>
        </div>
      </div>

      {/* Trade Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div className="skeleton" style={{ height: 400 }} />
        ) : (
          <div style={{ overflow: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Entry</th>
                  <th>Close</th>
                  <th>Volume</th>
                  <th>PnL</th>
                  <th>Commission</th>
                  <th>Channel</th>
                  <th>Ticket</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>{t.close_time?.replace('T', ' ')?.slice(0, 16)}</td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.symbol || '—'}</td>
                    <td>
                      <span className={`badge badge-${t.side?.toLowerCase() === 'buy' ? 'buy' : 'sell'}`}>
                        {t.side || '—'}
                      </span>
                    </td>
                    <td>{t.entry_price || '—'}</td>
                    <td>{t.close_price}</td>
                    <td>{t.close_volume}</td>
                    <td style={{ color: t.pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', fontWeight: 600 }}>
                      {t.pnl >= 0 ? '+' : ''}{t.pnl?.toFixed(2)} $
                    </td>
                    <td>{t.commission?.toFixed(2)} $</td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {resolveChannelName(t.channel_id, channelMap)}
                    </td>
                    <td style={{ fontSize: '0.75rem' }}>{t.ticket}</td>
                  </tr>
                ))}
                {!trades.length && (
                  <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No trades found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, padding: '1rem', borderTop: '1px solid var(--border)' }}>
            <button className="btn btn-ghost" disabled={filters.page <= 1} onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>
              <ChevronLeft size={16} />
            </button>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Page {filters.page} / {totalPages}
            </span>
            <button className="btn btn-ghost" disabled={filters.page >= totalPages} onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
