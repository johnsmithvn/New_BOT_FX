import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid, ReferenceLine, LabelList } from 'recharts';
import { PremiumTooltip } from './ChartPrimitives';

/** Custom label on top of bars */
const renderBarLabel = (props) => {
  const { x, y, width, value } = props;
  if (value == null || value === 0) return null;
  const formatted = Math.abs(value) >= 100 ? `${(value / 1).toFixed(0)}` : value.toFixed(1);
  return (
    <text
      x={x + width / 2}
      y={value >= 0 ? y - 6 : y + 14}
      fill={value >= 0 ? '#22c55e' : '#ef4444'}
      textAnchor="middle"
      fontSize={9}
      fontFamily="'JetBrains Mono', monospace"
      fontWeight={600}
      opacity={0.8}
    >
      ${formatted}
    </text>
  );
};

export default function DailyPnlBars({ data = [] }) {
  if (!data.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 20, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" vertical={false} />
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
        <Tooltip content={
          <PremiumTooltip
            formatter={(v, name) => `$${v?.toFixed(2)}`}
          />
        } />
        <ReferenceLine y={0} stroke="rgba(148,163,184,0.15)" />
        <Bar dataKey="net_pnl" name="Net PnL" radius={[4, 4, 0, 0]} animationDuration={800} maxBarSize={40}>
          <LabelList content={renderBarLabel} />
          {data.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.net_pnl >= 0 ? '#22c55e' : '#ef4444'}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
