import { useMemo } from 'react';
import ChartCard from '../components/ChartCard';
import { useDailyPnl, useEquityCurve, useSymbolStats } from '../hooks/useApi';
import { PremiumTooltip } from '../charts/ChartPrimitives';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, CartesianGrid, ReferenceLine, LabelList,
  ComposedChart, Line, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';

/** Stacked Win/Loss bar chart by week/period */
function WinLossStackedBars({ data = [] }) {
  // Group by week showing wins and losses as stacked bars
  const weekly = useMemo(() => {
    if (!data.length) return [];
    const weeks = {};
    data.forEach(d => {
      // Get ISO week start (Monday)
      const dt = new Date(d.date);
      const day = dt.getDay();
      const diff = dt.getDate() - day + (day === 0 ? -6 : 1);
      const weekStart = new Date(dt.setDate(diff)).toISOString().slice(0, 10);
      if (!weeks[weekStart]) weeks[weekStart] = { week: weekStart, wins: 0, losses: 0, net: 0 };
      const pnl = d.net_pnl || 0;
      if (pnl >= 0) weeks[weekStart].wins += pnl;
      else weeks[weekStart].losses += Math.abs(pnl);
      weeks[weekStart].net += pnl;
    });
    return Object.values(weeks).slice(-12);
  }, [data]);

  if (!weekly.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={weekly} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" vertical={false} />
        <XAxis dataKey="week" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={d => d?.slice(5)} />
        <YAxis yAxisId="stack" tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={v => `$${v}`} width={55} axisLine={false} tickLine={false} />
        <YAxis yAxisId="line" orientation="right" tick={{ fill: '#f59e0b', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={v => `$${v}`} width={50} axisLine={false} tickLine={false} hide />
        <Tooltip content={<PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} showTotal />} />
        <Legend wrapperStyle={{ fontSize: '0.6875rem' }} iconType="circle" iconSize={8} />
        <Bar yAxisId="stack" dataKey="wins" name="Wins" fill="#22c55e" fillOpacity={0.8} stackId="a" radius={[0, 0, 0, 0]} maxBarSize={28} />
        <Bar yAxisId="stack" dataKey="losses" name="Losses" fill="#ef4444" fillOpacity={0.7} stackId="a" radius={[3, 3, 0, 0]} maxBarSize={28} />
        <Line yAxisId="stack" type="monotone" dataKey="net" name="Net" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3, fill: '#f59e0b' }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/** PnL Distribution Histogram */
function PnlDistributionChart({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  const bucketSize = 50;
  const histogram = {};
  data.forEach(d => {
    const val = d.net_pnl || d.pnl || 0;
    const bucket = Math.round(val / bucketSize) * bucketSize;
    histogram[bucket] = (histogram[bucket] || 0) + 1;
  });
  const sorted = Object.entries(histogram)
    .map(([k, v]) => ({ bucket: Number(k), count: v }))
    .sort((a, b) => a.bucket - b.bucket);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={sorted} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" vertical={false} />
        <XAxis dataKey="bucket" tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={v => `$${v}`} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} axisLine={false} tickLine={false} />
        <Tooltip content={
          <PremiumTooltip formatter={(v, name) => name === 'count' || name === 'Days' ? `${v} days` : v} />
        } />
        <ReferenceLine x={0} stroke="rgba(148,163,184,0.3)" />
        <Bar dataKey="count" name="Days" radius={[4, 4, 0, 0]} animationDuration={600} maxBarSize={30}>
          <LabelList dataKey="count" position="top" style={{ fill: '#94a3b8', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
          {sorted.map((e, i) => (
            <Cell key={i} fill={e.bucket >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Drawdown Chart */
function DrawdownChart({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  let peak = 0;
  const dd = data.map(d => {
    const eq = d.cumulative_pnl || 0;
    if (eq > peak) peak = eq;
    const drawdown = peak > 0 ? ((eq - peak) / peak) * 100 : 0;
    return { date: d.date, drawdown: Math.min(drawdown, 0), equity: eq };
  });

  const maxDD = Math.min(...dd.map(d => d.drawdown));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={dd} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" />
        <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={d => d?.slice(5)} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} tickFormatter={v => `${v}%`} width={50} axisLine={false} tickLine={false} />
        <Tooltip content={<PremiumTooltip formatter={(v) => `${v?.toFixed(2)}%`} />} />
        <ReferenceLine y={0} stroke="rgba(148,163,184,0.2)" />
        {maxDD < 0 && <ReferenceLine y={maxDD} stroke="#ef4444" strokeDasharray="2 4" strokeOpacity={0.4} label={{ value: `Max ${maxDD.toFixed(1)}%`, fill: '#ef4444', fontSize: 10, position: 'left' }} />}
        <Area type="monotone" dataKey="drawdown" name="Drawdown" stroke="#ef4444" fill="url(#ddGrad)" strokeWidth={1.5} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Symbol performance — stacked horizontal bars comparing W/L */
function SymbolWinLossCompare({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  const top8 = data.slice(0, 8).map(s => ({
    symbol: s.symbol,
    wins: s.wins || 0,
    losses: -(s.losses || 0), // negative for visual comparison
    winRate: s.win_rate || 0,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={top8} layout="vertical" margin={{ top: 5, right: 40, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" horizontal={false} />
        <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="symbol" tick={{ fill: '#94a3b8', fontSize: 11 }} width={70} axisLine={false} tickLine={false} />
        <Tooltip content={<PremiumTooltip formatter={(v) => `${Math.abs(v)} trades`} />} />
        <Legend wrapperStyle={{ fontSize: '0.6875rem' }} iconType="circle" iconSize={8} />
        <ReferenceLine x={0} stroke="rgba(148,163,184,0.15)" />
        <Bar dataKey="wins" name="Wins" fill="#22c55e" fillOpacity={0.85} radius={[0, 3, 3, 0]} maxBarSize={18}>
          <LabelList dataKey="wins" position="right" style={{ fill: '#22c55e', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
        </Bar>
        <Bar dataKey="losses" name="Losses" fill="#ef4444" fillOpacity={0.75} radius={[3, 0, 0, 3]} maxBarSize={18}>
          <LabelList dataKey="losses" position="left" formatter={v => Math.abs(v)} style={{ fill: '#ef4444', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Trading Activity with cumulative count */
function TradingActivity({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  let cumCount = 0;
  const enriched = data.map(d => {
    cumCount += (d.trades || 0);
    return { ...d, cumTrades: cumCount };
  });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={enriched} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.2} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" />
        <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={d => d?.slice(5)} />
        <YAxis yAxisId="bar" tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} axisLine={false} tickLine={false} />
        <YAxis yAxisId="line" orientation="right" tick={{ fill: '#06b6d4', fontSize: 10 }} axisLine={false} tickLine={false} hide />
        <Tooltip content={<PremiumTooltip formatter={(v, name) => name === 'Cumulative' ? `${v} total` : `${v} trades` } />} />
        <Legend wrapperStyle={{ fontSize: '0.6875rem' }} iconType="circle" iconSize={8} />
        <Bar yAxisId="bar" dataKey="trades" name="Daily" fill="#3b82f6" fillOpacity={0.7} radius={[3, 3, 0, 0]} maxBarSize={20} />
        <Line yAxisId="line" type="monotone" dataKey="cumTrades" name="Cumulative" stroke="#06b6d4" strokeWidth={2} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default function Analytics() {
  const { data: dailyPnl, isLoading: dpLoading } = useDailyPnl(365);
  const { data: equity, isLoading: eqLoading } = useEquityCurve(365);
  const { data: symbols, isLoading: symLoading } = useSymbolStats();

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Analytics</h1>
        <p>Advanced performance analysis and distribution insights</p>
      </div>

      {/* Stacked Win/Loss + Histogram */}
      <div className="grid-2">
        <ChartCard title="Weekly Win vs Loss (Stacked)" loading={dpLoading}>
          <WinLossStackedBars data={dailyPnl} />
        </ChartCard>
        <ChartCard title="PnL Distribution" loading={dpLoading}>
          <PnlDistributionChart data={dailyPnl} />
        </ChartCard>
      </div>

      {/* Drawdown + Activity Combo */}
      <div className="grid-2">
        <ChartCard title="Max Drawdown" loading={eqLoading}>
          <DrawdownChart data={equity} />
        </ChartCard>
        <ChartCard title="Trading Activity (Daily + Cumulative)" loading={dpLoading}>
          <TradingActivity data={dailyPnl} />
        </ChartCard>
      </div>

      {/* Symbol comparison */}
      <div className="full-width">
        <ChartCard title="Symbol Win/Loss Comparison" loading={symLoading}>
          <SymbolWinLossCompare data={symbols} />
        </ChartCard>
      </div>
    </div>
  );
}
