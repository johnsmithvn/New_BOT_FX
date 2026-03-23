import { useState, useMemo, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, Eye, Trash2, ChevronLeft } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSignals, useSignalDetail, useChannelList, useSymbols } from '../hooks/useApi';
import { api } from '../api/client';
import { fmtCcy, buildChannelMap, resolveChannelName } from '../utils/format';
import ConfirmModal from '../components/ConfirmModal';

/* ─── Status badge colors ─────────────────────────────────── */
const STATUS_COLORS = {
  received:  { bg: 'rgba(59,130,246,0.12)', color: '#3b82f6' },
  parsed:    { bg: 'rgba(59,130,246,0.12)', color: '#3b82f6' },
  executed:  { bg: 'rgba(34,197,94,0.12)',  color: '#22c55e' },
  rejected:  { bg: 'rgba(245,158,11,0.12)', color: '#f59e0b' },
  failed:    { bg: 'rgba(239,68,68,0.12)',  color: '#ef4444' },
  duplicate: { bg: 'rgba(148,163,184,0.12)',color: '#94a3b8' },
};

/* ─── Event type labels ───────────────────────────────────── */
const EVENT_LABELS = {
  signal_received:               '📩 Signal received',
  signal_parsed:                 '🔍 Parsed signal',
  signal_parse_failed:           '❌ Parse failed',
  signal_rejected:               '🚫 Rejected',
  signal_executed:               '✅ Executed',
  signal_failed:                 '💥 Execution failed',
  edit_order_cancelled:          '✏️ Edit → Order cancelled',
  edit_group_pending_cancelled:  '✏️ Edit → Group cancelled',
  delete_signal_dry_run:         '🗑 Message deleted (dry run)',
  delete_order_cancelled:        '🗑 Delete → Order cancelled',
  delete_group_pending_cancelled:'🗑 Delete → Group cancelled',
  reply_executed:                '↩️ Reply executed',
};

/* ═══════════════════════════════════════════════════════════════
   SIGNAL DETAIL MODAL
   ═══════════════════════════════════════════════════════════════ */
function SignalDetailModal({ fingerprint, open, onClose, onDeleteOrder, channelMap }) {
  const { data, isLoading } = useSignalDetail(fingerprint);

  if (!open) return null;
  const sig = data?.signal;
  const orders = data?.orders || [];
  const trades = data?.trades || [];
  const events = data?.events || [];
  const group = data?.group;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          style={{ position: 'fixed', inset: 0, zIndex: 9998, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.94, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.94, opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={e => e.stopPropagation()}
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 16, padding: 0, maxWidth: 720, width: '95%', maxHeight: '85vh', overflow: 'auto', boxShadow: '0 24px 48px rgba(0,0,0,0.3)' }}
          >
            {isLoading ? (
              <div className="skeleton" style={{ height: 400, margin: 24 }} />
            ) : !sig ? (
              <p style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Signal not found</p>
            ) : (
              <>
                {/* Header */}
                <div style={{ padding: '1.5rem 1.5rem 1rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h2 style={{ margin: 0, fontSize: '1.125rem' }}>Signal Detail — {sig.symbol} {sig.side?.toUpperCase()}</h2>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{sig.fingerprint}</span>
                  </div>
                  <button onClick={onClose} className="btn btn-ghost" style={{ padding: '4px 8px' }}>✕</button>
                </div>

                <div style={{ padding: '1.25rem 1.5rem' }}>
                  {/* Raw text */}
                  <h3 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 8 }}>📝 Raw Signal Text</h3>
                  <pre style={{ background: 'var(--bg-tertiary)', padding: 16, borderRadius: 10, fontSize: '0.75rem', whiteSpace: 'pre-wrap', color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 20, border: '1px solid var(--border)', maxHeight: 200, overflow: 'auto' }}>
                    {sig.raw_text || '(no raw text stored)'}
                  </pre>

                  {/* Parsed result */}
                  <h3 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 8 }}>🔍 Parsed Result</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8, marginBottom: 20 }}>
                    {[
                      ['Symbol', sig.symbol],
                      ['Side', sig.side?.toUpperCase()],
                      ['Entry', sig.entry ?? '—'],
                      ['SL', sig.sl ?? '—'],
                      ['TP', Array.isArray(sig.tp) ? sig.tp.join(', ') : sig.tp || '—'],
                      ['Status', sig.status],
                      ['Channel', sig.channel_name || resolveChannelName(sig.source_chat_id, channelMap)],
                      ['Time', sig.received_at || sig.created_at],
                    ].map(([label, val]) => (
                      <div key={label} style={{ background: 'var(--bg-tertiary)', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: '0.625rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 600, fontFamily: typeof val === 'number' ? 'var(--font-mono)' : undefined }}>{String(val)}</div>
                      </div>
                    ))}
                  </div>

                  {/* Timeline */}
                  <h3 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 8 }}>📋 Timeline</h3>
                  <div style={{ borderLeft: '2px solid var(--border)', paddingLeft: 16, marginBottom: 20 }}>
                    {events.length ? events.map((ev, i) => (
                      <div key={i} style={{ marginBottom: 10, position: 'relative' }}>
                        <div style={{ position: 'absolute', left: -22, top: 4, width: 10, height: 10, borderRadius: '50%', background: ev.event_type?.includes('fail') || ev.event_type?.includes('reject') ? '#ef4444' : ev.event_type?.includes('execut') ? '#22c55e' : '#3b82f6', border: '2px solid var(--bg-secondary)' }} />
                        <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{ev.timestamp?.replace('T', ' ')}</div>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 500 }}>{EVENT_LABELS[ev.event_type] || ev.event_type}</div>
                        {ev.details && Object.keys(ev.details).length > 0 && (
                          <div style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                            {JSON.stringify(ev.details)}
                          </div>
                        )}
                      </div>
                    )) : <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No events recorded</p>}
                  </div>

                  {/* Orders table */}
                  <h3 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 8 }}>📋 Orders ({orders.length})</h3>
                  {orders.length > 0 && (
                    <div style={{ overflow: 'auto', marginBottom: 20 }}>
                      <table className="data-table" style={{ fontSize: '0.75rem' }}>
                        <thead><tr>
                          <th>Ticket</th><th>Kind</th><th>Price</th><th>SL</th><th>TP</th><th>Status</th><th></th>
                        </tr></thead>
                        <tbody>
                          {orders.map(o => (
                            <tr key={o.id}>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>{o.ticket || '—'}</td>
                              <td><span className={`badge ${o.order_kind?.includes('BUY') ? 'badge-buy' : 'badge-sell'}`}>{o.order_kind}</span></td>
                              <td>{o.price || '—'}</td>
                              <td>{o.sl || '—'}</td>
                              <td>{o.tp || '—'}</td>
                              <td>{o.success ? <span style={{ color: '#22c55e' }}>✅</span> : <span style={{ color: '#ef4444' }}>❌ {o.retcode}</span>}</td>
                              <td>
                                <button onClick={() => onDeleteOrder(o.id, o.ticket)} className="btn btn-ghost" style={{ padding: '2px 6px', color: 'var(--accent-red)', fontSize: '0.6875rem' }}>
                                  <Trash2 size={12} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Trade outcomes */}
                  <h3 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 8 }}>💰 Trade Outcomes ({trades.length})</h3>
                  {trades.length > 0 ? (
                    <div style={{ overflow: 'auto', marginBottom: 20 }}>
                      <table className="data-table" style={{ fontSize: '0.75rem' }}>
                        <thead><tr>
                          <th>Ticket</th><th>Close Price</th><th>Volume</th><th>PnL</th><th>Reason</th><th>Time</th>
                        </tr></thead>
                        <tbody>
                          {trades.map(t => (
                            <tr key={t.id}>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>{t.ticket}</td>
                              <td>{t.close_price}</td>
                              <td>{t.close_volume}</td>
                              <td style={{ color: t.pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{t.pnl?.toFixed(2)} $</td>
                              <td>{t.close_reason || '—'}</td>
                              <td style={{ fontSize: '0.6875rem' }}>{t.close_time?.replace('T', ' ')?.slice(0, 16)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 20 }}>No trades closed yet</p>}

                  {/* Group info */}
                  {group && (
                    <>
                      <h3 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 8 }}>🔗 Signal Group</h3>
                      <div style={{ background: 'var(--bg-tertiary)', padding: 12, borderRadius: 8, fontSize: '0.75rem', fontFamily: 'var(--font-mono)', border: '1px solid var(--border)', marginBottom: 20 }}>
                        <div>Status: <strong>{group.status}</strong></div>
                        <div>Tickets: {JSON.stringify(group.tickets)}</div>
                        <div>SL Mode: {group.sl_mode}</div>
                      </div>
                    </>
                  )}
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ═══════════════════════════════════════════════════════════════
   SIGNALS PAGE
   ═══════════════════════════════════════════════════════════════ */
export default function Signals() {
  const [filters, setFilters] = useState({ channel: '', symbol: '', status: '', from: '', to: '', page: 1, per_page: 20 });
  const { data, isLoading, refetch } = useSignals(filters);
  const { data: channelList } = useChannelList();
  const { data: symbolList } = useSymbols();
  const qc = useQueryClient();

  const signals = data?.signals || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / filters.per_page);

  const channelMap = useMemo(() => buildChannelMap(channelList), [channelList]);

  // Expandable rows
  const [expanded, setExpanded] = useState({});
  const toggle = useCallback((fp) => setExpanded(prev => ({ ...prev, [fp]: !prev[fp] })), []);

  // Detail modal
  const [detailFp, setDetailFp] = useState(null);

  // Confirm modal
  const [confirmState, setConfirmState] = useState({ open: false, title: '', message: '', onConfirm: null, confirmPhrase: '' });

  const update = (key, val) => setFilters(f => ({ ...f, [key]: val, page: 1 }));

  // ── Delete handlers ──────────────────────────────────────────
  const handleDeleteSignal = (fp) => {
    setConfirmState({
      open: true,
      title: 'Delete Signal & All Data',
      message: `This will permanently delete this signal and ALL related orders, trades, events, and groups. This cannot be undone.`,
      confirmText: 'Delete All',
      confirmPhrase: 'DELETE',
      onConfirm: async () => {
        await api.deleteSignal(fp);
        setDetailFp(null);
        qc.invalidateQueries({ queryKey: ['signals'] });
        qc.invalidateQueries({ queryKey: ['overview'] });
        qc.invalidateQueries({ queryKey: ['trades'] });
        refetch();
      },
    });
  };

  const handleDeleteOrder = (orderId, ticket) => {
    setConfirmState({
      open: true,
      title: 'Delete Order',
      message: `Delete order #${ticket || orderId}? Related trades will also be removed.`,
      confirmText: 'Delete',
      onConfirm: async () => {
        await api.deleteOrder(orderId);
        qc.invalidateQueries({ queryKey: ['signal-detail'] });
        qc.invalidateQueries({ queryKey: ['overview'] });
        qc.invalidateQueries({ queryKey: ['trades'] });
      },
    });
  };

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Signal Lifecycle</h1>
        <p>Full signal history — from Telegram to close</p>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          <select className="select" value={filters.channel} onChange={e => update('channel', e.target.value)}>
            <option value="">All Channels</option>
            {(channelList || []).map(c => <option key={c.id} value={c.id}>{c.name || c.id}</option>)}
          </select>
          <select className="select" value={filters.symbol} onChange={e => update('symbol', e.target.value)}>
            <option value="">All Symbols</option>
            {(symbolList || []).map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="select" value={filters.status} onChange={e => update('status', e.target.value)}>
            <option value="">All Status</option>
            <option value="executed">Executed</option>
            <option value="rejected">Rejected</option>
            <option value="failed">Failed</option>
            <option value="received">Received</option>
            <option value="duplicate">Duplicate</option>
          </select>
          <input type="date" className="input" value={filters.from} onChange={e => update('from', e.target.value)} />
          <input type="date" className="input" value={filters.to} onChange={e => update('to', e.target.value)} />
        </div>
      </div>

      {/* Summary */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '0.75rem 1.25rem' }}>
        <span className="text-muted" style={{ fontSize: '0.8125rem' }}>{total} signals</span>
      </div>

      {/* Signal Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div className="skeleton" style={{ height: 400 }} />
        ) : (
          <div style={{ overflow: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 30 }}></th>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Status</th>
                  <th>Orders</th>
                  <th>PnL</th>
                  <th>Channel</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {signals.map(s => {
                  const isOpen = expanded[s.fingerprint];
                  const sc = STATUS_COLORS[s.status] || STATUS_COLORS.received;
                  return (
                    <SignalRow
                      key={s.id}
                      s={s}
                      isOpen={isOpen}
                      toggle={() => toggle(s.fingerprint)}
                      onDetail={() => setDetailFp(s.fingerprint)}
                      onDelete={() => handleDeleteSignal(s.fingerprint)}
                      channelMap={channelMap}
                      sc={sc}
                    />
                  );
                })}
                {!signals.length && (
                  <tr><td colSpan={9} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No signals found</td></tr>
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

      {/* Detail Modal */}
      <SignalDetailModal
        fingerprint={detailFp}
        open={!!detailFp}
        onClose={() => setDetailFp(null)}
        onDeleteOrder={handleDeleteOrder}
        channelMap={channelMap}
      />

      {/* Confirm Modal */}
      <ConfirmModal
        open={confirmState.open}
        onClose={() => setConfirmState(s => ({ ...s, open: false }))}
        onConfirm={confirmState.onConfirm}
        title={confirmState.title}
        message={confirmState.message}
        confirmText={confirmState.confirmText || 'Confirm'}
        confirmPhrase={confirmState.confirmPhrase || ''}
        level="danger"
      />
    </div>
  );
}

/* ─── Signal Row (expandable) ─────────────────────────────────── */
function SignalRow({ s, isOpen, toggle, onDetail, onDelete, channelMap, sc }) {
  const { data: detail } = useSignalDetail(isOpen ? s.fingerprint : null);
  const orders = detail?.orders || [];

  return (
    <>
      <tr style={{ cursor: 'pointer' }} onClick={toggle}>
        <td style={{ textAlign: 'center', padding: '0 4px' }}>
          {s.order_count > 0 ? (isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : <span style={{ width: 14, display: 'inline-block' }} />}
        </td>
        <td style={{ fontSize: '0.75rem', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>{(s.received_at || s.created_at)?.replace('T', ' ')?.slice(0, 16)}</td>
        <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.symbol}</td>
        <td><span className={`badge badge-${s.side?.toLowerCase() === 'buy' ? 'buy' : 'sell'}`}>{s.side?.toUpperCase()}</span></td>
        <td>
          <span style={{ background: sc.bg, color: sc.color, padding: '2px 10px', borderRadius: 12, fontSize: '0.6875rem', fontWeight: 600 }}>
            {s.status}
          </span>
        </td>
        <td style={{ textAlign: 'center' }}>{s.order_count} / {s.success_count}</td>
        <td style={{ color: s.total_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
          {s.trade_count > 0 ? `${s.total_pnl?.toFixed(2)} $` : '—'}
        </td>
        <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          {s.channel_name || resolveChannelName(s.source_chat_id, channelMap)}
        </td>
        <td onClick={e => e.stopPropagation()}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button onClick={onDetail} className="btn btn-ghost" style={{ padding: '3px 6px' }} title="View details">
              <Eye size={14} />
            </button>
            <button onClick={onDelete} className="btn btn-ghost" style={{ padding: '3px 6px', color: 'var(--accent-red)' }} title="Delete signal">
              <Trash2 size={14} />
            </button>
          </div>
        </td>
      </tr>
      {/* Expanded orders */}
      {isOpen && orders.map(o => (
        <tr key={`order-${o.id}`} style={{ background: 'rgba(59,130,246,0.03)' }}>
          <td></td>
          <td style={{ fontSize: '0.6875rem', paddingLeft: 20, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
            └─ #{o.ticket || '—'}
          </td>
          <td style={{ fontSize: '0.6875rem' }}>{o.order_kind}</td>
          <td style={{ fontSize: '0.6875rem' }}>{o.price || '—'}</td>
          <td style={{ fontSize: '0.6875rem' }}>
            {o.success ? <span style={{ color: '#22c55e' }}>✅</span> : <span style={{ color: '#ef4444' }}>❌</span>}
          </td>
          <td colSpan={3} style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            SL: {o.sl || '—'} | TP: {o.tp || '—'}
          </td>
          <td></td>
        </tr>
      ))}
    </>
  );
}
