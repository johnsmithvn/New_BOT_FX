import ChartCard from '../components/ChartCard';
import { useSymbolStats } from '../hooks/useApi';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from 'recharts';

function SymbolTable({ data }) {
  if (!data?.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No symbol data</p>;

  return (
    <div style={{ overflow: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Trades</th>
            <th>Win Rate</th>
            <th>Total PnL</th>
            <th>Avg PnL</th>
            <th>W/L</th>
          </tr>
        </thead>
        <tbody>
          {data.map((s, i) => (
            <tr key={i}>
              <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.symbol}</td>
              <td>{s.total_trades}</td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 60, height: 4, borderRadius: 2, background: 'var(--accent-red-dim)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${s.win_rate}%`, background: 'var(--accent-green)', borderRadius: 2 }} />
                  </div>
                  <span style={{ fontSize: '0.75rem' }}>{s.win_rate}%</span>
                </div>
              </td>
              <td style={{ color: s.total_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                ${s.total_pnl?.toFixed(2)}
              </td>
              <td style={{ color: s.avg_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                ${s.avg_pnl?.toFixed(2)}
              </td>
              <td>
                <span style={{ color: 'var(--accent-green)' }}>{s.wins}</span>
                {' / '}
                <span style={{ color: 'var(--accent-red)' }}>{s.losses}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SymbolRadar({ data }) {
  const top5 = (data || []).slice(0, 5).map(s => ({
    symbol: s.symbol,
    winRate: s.win_rate || 0,
    trades: Math.min((s.total_trades || 0), 100),
    avgPnl: Math.max(Math.min((s.avg_pnl || 0) + 50, 100), 0),
  }));

  if (!top5.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={top5} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
        <PolarGrid stroke="rgba(148,163,184,0.1)" />
        <PolarAngleAxis dataKey="symbol" tick={{ fill: '#94a3b8', fontSize: 11 }} />
        <PolarRadiusAxis tick={{ fill: '#64748b', fontSize: 10 }} domain={[0, 100]} />
        <Radar name="Win Rate" dataKey="winRate" stroke="#22c55e" fill="#22c55e" fillOpacity={0.2} />
        <Radar name="Activity" dataKey="trades" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export default function Symbols() {
  const { data: symbols, isLoading } = useSymbolStats();

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Symbols</h1>
        <p>Per-instrument performance breakdown</p>
      </div>

      <div className="full-width">
        <ChartCard title="Symbol Performance Table" loading={isLoading}>
          <SymbolTable data={symbols} />
        </ChartCard>
      </div>

      <div className="grid-2">
        <ChartCard title="Symbol PnL Ranking" loading={isLoading}>
          {symbols && symbols.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={symbols} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `$${v}`} />
                <YAxis type="category" dataKey="symbol" tick={{ fill: '#94a3b8', fontSize: 11 }} width={80} />
                <Tooltip
                  formatter={(v) => [`$${v?.toFixed(2)}`, 'PnL']}
                  contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
                />
                <Bar dataKey="total_pnl" radius={[0, 4, 4, 0]}>
                  {symbols.map((s, i) => (
                    <Cell key={i} fill={s.total_pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : null}
        </ChartCard>

        <ChartCard title="Top 5 Symbol Radar" loading={isLoading}>
          <SymbolRadar data={symbols} />
        </ChartCard>
      </div>
    </div>
  );
}
