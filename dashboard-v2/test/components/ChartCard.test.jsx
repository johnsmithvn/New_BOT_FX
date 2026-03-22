import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import ChartCard from '../../src/components/ChartCard';

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef(({ children, ...props }, ref) => (
      <div ref={ref} {...props}>{children}</div>
    )),
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

describe('ChartCard', () => {
  it('renders title', () => {
    render(<ChartCard title="Equity Curve">content</ChartCard>);
    expect(screen.getByText('Equity Curve')).toBeInTheDocument();
  });

  it('renders children when not loading', () => {
    render(<ChartCard title="Test">Hello World</ChartCard>);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('shows skeleton when loading', () => {
    const { container } = render(
      <ChartCard title="Test" loading={true}>Content</ChartCard>
    );
    expect(container.querySelector('.skeleton')).toBeInTheDocument();
    expect(screen.queryByText('Content')).toBeNull();
  });

  it('renders actions when provided', () => {
    render(
      <ChartCard title="Test" actions={<button>7D</button>}>
        Content
      </ChartCard>
    );
    expect(screen.getByText('7D')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <ChartCard title="Test" className="custom-class">Content</ChartCard>
    );
    expect(container.firstChild.classList.contains('custom-class')).toBe(true);
  });
});
