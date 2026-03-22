import { useState, useMemo } from 'react';
import ChartCard from '../components/ChartCard';
import SparkCard from '../components/SparkCard';
import EquityCurve from '../charts/EquityCurve';
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
  const str = abs >= 1000 ? `${(abs / 1000).toFixed(1)}K` : abs.toFixed(2);
  return `${n < 0 ? '-' : ''}${prefix}${str}`;
}

/** Combo Chart: Daily PnL bars + cumulative line overlay */
function ComboPnlChart({ dailyData = [], equityData = [] }) {
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
        <Tooltip cursor={false} content={
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

/** Monthly Wins vs Losses grouped bar chart (cashflow style) */
function MonthlyWinLossGrouped({ data = [] }) {
  const monthly = useMemo(() => {
    if (!data.length) return [];
    const months = {};
    data.forEach(d => {
      const month = d.date?.slice(0, 7); // "2026-03"
      if (!month) return;
      if (!months[month]) months[month] = { month, wins: 0, losses: 0 };
      const pnl = d.net_pnl || 0;
      if (pnl >= 0) months[month].wins += pnl;
      else months[month].losses += Math.abs(pnl);
    });
    return Object.values(months).slice(-6);
  }, [data]);

  if (!monthly.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={monthly} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" vertical={false} />
        <XAxis
          dataKey="month"
          tick={{ fill: '#94a3b8', fontSize: 12, fontWeight: 500 }}
          axisLine={false} tickLine={false}
          tickFormatter={m => {
            const idx = parseInt(m?.slice(5), 10) - 1;
            return monthNames[idx] || m;
          }}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false} tickLine={false}
          tickFormatter={v => `$${v}`}
          width={55}
        />
        <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} />} />
        <Legend wrapperStyle={{ fontSize: '0.6875rem' }} iconType="circle" iconSize={8} />
        <Bar dataKey="wins" name="Wins $" fill="#22c55e" fillOpacity={0.85} radius={[4, 4, 0, 0]} maxBarSize={28}>
          <LabelList
            dataKey="wins"
            position="top"
            formatter={v => v > 0 ? `$${v.toFixed(0)}` : ''}
            style={{ fill: '#22c55e', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
          />
        </Bar>
        <Bar dataKey="losses" name="Losses $" fill="#ef4444" fillOpacity={0.75} radius={[4, 4, 0, 0]} maxBarSize={28}>
          <LabelList
            dataKey="losses"
            position="top"
            formatter={v => v > 0 ? `$${v.toFixed(0)}` : ''}
            style={{ fill: '#ef4444', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
          />
        </Bar>
      </BarChart>
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
        <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} />} />
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

  // Prepare sparkline data from daily PnL
  const pnlSpark = useMemo(() =>
    (dailyPnl || []).slice(-14).map(d => ({ value: d.net_pnl || 0 }))
  , [dailyPnl]);

  const equitySpark = useMemo(() =>
    (equity || []).slice(-14).map(d => ({ value: d.cumulative_pnl || 0 }))
  , [equity]);

  // Compute commission from overview
  const commRate = ov.total_trades > 0 ? (ov.total_commission || 0) / ov.total_trades : 0;

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Dashboard Overview</h1>
        <p>Real-time trading performance at a glance</p>
      </div>

      {/* ── SparkCards (cashflow style: big number + sparkline) ──── */}
      <div className="grid-stats">
        <SparkCard
          title="Net PnL"
          value={ovLoading ? '...' : fmt(ov.net_pnl)}
          subtitle={ovLoading ? '' : `Gross: ${fmt(ov.total_pnl)} | Comm: ${fmt(ov.total_commission)}`}
          color={ov.net_pnl >= 0 ? 'green' : 'red'}
          sparkData={pnlSpark}
          sparkType="bar"
          delay={0}
        />
        <SparkCard
          title="Win Rate"
          value={ovLoading ? '...' : `${ov.win_rate || 0}%`}
          subtitle={`${ov.wins || 0}W / ${ov.losses || 0}L`}
          color="blue"
          sparkData={equitySpark}
          sparkType="area"
          delay={1}
        />
        <SparkCard
          title="Total Trades"
          value={ovLoading ? '...' : String(ov.total_trades || 0)}
          subtitle={`Avg: ${fmt(ov.avg_pnl)}`}
          color="purple"
          sparkData={pnlSpark}
          sparkType="line"
          delay={2}
        />
        <SparkCard
          title="Active Positions"
          value={ovLoading ? '...' : String(ov.active_groups || 0)}
          subtitle={`${ov.total_signals || 0} total signals`}
          color="amber"
          sparkData={[]}
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

      {/* ── Monthly Wins vs Losses (grouped bars, cashflow style) + Donut ── */}
      <div className="grid-main">
        <ChartCard title="Monthly Performance — Wins vs Losses" loading={dpLoading}>
          <MonthlyWinLossGrouped data={dailyPnl} />
        </ChartCard>
        <ChartCard title="Win / Loss Ratio" loading={ovLoading}>
          <WinLossDonut wins={ov.wins || 0} losses={ov.losses || 0} />
        </ChartCard>
      </div>

      {/* ── Top Channels + Active Positions ──────────────────────── */}
      <div className="grid-main">
        <ChartCard title="Top Channels" loading={chLoading}>
          <TopChannelsBars channels={channels} />
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
