import { useState } from 'react';
import ChartCard from '../components/ChartCard';
import { useChannels, useChannelDailyPnl } from '../hooks/useApi';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid, LineChart, Line, LabelList } from 'recharts';
import { PremiumTooltip } from '../charts/ChartPrimitives';

function ChannelCard({ ch, isSelected, onClick }) {
  const pnl = ch.total_pnl || 0;
  const wins = ch.wins || 0;
  const total = ch.total_trades || 0;
  const winRate = total > 0 ? ((wins / total) * 100).toFixed(1) : '0.0';

  return (
    <div
      className="card"
      onClick={onClick}
      style={{
        cursor: 'pointer',
        borderColor: isSelected ? 'var(--accent-blue)' : undefined,
        boxShadow: isSelected ? 'var(--shadow-glow)' : undefined,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{ch.channel_name || ch.channel_id}</span>
        <span className={`badge ${pnl >= 0 ? 'badge-profit' : 'badge-loss'}`}>
          {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
        </span>
      </div>

      {/* Win rate bar */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6875rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
          <span>Win Rate</span>
          <span>{winRate}%</span>
        </div>
        <div style={{ height: 4, borderRadius: 2, background: 'var(--accent-red-dim)', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${winRate}%`, background: 'var(--accent-green)', borderRadius: 2, transition: 'width 0.5s' }} />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
        <span>{total} trades</span>
        <span style={{ color: 'var(--accent-green)' }}>{wins} W</span>
        <span style={{ color: 'var(--accent-red)' }}>{ch.losses || 0} L</span>
      </div>
    </div>
  );
}

export default function Channels() {
  const { data: channels, isLoading } = useChannels();
  const [selected, setSelected] = useState(null);
  const { data: chDaily } = useChannelDailyPnl(selected, 30);

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Channels</h1>
        <p>Performance breakdown by signal source</p>
      </div>

      {/* Channel comparison bar */}
      <div className="full-width">
        <ChartCard title="Channel Comparison — Total PnL" loading={isLoading}>
          {channels && channels.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={channels} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="channel_name" tick={{ fill: '#94a3b8', fontSize: 11 }} width={120} axisLine={false} tickLine={false} />
                <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} />} />
                <Bar dataKey="total_pnl" name="Total PnL" radius={[0, 4, 4, 0]} animationDuration={600} maxBarSize={22}>
                  <LabelList dataKey="total_pnl" position="right" formatter={v => `$${v?.toFixed(1)}`} style={{ fill: '#94a3b8', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
                  {channels.map((ch, i) => (
                    <Cell key={i} fill={ch.total_pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No channel data</p>
          )}
        </ChartCard>
      </div>

      {/* Channel Cards Grid + Detail */}
      <div className="grid-main">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
          {(channels || []).map((ch) => (
            <ChannelCard
              key={ch.channel_id}
              ch={ch}
              isSelected={selected === ch.channel_id}
              onClick={() => setSelected(selected === ch.channel_id ? null : ch.channel_id)}
            />
          ))}
          {isLoading && [1, 2, 3].map(i => (
            <div key={i} className="card skeleton" style={{ height: 120 }} />
          ))}
        </div>

        {selected && (
          <ChartCard title={`Daily PnL — ${(channels || []).find(c => c.channel_id === selected)?.channel_name || selected}`}>
            {chDaily && chDaily.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chDaily} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={d => d?.slice(5)} axisLine={{ stroke: 'rgba(148,163,184,0.08)' }} tickLine={false} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} />
                  <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} />} />
                  <Line type="monotone" dataKey="pnl" name="PnL" stroke="#3b82f6" strokeWidth={2.5} dot={{ fill: '#3b82f6', r: 3, stroke: 'var(--bg-primary)', strokeWidth: 2 }} activeDot={{ r: 5, stroke: '#3b82f6', fill: 'var(--bg-primary)', strokeWidth: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>Select a channel to view details</p>
            )}
          </ChartCard>
        )}
      </div>
    </div>
  );
}
