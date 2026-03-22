import { PieChart, Pie, Cell, ResponsiveContainer, Sector } from 'recharts';
import { useState } from 'react';

/** Active sector renderer — expanded sector with glow effect */
const renderActiveShape = (props) => {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload, percent, value } = props;
  return (
    <g>
      <Sector
        cx={cx} cy={cy}
        innerRadius={innerRadius - 3}
        outerRadius={outerRadius + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={1}
        style={{ filter: `drop-shadow(0 0 8px ${fill})` }}
      />
      <Sector
        cx={cx} cy={cy}
        innerRadius={outerRadius + 10}
        outerRadius={outerRadius + 12}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.6}
      />
      {/* Label outside */}
      <text x={cx} y={cy - 45} textAnchor="middle" fill="#64748b" fontSize={10} fontFamily="'Inter', sans-serif">
        {payload.name}
      </text>
    </g>
  );
};

export default function WinLossDonut({ wins = 0, losses = 0 }) {
  const [activeIndex, setActiveIndex] = useState(-1);
  const total = wins + losses;
  const winRate = total > 0 ? ((wins / total) * 100).toFixed(1) : '0.0';

  const data = [
    { name: 'Wins', value: wins },
    { name: 'Losses', value: losses },
  ];
  const colors = ['#22c55e', '#ef4444'];

  if (total === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <p className="text-muted">No trades yet</p>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius="60%"
            outerRadius="80%"
            paddingAngle={4}
            dataKey="value"
            animationDuration={1000}
            stroke="none"
            activeIndex={activeIndex >= 0 ? activeIndex : undefined}
            activeShape={renderActiveShape}
            onMouseEnter={(_, i) => setActiveIndex(i)}
            onMouseLeave={() => setActiveIndex(-1)}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={colors[i]} fillOpacity={activeIndex === i ? 1 : 0.85} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>

      {/* Center text */}
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        textAlign: 'center',
        pointerEvents: 'none',
      }}>
        <div style={{
          fontSize: '2rem',
          fontWeight: 800,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-primary)',
          lineHeight: 1.1,
          textShadow: '0 0 20px rgba(255,255,255,0.1)',
        }}>
          {winRate}%
        </div>
        <div style={{
          fontSize: '0.625rem',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          marginTop: 2,
        }}>
          Win Rate
        </div>
      </div>

      {/* Legend with counts + percentage */}
      <div style={{
        position: 'absolute',
        bottom: 4,
        left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex',
        gap: 20,
        fontSize: '0.75rem',
        fontFamily: 'var(--font-mono)',
      }}>
        <span style={{ color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          {wins}W ({total > 0 ? ((wins / total) * 100).toFixed(0) : 0}%)
        </span>
        <span style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
          {losses}L ({total > 0 ? ((losses / total) * 100).toFixed(0) : 0}%)
        </span>
      </div>
    </div>
  );
}
