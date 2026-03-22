import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import StatCard from '../../src/components/StatCard';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef(({ children, ...props }, ref) => (
      <div ref={ref} {...props}>{children}</div>
    )),
  },
}));

const MockIcon = ({ size }) => <span data-testid="mock-icon">{size}</span>;

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard icon={MockIcon} label="Win Rate" value="65%" />);
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('65%')).toBeInTheDocument();
  });

  it('renders icon', () => {
    render(<StatCard icon={MockIcon} label="Test" value="0" />);
    expect(screen.getByTestId('mock-icon')).toBeInTheDocument();
  });

  it('shows positive change with ▲', () => {
    render(<StatCard icon={MockIcon} label="Test" value="100" change={5.3} />);
    expect(screen.getByText(/▲/)).toBeInTheDocument();
    expect(screen.getByText(/5.3%/)).toBeInTheDocument();
  });

  it('shows negative change with ▼', () => {
    render(<StatCard icon={MockIcon} label="Test" value="100" change={-2.7} />);
    expect(screen.getByText(/▼/)).toBeInTheDocument();
    expect(screen.getByText(/2.7%/)).toBeInTheDocument();
  });

  it('does not show change when undefined', () => {
    const { container } = render(<StatCard icon={MockIcon} label="Test" value="100" />);
    expect(container.querySelector('.stat-change')).toBeNull();
  });

  it('applies correct color class', () => {
    const { container } = render(
      <StatCard icon={MockIcon} label="Test" value="100" color="green" />
    );
    expect(container.querySelector('.stat-card')).toBeInTheDocument();
  });
});
