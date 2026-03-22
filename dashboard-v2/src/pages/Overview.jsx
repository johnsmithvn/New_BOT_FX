import { useState } from 'react';
import { DollarSign, TrendingUp, BarChart3, Activity } from 'lucide-react';
import StatCard from '../components/StatCard';
import ChartCard from '../components/ChartCard';
import EquityCurve from '../charts/EquityCurve';
import DailyPnlBars from '../charts/DailyPnlBars';
import WinLossDonut from '../charts/WinLossDonut';
import { useOverview, useDailyPnl, useEquityCurve, useChannels, useActive } from '../hooks/useApi';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

function fmt(n, prefix = '$') {
  if (n == null) return `${prefix}0.00`;
  const abs = Math.abs(n);
  const str = abs >= 1000 ? `${(abs / 1000).toFixed(1)}k` : abs.toFixed(2);
  return `${n < 0 ? '-' : ''}${prefix}${str}`;
}

export default function Overview() {
  const { data: overview, isLoading: ovLoading } = useOverview();
  const [pnlDays, setPnlDays] = useState(30);
  const { data: dailyPnl, isLoading: dpLoading } = useDailyPnl(pnlDays);
  const { data: equity, isLoading: eqLoading } = useEquityCurve(365);
  const { data: channels, isLoading: chLoading } = useChannels();
  const { data: active } = useActive();

  const ov = overview || {};

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Dashboard Overview</h1>
        <p>Real-time trading performance at a glance</p>
      </div>

      {/* ── Stat Cards ──────────────────────────────────────────── */}
      <div className="grid-stats">
        <StatCard
          icon={DollarSign}
          label="Net PnL"
          value={ovLoading ? '...' : fmt(ov.net_pnl)}
          color={ov.net_pnl >= 0 ? 'green' : 'red'}
          delay={0}
        />
        <StatCard
          icon={TrendingUp}
          label="Win Rate"
          value={ovLoading ? '...' : `${ov.win_rate || 0}%`}
          color="blue"
          delay={1}
        />
        <StatCard
          icon={BarChart3}
          label="Total Trades"
          value={ovLoading ? '...' : String(ov.total_trades || 0)}
          color="purple"
          delay={2}
        />
        <StatCard
          icon={Activity}
          label="Active Positions"
          value={ovLoading ? '...' : String(ov.active_groups || 0)}
          color="amber"
          delay={3}
        />
      </div>

      {/* ── Equity Curve (full width) ───────────────────────────── */}
      <div className="full-width">
        <ChartCard title="Equity Curve" loading={eqLoading}>
          <EquityCurve data={equity} />
        </ChartCard>
      </div>

      {/* ── Daily PnL + Win/Loss Donut ──────────────────────────── */}
      <div className="grid-main">
        <ChartCard
          title="Daily PnL"
          loading={dpLoading}
          actions={
            <>
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  className={`btn btn-ghost${pnlDays === d ? ' active' : ''}`}
                  onClick={() => setPnlDays(d)}
                  style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                >
                  {d}D
                </button>
              ))}
            </>
          }
        >
          <DailyPnlBars data={dailyPnl} />
        </ChartCard>

        <ChartCard title="Win / Loss Ratio" loading={ovLoading}>
          <WinLossDonut wins={ov.wins || 0} losses={ov.losses || 0} />
        </ChartCard>
      </div>

      {/* ── Top Channels + Active Positions ─────────────────────── */}
      <div className="grid-2">
        <ChartCard title="Top Channels" loading={chLoading}>
          {channels && channels.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={channels.slice(0, 6)}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
              >
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
                <YAxis
                  type="category"
                  dataKey="channel_name"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={100}
                />
                <Tooltip
                  formatter={(v) => [`$${v?.toFixed(2)}`, 'PnL']}
                  contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                />
                <Bar dataKey="total_pnl" radius={[0, 4, 4, 0]} animationDuration={600}>
                  {channels.slice(0, 6).map((ch, i) => (
                    <Cell key={i} fill={ch.total_pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No channel data</p>
          )}
        </ChartCard>

        <ChartCard title="Active Positions" loading={false}>
          {active && active.length > 0 ? (
            <div style={{ overflow: 'auto', maxHeight: 260 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Tickets</th>
                  </tr>
                </thead>
                <tbody>
                  {active.map((pos, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{pos.symbol}</td>
                      <td>
                        <span className={`badge badge-${pos.side?.toLowerCase() === 'buy' ? 'buy' : 'sell'}`}>
                          {pos.side}
                        </span>
                      </td>
                      <td>{pos.tickets?.length || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No active positions</p>
          )}
        </ChartCard>
      </div>
    </div>
  );
}
