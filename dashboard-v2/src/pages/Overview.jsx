import { useState, useMemo, useCallback } from 'react';
import { Eye, EyeOff, SlidersHorizontal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ChartCard from '../components/ChartCard';
import SparkCard from '../components/SparkCard';
import EquityCurve from '../charts/EquityCurve';
import WinLossDonut from '../charts/WinLossDonut';
import { useOverview, useDailyPnl, useEquityCurve, useChannels, useActive, useSignalStatusCounts } from '../hooks/useApi';
import {
  ComposedChart, BarChart, Bar, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, CartesianGrid, LabelList, Legend,
  RadialBarChart, RadialBar,
} from 'recharts';
import { PremiumTooltip } from '../charts/ChartPrimitives';
import { fmtCcy, tickCcy, tooltipCcy } from '../utils/format';

/* ═══════════════════════════════════════════════════════════════
   CHART VISIBILITY HOOK — persisted to localStorage
   ═══════════════════════════════════════════════════════════════ */
const STORAGE_KEY = 'overview_chart_visibility';
const DEFAULT_VISIBILITY = {
  equity: true,
  comboPnl: true,
  monthlyWinLoss: true,
  winLossDonut: true,
  topChannels: true,
  activePositions: true,
  signalBreakdown: true,
  winRateGauge: true,
  pnlByWeekday: true,
};

function useChartVisibility() {
  const [visibility, setVisibility] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? { ...DEFAULT_VISIBILITY, ...JSON.parse(saved) } : DEFAULT_VISIBILITY;
    } catch { return DEFAULT_VISIBILITY; }
  });

  const toggle = useCallback((key) => {
    setVisibility(prev => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  return [visibility, toggle];
}

/* ═══════════════════════════════════════════════════════════════
   CHART TOGGLE PANEL
   ═══════════════════════════════════════════════════════════════ */
const CHART_LABELS = {
  equity:          'Equity Curve',
  comboPnl:        'Daily PnL + Cumulative',
  monthlyWinLoss:  'Monthly Wins vs Losses',
  winLossDonut:    'Win / Loss Ratio',
  topChannels:     'Top Channels',
  activePositions: 'Active Positions',
  signalBreakdown: 'Signal Breakdown',
  winRateGauge:    'Win Rate Gauge',
  pnlByWeekday:    'PnL by Weekday',
};

function ChartTogglePanel({ visibility, onToggle }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <button
        className="btn btn-ghost"
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', fontSize: '0.8125rem' }}
      >
        <SlidersHorizontal size={14} />
        Customize
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            style={{
              position: 'absolute', right: 0, top: '100%', marginTop: 6,
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              borderRadius: 12, padding: '12px 16px', zIndex: 100, minWidth: 220,
              boxShadow: '0 12px 32px rgba(0,0,0,0.25)',
            }}
          >
            <p style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
              Show / Hide Charts
            </p>
            {Object.entries(CHART_LABELS).map(([key, label]) => (
              <button
                key={key}
                onClick={() => onToggle(key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                  padding: '6px 0', background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: '0.8125rem', color: visibility[key] ? 'var(--text-primary)' : 'var(--text-muted)',
                }}
              >
                {visibility[key] ? <Eye size={14} color="var(--accent-green)" /> : <EyeOff size={14} />}
                {label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   NEW CHART: Win Rate Gauge (radial bar)
   ═══════════════════════════════════════════════════════════════ */
function WinRateGauge({ winRate = 0, wins = 0, losses = 0 }) {
  const data = [{ name: 'Win Rate', value: winRate, fill: winRate >= 50 ? '#22c55e' : '#ef4444' }];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
      <div style={{ width: 180, height: 180, position: 'relative' }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%" cy="50%"
            innerRadius="78%" outerRadius="100%"
            startAngle={210} endAngle={-30}
            data={data}
            barSize={14}
          >
            <RadialBar background={{ fill: 'rgba(148,163,184,0.08)' }} dataKey="value" cornerRadius={8} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: '2rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: winRate >= 50 ? '#22c55e' : '#ef4444' }}>
            {winRate}%
          </span>
          <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Win Rate</span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 20, marginTop: 12 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#22c55e', fontFamily: 'var(--font-mono)' }}>{wins}</div>
          <div style={{ fontSize: '0.625rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Wins</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#ef4444', fontFamily: 'var(--font-mono)' }}>{losses}</div>
          <div style={{ fontSize: '0.625rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Losses</div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   NEW CHART: Signal Breakdown (table card like PLECTO MRR Breakdown)
   ═══════════════════════════════════════════════════════════════ */
function SignalBreakdown({ statusCounts }) {
  const stats = statusCounts || {};

  const rows = [
    { label: 'Executed', count: stats.executed, color: '#22c55e', icon: '✅' },
    { label: 'Rejected', count: stats.rejected, color: '#f59e0b', icon: '🚫' },
    { label: 'Failed', count: stats.failed, color: '#ef4444', icon: '❌' },
    { label: 'Received', count: stats.received, color: '#3b82f6', icon: '📩' },
    { label: 'Duplicate', count: stats.duplicate, color: '#94a3b8', icon: '📋' },
    { label: 'Active', count: stats.active, color: '#8b5cf6', icon: '🔄' },
  ];

  return (
    <div style={{ padding: '4px 0' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={{ textAlign: 'left', padding: '6px 0', fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: 600 }}>TYPE</th>
            <th style={{ textAlign: 'right', padding: '6px 0', fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: 600 }}>COUNT</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.label} style={{ borderBottom: '1px solid rgba(148,163,184,0.04)' }}>
              <td style={{ padding: '8px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>{r.icon}</span>
                <span>{r.label}</span>
              </td>
              <td style={{ textAlign: 'right', padding: '8px 0' }}>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontWeight: 600,
                  color: r.count > 0 ? r.color : 'var(--text-muted)',
                  background: r.count > 0 ? `${r.color}15` : 'transparent',
                  padding: '2px 10px', borderRadius: 6,
                }}>
                  {r.count}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: '10px 0', fontWeight: 700, fontSize: '0.8125rem' }}>TOTAL</td>
            <td style={{ textAlign: 'right', padding: '10px 0', fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.9375rem' }}>{stats.total}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   NEW CHART: PnL by Weekday (bar chart)
   ═══════════════════════════════════════════════════════════════ */
function PnlByWeekday({ dailyData = [] }) {
  const weekdayData = useMemo(() => {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const agg = days.map(d => ({ day: d, pnl: 0, count: 0 }));
    dailyData.forEach(d => {
      if (!d.date) return;
      const dow = new Date(d.date).getDay();
      agg[dow].pnl += (d.net_pnl || 0);
      agg[dow].count++;
    });
    // Trading days only (Mon-Fri)
    return agg.slice(1, 6);
  }, [dailyData]);

  if (!weekdayData.length || weekdayData.every(d => d.count === 0)) {
    return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No data</p>;
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={weekdayData} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" vertical={false} />
        <XAxis
          dataKey="day"
          tick={{ fill: '#94a3b8', fontSize: 12, fontWeight: 600 }}
          axisLine={false} tickLine={false}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false} tickLine={false}
          tickFormatter={tickCcy}
          width={55}
        />
        <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => tooltipCcy(v)} />} />
        <Bar dataKey="pnl" name="Total PnL" radius={[6, 6, 0, 0]} maxBarSize={40} animationDuration={800}>
          <LabelList
            dataKey="pnl"
            position="top"
            formatter={v => v !== 0 ? `${v.toFixed(1)} $` : ''}
            style={{ fill: '#94a3b8', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
          />
          {weekdayData.map((entry, i) => (
            <Cell key={i} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ═══════════════════════════════════════════════════════════════
   EXISTING CHARTS (kept as is)
   ═══════════════════════════════════════════════════════════════ */

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
          tickFormatter={tickCcy}
          width={55}
        />
        <YAxis
          yAxisId="line" orientation="right"
          tick={{ fill: '#8b5cf6', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false} tickLine={false}
          tickFormatter={tickCcy}
          width={55}
        />
        <Tooltip cursor={false} content={
          <PremiumTooltip formatter={(v) => tooltipCcy(v)} />
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

/** Monthly Wins vs Losses grouped bar chart */
function MonthlyWinLossGrouped({ data = [] }) {
  const monthly = useMemo(() => {
    if (!data.length) return [];
    const months = {};
    data.forEach(d => {
      const month = d.date?.slice(0, 7);
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
          tickFormatter={tickCcy}
          width={55}
        />
        <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => tooltipCcy(v)} />} />
        <Legend wrapperStyle={{ fontSize: '0.6875rem' }} iconType="circle" iconSize={8} />
        <Bar dataKey="wins" name="Wins" fill="#22c55e" fillOpacity={0.85} radius={[4, 4, 0, 0]} maxBarSize={28}>
          <LabelList
            dataKey="wins"
            position="top"
            formatter={v => v > 0 ? `${v.toFixed(0)} $` : ''}
            style={{ fill: '#22c55e', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
          />
        </Bar>
        <Bar dataKey="losses" name="Losses" fill="#ef4444" fillOpacity={0.75} radius={[4, 4, 0, 0]} maxBarSize={28}>
          <LabelList
            dataKey="losses"
            position="top"
            formatter={v => v > 0 ? `${v.toFixed(0)} $` : ''}
            style={{ fill: '#ef4444', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Top Channels — horizontal bars */
function TopChannelsBars({ channels = [] }) {
  if (!channels.length) return <p className="text-muted" style={{ textAlign: 'center', paddingTop: 60 }}>No channel data</p>;

  const sorted = [...channels].sort((a, b) => (b.total_pnl || 0) - (a.total_pnl || 0)).slice(0, 8);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={sorted} layout="vertical" margin={{ top: 5, right: 50, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" horizontal={false} />
        <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} axisLine={false} tickLine={false} tickFormatter={tickCcy} />
        <YAxis type="category" dataKey="channel_name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} width={100} />
        <Tooltip cursor={false} content={<PremiumTooltip formatter={(v) => tooltipCcy(v)} />} />
        <Bar dataKey="total_pnl" name="Total PnL" radius={[0, 4, 4, 0]} animationDuration={800} maxBarSize={22}>
          <LabelList
            dataKey="total_pnl"
            position="right"
            formatter={(v) => `${v?.toFixed(1)} $`}
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

/* ═══════════════════════════════════════════════════════════════
   OVERVIEW PAGE
   ═══════════════════════════════════════════════════════════════ */
export default function Overview() {
  const { data: overview, isLoading: ovLoading } = useOverview();
  const [pnlDays, setPnlDays] = useState(30);
  const { data: dailyPnl, isLoading: dpLoading } = useDailyPnl(pnlDays);
  const { data: equity, isLoading: eqLoading } = useEquityCurve(365);
  const { data: channels, isLoading: chLoading } = useChannels();
  const { data: active } = useActive();
  const { data: statusCounts } = useSignalStatusCounts();

  const [vis, toggleVis] = useChartVisibility();

  const ov = overview || {};

  // Prepare sparkline data from daily PnL
  const pnlSpark = useMemo(() =>
    (dailyPnl || []).slice(-14).map(d => ({ value: d.net_pnl || 0 }))
  , [dailyPnl]);

  const equitySpark = useMemo(() =>
    (equity || []).slice(-14).map(d => ({ value: d.cumulative_pnl || 0 }))
  , [equity]);

  return (
    <div className="page-content">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1>Dashboard Overview</h1>
          <p>Real-time trading performance at a glance</p>
        </div>
        <ChartTogglePanel visibility={vis} onToggle={toggleVis} />
      </div>

      {/* ── SparkCards ──────────────────────────────────────────── */}
      <div className="grid-stats">
        <SparkCard
          title="Net PnL"
          value={ovLoading ? '...' : fmtCcy(ov.net_pnl)}
          subtitle={ovLoading ? '' : `Gross: ${fmtCcy(ov.total_pnl)} | Comm: ${fmtCcy(ov.total_commission)}`}
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
          subtitle={`Avg: ${fmtCcy(ov.avg_pnl)}`}
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

      {/* ── NEW: Win Rate Gauge + Signal Breakdown (PLECTO-style) ── */}
      <div className="grid-main">
        {vis.winRateGauge && (
          <ChartCard title="Win Rate" loading={ovLoading}>
            <WinRateGauge winRate={ov.win_rate || 0} wins={ov.wins || 0} losses={ov.losses || 0} />
          </ChartCard>
        )}
        {vis.signalBreakdown && (
          <ChartCard title="Signal Breakdown" loading={!statusCounts}>
            <SignalBreakdown statusCounts={statusCounts} />
          </ChartCard>
        )}
      </div>

      {/* ── Equity Curve ─────────────────────────────────────────── */}
      {vis.equity && (
        <div className="full-width">
          <ChartCard title="Equity Curve" loading={eqLoading}>
            <EquityCurve data={equity} />
          </ChartCard>
        </div>
      )}

      {/* ── Combo Chart: Daily PnL bars + Cumulative line ────────── */}
      {vis.comboPnl && (
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
      )}

      {/* ── Monthly + Donut / PnL by Weekday ─────────────────────── */}
      <div className="grid-main">
        {vis.monthlyWinLoss && (
          <ChartCard title="Monthly Performance — Wins vs Losses" loading={dpLoading}>
            <MonthlyWinLossGrouped data={dailyPnl} />
          </ChartCard>
        )}
        {vis.pnlByWeekday && (
          <ChartCard title="PnL by Weekday" loading={dpLoading}>
            <PnlByWeekday dailyData={dailyPnl} />
          </ChartCard>
        )}
      </div>

      {/* ── Win/Loss Donut + Top Channels ─────────────────────────── */}
      <div className="grid-main">
        {vis.winLossDonut && (
          <ChartCard title="Win / Loss Ratio" loading={ovLoading}>
            <WinLossDonut wins={ov.wins || 0} losses={ov.losses || 0} />
          </ChartCard>
        )}
        {vis.topChannels && (
          <ChartCard title="Top Channels" loading={chLoading}>
            <TopChannelsBars channels={channels} />
          </ChartCard>
        )}
      </div>

      {/* ── Active Positions ──────────────────────────────────────── */}
      {vis.activePositions && (
        <div className="full-width">
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
      )}
    </div>
  );
}
