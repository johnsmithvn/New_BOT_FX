import { useState } from 'react';
import { Wifi, WifiOff, RefreshCw, Info } from 'lucide-react';

export default function Settings() {
  const [apiUrl] = useState(import.meta.env.VITE_API_URL || window.location.origin);
  const [apiKey, setApiKey] = useState(localStorage.getItem('dashboard_api_key') || '');

  const saveKey = () => {
    if (apiKey) {
      localStorage.setItem('dashboard_api_key', apiKey);
    } else {
      localStorage.removeItem('dashboard_api_key');
    }
  };

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
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <Wifi size={18} style={{ color: 'var(--accent-green)' }} />
            <span style={{ fontSize: '0.875rem' }}>API Server</span>
            <span className="badge badge-profit">Connected</span>
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            <p>URL: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)' }}>{apiUrl}</code></p>
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
            <p>Version: 0.15.0</p>
            <p>Tech: React + Vite + Recharts + TanStack Query</p>
            <p>Auto-refresh: 30 seconds</p>
          </div>
        </div>
      </div>
    </div>
  );
}
