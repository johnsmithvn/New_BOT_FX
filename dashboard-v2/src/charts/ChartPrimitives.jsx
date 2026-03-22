/**
 * Shared premium tooltip component for all Recharts charts.
 * Glassy dark design with color-coded values and data labels.
 */

export function PremiumTooltip({ active, payload, label, formatter, showTotal }) {
  if (!active || !payload?.length) return null;

  const total = showTotal ? payload.reduce((sum, p) => sum + (p.value || 0), 0) : null;

  return (
    <div className="chart-tooltip">
      <div className="tooltip-label">{label}</div>
      {payload.map((p, i) => {
        const val = typeof formatter === 'function' ? formatter(p.value, p.name) : `$${p.value?.toFixed(2)}`;
        const colorClass = p.value > 0 ? 'profit' : p.value < 0 ? 'loss' : 'neutral';
        return (
          <div key={i} className="tooltip-row">
            <span className="tooltip-name">
              <span className="tooltip-dot" style={{ backgroundColor: p.color || p.stroke }} />
              {p.name || p.dataKey}
            </span>
            <span className={`tooltip-value ${colorClass}`}>{val}</span>
          </div>
        );
      })}
      {total !== null && (
        <div className="tooltip-footer">
          Total: <strong style={{ color: total >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>${total.toFixed(2)}</strong>
        </div>
      )}
    </div>
  );
}

/** Custom bar label renderer - shows value on top of bars */
export function BarLabel({ x, y, width, value, fill }) {
  if (value === 0 || value == null) return null;
  const formatted = Math.abs(value) >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(1);
  return (
    <text
      x={x + width / 2}
      y={value >= 0 ? y - 6 : y + 16}
      fill={fill || '#94a3b8'}
      textAnchor="middle"
      fontSize={10}
      fontFamily="'JetBrains Mono', monospace"
      fontWeight={600}
    >
      ${formatted}
    </text>
  );
}

/** Pie chart custom label with percentage + value */
export function PieLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent, value, name }) {
  if (percent < 0.05) return null; // Skip tiny slices
  const RADIAN = Math.PI / 180;
  const radius = outerRadius + 24;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="#94a3b8"
      textAnchor={x > cx ? 'start' : 'end'}
      dominantBaseline="central"
      fontSize={11}
      fontFamily="'JetBrains Mono', monospace"
    >
      {name} ({(percent * 100).toFixed(0)}%)
    </text>
  );
}
