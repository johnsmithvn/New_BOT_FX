import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Navbar from '../../src/components/Navbar';

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  BarChart3: () => <span data-testid="icon-barchart" />,
  LayoutDashboard: () => <span data-testid="icon-dashboard" />,
  LineChart: () => <span data-testid="icon-linechart" />,
  Radio: () => <span data-testid="icon-radio" />,
  BookOpen: () => <span data-testid="icon-bookopen" />,
  Settings: () => <span data-testid="icon-settings" />,
  Layers: () => <span data-testid="icon-layers" />,
  GitBranch: () => <span data-testid="icon-gitbranch" />,
}));

describe('Navbar', () => {
  function renderNavbar() {
    return render(
      <MemoryRouter initialEntries={['/']}>
        <Navbar />
      </MemoryRouter>
    );
  }

  it('renders brand text', () => {
    renderNavbar();
    expect(screen.getByText('Forex Bot')).toBeInTheDocument();
    expect(screen.getByText('V2')).toBeInTheDocument();
  });

  it('renders all 7 navigation links', () => {
    renderNavbar();
    const links = ['Overview', 'Analytics', 'Channels', 'Symbols', 'Trades', 'Signals', 'Settings'];
    links.forEach(label => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it('renders Live status indicator', () => {
    renderNavbar();
    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('has correct link hrefs', () => {
    renderNavbar();
    const overviewLink = screen.getByText('Overview').closest('a');
    expect(overviewLink.getAttribute('href')).toBe('/');

    const analyticsLink = screen.getByText('Analytics').closest('a');
    expect(analyticsLink.getAttribute('href')).toBe('/analytics');
  });
});
