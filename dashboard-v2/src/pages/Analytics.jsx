import { useState } from 'react';
import ChartCard from '../components/ChartCard';
import { useDailyPnl, useEquityCurve, useSymbolStats } from '../hooks/useApi';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid, ReferenceLine } from 'recharts';

function PnlDistributionChart({ data = [] }) {
  // Build histogram from daily PnL data
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
      <BarChart data={sorted} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" vertical={false} />
        <XAxis dataKey="bucket" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `$${v}`} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          formatter={(v) => [v, 'Days']}
          labelFormatter={(l) => `$${l} range`}
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
        />
        <ReferenceLine x={0} stroke="rgba(148,163,184,0.3)" />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} animationDuration={600}>
          {sorted.map((e, i) => (
            <Cell key={i} fill={e.bucket >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function DrawdownChart({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  // Compute drawdown from equity curve
  let peak = 0;
  const dd = data.map(d => {
    const eq = d.cumulative_pnl || 0;
    if (eq > peak) peak = eq;
    const drawdown = peak > 0 ? ((eq - peak) / peak) * 100 : 0;
    return { date: d.date, drawdown: Math.min(drawdown, 0) };
  });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={dd} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
        <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={d => d?.slice(5)} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `${v}%`} width={50} />
        <Tooltip
          formatter={(v) => [`${v?.toFixed(2)}%`, 'Drawdown']}
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
        />
        <ReferenceLine y={0} stroke="rgba(148,163,184,0.2)" />
        <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="url(#ddGrad)" strokeWidth={1.5} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function SymbolPerformanceBars({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data.slice(0, 8)} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `$${v}`} />
        <YAxis type="category" dataKey="symbol" tick={{ fill: '#94a3b8', fontSize: 11 }} width={80} />
        <Tooltip
          formatter={(v) => [`$${v?.toFixed(2)}`, 'PnL']}
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
        />
        <Bar dataKey="total_pnl" radius={[0, 4, 4, 0]} animationDuration={600}>
          {data.slice(0, 8).map((s, i) => (
            <Cell key={i} fill={s.total_pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function TradingActivity({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
        <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={d => d?.slice(5)} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
        />
        <Area type="monotone" dataKey="trades" stroke="#8b5cf6" fill="url(#actGrad)" strokeWidth={2} />
      </AreaChart>
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

      <div className="grid-2">
        <ChartCard title="PnL Distribution" loading={dpLoading}>
          <PnlDistributionChart data={dailyPnl} />
        </ChartCard>
        <ChartCard title="Max Drawdown" loading={eqLoading}>
          <DrawdownChart data={equity} />
        </ChartCard>
      </div>

      <div className="grid-2">
        <ChartCard title="Symbol Performance" loading={symLoading}>
          <SymbolPerformanceBars data={symbols} />
        </ChartCard>
        <ChartCard title="Trading Activity" loading={dpLoading}>
          <TradingActivity data={dailyPnl} />
        </ChartCard>
      </div>
    </div>
  );
}
