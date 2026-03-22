import { useState, useEffect, useCallback } from 'react';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

export default function Settings() {
  const [apiUrl] = useState(import.meta.env.VITE_API_URL || window.location.origin);
  const [apiKey, setApiKey] = useState(localStorage.getItem('dashboard_api_key') || '');
  const [connStatus, setConnStatus] = useState('checking'); // 'online' | 'offline' | 'checking'
  const [lastCheck, setLastCheck] = useState(null);

  const checkConnection = useCallback(async () => {
    setConnStatus('checking');
    try {
      await api.overview();
      setConnStatus('online');
    } catch {
      setConnStatus('offline');
    }
    setLastCheck(new Date().toLocaleTimeString());
  }, []);

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  const saveKey = () => {
    if (apiKey) {
      localStorage.setItem('dashboard_api_key', apiKey);
    } else {
      localStorage.removeItem('dashboard_api_key');
    }
    // Re-check connection with new key
    checkConnection();
  };

  const isOnline = connStatus === 'online';
  const isChecking = connStatus === 'checking';

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Dashboard configuration and connection status</p>
      </div>

      <div style={{ display: 'grid', gap: '1.5rem', maxWidth: 600 }}>
        {/* Connection Status */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Connection</span>
            <button
              className="btn btn-ghost"
              onClick={checkConnection}
              disabled={isChecking}
              style={{ padding: '4px 8px', fontSize: '0.75rem' }}
            >
              <RefreshCw size={14} className={isChecking ? 'spin' : ''} />
              {isChecking ? 'Checking…' : 'Refresh'}
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            {isOnline
              ? <Wifi size={18} style={{ color: 'var(--accent-green)' }} />
              : <WifiOff size={18} style={{ color: 'var(--accent-red)' }} />
            }
            <span style={{ fontSize: '0.875rem' }}>API Server</span>
            <span className={`badge ${isOnline ? 'badge-profit' : 'badge-loss'}`}>
              {isChecking ? 'Checking…' : isOnline ? 'Connected' : 'Offline'}
            </span>
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            <p>URL: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)' }}>{apiUrl}</code></p>
            {lastCheck && (
              <p style={{ marginTop: 4, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Last checked: {lastCheck}
              </p>
            )}
          </div>
        </div>

        {/* API Key */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">API Key</span>
          </div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 12 }}>
            If your dashboard API requires an X-API-Key header, set it here.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="password"
              className="input"
              style={{ flex: 1 }}
              placeholder="Enter API key..."
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
            />
            <button className="btn btn-primary" onClick={saveKey}>Save</button>
          </div>
        </div>

        {/* About */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">About</span>
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <p><strong>Dashboard V2</strong> — React SPA</p>
            <p>Version: 0.16.2</p>
            <p>Tech: React + Vite + Recharts + TanStack Query</p>
            <p>Auto-refresh: 30 seconds</p>
          </div>
        </div>
      </div>
    </div>
  );
}
