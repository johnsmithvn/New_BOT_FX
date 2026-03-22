import { motion } from 'framer-motion';

export default function ChartCard({ title, children, actions, loading, className = '' }) {
  return (
    <motion.div
      className={`card ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      style={{ display: 'flex', flexDirection: 'column', minHeight: 320 }}
    >
      <div className="card-header">
        <span className="card-title">{title}</span>
        {actions && <div style={{ display: 'flex', gap: 4 }}>{actions}</div>}
      </div>
      <div className="chart-body" style={{ flex: 1, minHeight: 0 }}>
        {loading ? (
          <div className="skeleton skeleton-chart" style={{ height: '100%' }} />
        ) : (
          children
        )}
      </div>
    </motion.div>
  );
}
