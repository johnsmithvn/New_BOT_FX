import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts';
import { PremiumTooltip } from './ChartPrimitives';

export default function EquityCurve({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data available</p>;

  const isPositive = data[data.length - 1].cumulative_pnl >= 0;
  const color = isPositive ? '#22c55e' : '#ef4444';
  const highColor = '#3b82f6';

  // Annotate high / low
  let maxVal = -Infinity, minVal = Infinity;
  data.forEach(d => {
    if (d.cumulative_pnl > maxVal) maxVal = d.cumulative_pnl;
    if (d.cumulative_pnl < minVal) minVal = d.cumulative_pnl;
  });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="50%" stopColor={color} stopOpacity={0.1} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'Inter', sans-serif" }}
          axisLine={{ stroke: 'rgba(148,163,184,0.08)' }}
          tickLine={false}
          tickFormatter={(d) => d?.slice(5)}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v}`}
          width={60}
        />
        <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => `$${v?.toFixed(2)}`} />} />
        <ReferenceLine y={0} stroke="rgba(148,163,184,0.12)" strokeDasharray="4 4" />
        {maxVal > 0 && <ReferenceLine y={maxVal} stroke="#22c55e" strokeDasharray="2 4" strokeOpacity={0.3} label={{ value: `Peak $${maxVal.toFixed(0)}`, fill: '#22c55e', fontSize: 10, position: 'right' }} />}
        <Area
          type="monotone"
          dataKey="cumulative_pnl"
          name="Equity"
          stroke={color}
          strokeWidth={2.5}
          fill="url(#equityGrad)"
          animationDuration={1000}
          activeDot={{ r: 5, stroke: color, fill: 'var(--bg-primary)', strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
