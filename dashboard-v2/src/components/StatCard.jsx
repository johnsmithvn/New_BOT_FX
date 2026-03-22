import { motion } from 'framer-motion';

export default function StatCard({ icon: Icon, label, value, change, color = 'blue', delay = 0 }) {
  const colorMap = {
    blue:   { bg: 'var(--accent-blue-dim)',   text: 'var(--accent-blue)' },
    green:  { bg: 'var(--accent-green-dim)',  text: 'var(--accent-green)' },
    red:    { bg: 'var(--accent-red-dim)',    text: 'var(--accent-red)' },
    purple: { bg: 'var(--accent-purple-dim)', text: 'var(--accent-purple)' },
    amber:  { bg: 'var(--accent-amber-dim)',  text: 'var(--accent-amber)' },
  };
  const c = colorMap[color] || colorMap.blue;

  return (
    <motion.div
      className="stat-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: delay * 0.1, duration: 0.4 }}
    >
      <div className="stat-icon" style={{ background: c.bg, color: c.text }}>
        <Icon size={20} />
      </div>
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={{ color: c.text }}>{value}</span>
      {change !== undefined && (
        <span className={`stat-change ${change >= 0 ? 'text-profit' : 'text-loss'}`}>
          {change >= 0 ? '▲' : '▼'} {Math.abs(change).toFixed(1)}%
        </span>
      )}
    </motion.div>
  );
}
