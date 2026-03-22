import { useState, useMemo } from 'react';
import { DollarSign, TrendingUp, BarChart3, Activity } from 'lucide-react';
import StatCard from '../components/StatCard';
import ChartCard from '../components/ChartCard';
import EquityCurve from '../charts/EquityCurve';
import DailyPnlBars from '../charts/DailyPnlBars';
import WinLossDonut from '../charts/WinLossDonut';
import { useOverview, useDailyPnl, useEquityCurve, useChannels, useActive } from '../hooks/useApi';
import {
  ComposedChart, BarChart, Bar, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, CartesianGrid, LabelList, Legend,
} from 'recharts';
import { PremiumTooltip } from '../charts/ChartPrimitives';

function fmt(n, prefix = '$') {
  if (n == null) return `${prefix}0.00`;
  const abs = Math.abs(n);
  const str = abs >= 1000 ? `${(abs / 1000).toFixed(1)}k` : abs.toFixed(2);
  return `${n < 0 ? '-' : ''}${prefix}${str}`;
}

/** Combo Chart: Daily PnL bars + cumulative line overlay */
function ComboPnlChart({ dailyData = [], equityData = [] }) {
  // Merge daily PnL with cumulative equity by date
  const merged = useMemo(() => {
    const eqMap = {};
    (equityData || []).forEach(d => { eqMap[d.date] = d.cumulative_pnl; });
    return (dailyData || []).map(d => ({
      ...d,
      cumulative: eqMap[d.date] ?? null,
    }));
  }, [dailyData, equityData]);

  if (!merged.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={merged} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="comboCumGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={{ stroke: 'rgba(148,163,184,0.08)' }}
          tickLine={false}
          tickFormatter={(d) => d?.slice(5)}
        />
        <YAxis
          yAxisId="bar"
          tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false} tickLine={false}
          tickFormatter={(v) => `$${v}`}
          width={55}
        />
        <YAxis
          yAxisId="line" orientation="right"
          tick={{ fill: '#8b5cf6', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false} tickLine={false}
          tickFormatter={(v) => `$${v}`}
          width={55}
        />
        <Tooltip content={
          <PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} />
        } />
        <Legend
          wrapperStyle={{ fontSize: '0.6875rem', color: '#94a3b8' }}
          iconType="circle"
          iconSize={8}
        />
        <Bar yAxisId="bar" dataKey="net_pnl" name="Daily PnL" radius={[3, 3, 0, 0]} maxBarSize={30}>
          {merged.map((entry, i) => (
            <Cell key={i} fill={entry.net_pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
          ))}
        </Bar>
        <Line
          yAxisId="line"
          type="monotone"
          dataKey="cumulative"
          name="Cumulative PnL"
          stroke="#8b5cf6"
          strokeWidth={2.5}
          dot={false}
          activeDot={{ r: 4, fill: '#8b5cf6', stroke: 'var(--bg-primary)', strokeWidth: 2 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/** Top Channels — horizontal bars with labels */
function TopChannelsBars({ channels = [] }) {
  if (!channels.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No channel data</p>;

  const sorted = [...channels].sort((a, b) => (b.total_pnl || 0) - (a.total_pnl || 0)).slice(0, 8);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={sorted} layout="vertical" margin={{ top: 5, right: 50, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" horizontal={false} />
        <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
        <YAxis type="category" dataKey="channel_name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} width={100} />
        <Tooltip content={<PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} />} />
        <Bar dataKey="total_pnl" name="Total PnL" radius={[0, 4, 4, 0]} animationDuration={800} maxBarSize={22}>
          <LabelList
            dataKey="total_pnl"
            position="right"
            formatter={(v) => `$${v?.toFixed(1)}`}
            style={{ fill: '#94a3b8', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
          />
          {sorted.map((ch, i) => (
            <Cell key={i} fill={ch.total_pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
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

      {/* ── Combo Chart: Daily PnL bars + Cumulative line overlay (full width) */}
      <div className="full-width">
        <ChartCard
          title="Daily PnL + Cumulative Trend"
          loading={dpLoading || eqLoading}
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
          <ComboPnlChart dailyData={dailyPnl} equityData={equity} />
        </ChartCard>
      </div>

      {/* ── Win/Loss Donut + Top Channels ───────────────────────── */}
      <div className="grid-main">
        <ChartCard title="Top Channels" loading={chLoading}>
          <TopChannelsBars channels={channels} />
        </ChartCard>
        <ChartCard title="Win / Loss Ratio" loading={ovLoading}>
          <WinLossDonut wins={ov.wins || 0} losses={ov.losses || 0} />
        </ChartCard>
      </div>

      {/* ── Active Positions ────────────────────────────────────── */}
      <div className="full-width">
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
