import { NavLink } from 'react-router-dom';
import { BarChart3, LayoutDashboard, LineChart, Radio, BookOpen, Settings, Layers } from 'lucide-react';

const links = [
  { to: '/',          icon: LayoutDashboard, label: 'Overview' },
  { to: '/analytics', icon: LineChart,       label: 'Analytics' },
  { to: '/channels',  icon: Radio,           label: 'Channels' },
  { to: '/symbols',   icon: Layers,          label: 'Symbols' },
  { to: '/trades',    icon: BookOpen,        label: 'Trades' },
  { to: '/settings',  icon: Settings,        label: 'Settings' },
];

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="nav-brand">
        <div className="nav-brand-icon">
          <BarChart3 size={18} />
        </div>
        <span className="nav-brand-text">Forex Bot</span>
        <span className="nav-brand-tag">V2</span>
      </div>

      <div className="nav-links">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </div>

      <div className="nav-status">
        <span className="status-dot" />
        <span className="status-text">Live</span>
      </div>
    </nav>
  );
}
