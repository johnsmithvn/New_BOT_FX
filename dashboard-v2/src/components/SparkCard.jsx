import { motion } from 'framer-motion';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  ResponsiveContainer, Cell,
} from 'recharts';

/**
 * SparkCard — Big KPI number with embedded mini sparkline chart.
 * Inspired by cashflow dashboard style.
 *
 * Props:
 *   title      — Card label (e.g. "Net PnL")
 *   value      — Big formatted value (e.g. "$616.5K")
 *   subtitle   — Optional sub-text
 *   color      — Accent color name: 'green' | 'red' | 'blue' | 'purple' | 'amber'
 *   sparkData  — Array of {value: number} for sparkline
 *   sparkType  — 'area' | 'bar' | 'line' (default: 'area')
 *   delay      — Animation delay index
 */
const COLORS = {
  green:  { main: '#22c55e', dim: 'rgba(34,197,94,0.15)', bg: 'rgba(34,197,94,0.06)' },
  red:    { main: '#ef4444', dim: 'rgba(239,68,68,0.15)', bg: 'rgba(239,68,68,0.06)' },
  blue:   { main: '#3b82f6', dim: 'rgba(59,130,246,0.15)', bg: 'rgba(59,130,246,0.06)' },
  purple: { main: '#8b5cf6', dim: 'rgba(139,92,246,0.15)', bg: 'rgba(139,92,246,0.06)' },
  amber:  { main: '#f59e0b', dim: 'rgba(245,158,11,0.15)', bg: 'rgba(245,158,11,0.06)' },
  cyan:   { main: '#06b6d4', dim: 'rgba(6,182,212,0.15)', bg: 'rgba(6,182,212,0.06)' },
};

function MiniBar({ data, color }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <Bar dataKey="value" radius={[2, 2, 0, 0]} maxBarSize={12}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.value >= 0 ? color : '#ef4444'} fillOpacity={0.7} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function MiniArea({ data, color }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill={`url(#spark-${color})`}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function MiniLine({ data, color }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function SparkCard({
  title, value, subtitle, color = 'blue', sparkData = [],
  sparkType = 'area', delay = 0,
}) {
  const c = COLORS[color] || COLORS.blue;

  const SparkComponent = sparkType === 'bar' ? MiniBar
    : sparkType === 'line' ? MiniLine
    : MiniArea;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: delay * 0.08 }}
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px 20px 8px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        minHeight: 180,
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{
          fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-muted)',
          textTransform: 'uppercase', letterSpacing: '0.06em',
        }}>
          {title}
        </span>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: c.main, boxShadow: `0 0 8px ${c.dim}`,
        }} />
      </div>

      {/* Big Number */}
      <div style={{
        fontSize: '1.75rem', fontWeight: 700, lineHeight: 1.1,
        color: c.main, fontFamily: "'JetBrains Mono', monospace",
      }}>
        {value}
      </div>

      {/* Subtitle */}
      {subtitle && (
        <span style={{
          fontSize: '0.6875rem', color: 'var(--text-secondary)',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {subtitle}
        </span>
      )}

      {/* Sparkline */}
      {sparkData.length > 0 && (
        <div style={{ flex: 1, minHeight: 50, marginTop: 4 }}>
          <SparkComponent data={sparkData} color={c.main} />
        </div>
      )}
    </motion.div>
  );
}
