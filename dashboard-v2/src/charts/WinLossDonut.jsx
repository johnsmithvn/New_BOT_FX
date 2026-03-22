import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

export default function WinLossDonut({ wins = 0, losses = 0 }) {
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
            innerRadius="65%"
            outerRadius="85%"
            paddingAngle={3}
            dataKey="value"
            animationDuration={800}
            stroke="none"
          >
            {data.map((_, i) => (
              <Cell key={i} fill={colors[i]} />
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
      }}>
        <div style={{
          fontSize: '1.5rem',
          fontWeight: 700,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-primary)',
        }}>
          {winRate}%
        </div>
        <div style={{
          fontSize: '0.6875rem',
          color: 'var(--text-secondary)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}>
          Win Rate
        </div>
      </div>

      {/* Legend */}
      <div style={{
        position: 'absolute',
        bottom: 8,
        left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex',
        gap: 16,
        fontSize: '0.75rem',
      }}>
        <span style={{ color: '#22c55e' }}>● {wins} Wins</span>
        <span style={{ color: '#ef4444' }}>● {losses} Losses</span>
      </div>
    </div>
  );
}
