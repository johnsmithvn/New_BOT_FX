import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, X } from 'lucide-react';

/**
 * Shared confirmation modal (popup, not window.alert).
 *
 * @param {object} props
 * @param {boolean} props.open           - visible?
 * @param {function} props.onClose       - cancel callback
 * @param {function} props.onConfirm     - confirm callback
 * @param {string} props.title           - modal title
 * @param {string} props.message         - body text / description
 * @param {string} [props.confirmText]   - button label (default "Confirm")
 * @param {string} [props.confirmPhrase] - if set, user must type this to enable confirm
 * @param {'danger'|'warning'|'info'} [props.level] - severity (default 'danger')
 */
export default function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title = 'Confirm action',
  message = 'Are you sure?',
  confirmText = 'Confirm',
  confirmPhrase = '',
  level = 'danger',
}) {
  const [typed, setTyped] = useState('');

  useEffect(() => {
    if (!open) setTyped('');
  }, [open]);

  const canConfirm = !confirmPhrase || typed === confirmPhrase;

  const levelColors = {
    danger: { bg: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', icon: '#ef4444', btn: '#ef4444' },
    warning: { bg: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', icon: '#f59e0b', btn: '#f59e0b' },
    info: { bg: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.25)', icon: '#3b82f6', btn: '#3b82f6' },
  };
  const c = levelColors[level] || levelColors.danger;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(4px)',
          }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.92, opacity: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            onClick={e => e.stopPropagation()}
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 16,
              padding: '1.75rem',
              maxWidth: 440,
              width: '92%',
              boxShadow: '0 24px 48px rgba(0,0,0,0.3)',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: c.bg, border: c.border,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <AlertTriangle size={18} color={c.icon} />
                </div>
                <span style={{ fontSize: '1.0625rem', fontWeight: 700, color: 'var(--text-primary)' }}>{title}</span>
              </div>
              <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
                <X size={18} />
              </button>
            </div>

            {/* Body */}
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: confirmPhrase ? 16 : 24 }}>
              {message}
            </p>

            {/* Type-to-confirm */}
            {confirmPhrase && (
              <div style={{ marginBottom: 20 }}>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                  Type <code style={{ color: c.icon, fontWeight: 700, background: c.bg, padding: '2px 6px', borderRadius: 4 }}>{confirmPhrase}</code> to confirm:
                </p>
                <input
                  type="text"
                  value={typed}
                  onChange={e => setTyped(e.target.value)}
                  placeholder={confirmPhrase}
                  autoFocus
                  className="input"
                  style={{ width: '100%', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}
                />
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={onClose} style={{ padding: '8px 20px' }}>
                Cancel
              </button>
              <button
                disabled={!canConfirm}
                onClick={() => { onConfirm(); onClose(); }}
                style={{
                  padding: '8px 20px',
                  borderRadius: 8,
                  fontWeight: 600,
                  fontSize: '0.8125rem',
                  border: 'none',
                  cursor: canConfirm ? 'pointer' : 'not-allowed',
                  background: canConfirm ? c.btn : 'var(--bg-tertiary)',
                  color: canConfirm ? '#fff' : 'var(--text-muted)',
                  opacity: canConfirm ? 1 : 0.5,
                  transition: 'all 0.15s',
                }}
              >
                {confirmText}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
