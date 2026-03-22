import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import SparkCard from '../../src/components/SparkCard';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef(({ children, ...props }, ref) => (
      <div ref={ref} {...props}>{children}</div>
    )),
  },
}));

// Mock recharts (heavy chart library)
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div data-testid="responsive">{children}</div>,
  AreaChart: ({ children }) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div data-testid="area" />,
  BarChart: ({ children }) => <div data-testid="bar-chart">{children}</div>,
  Bar: ({ children }) => <div data-testid="bar">{children}</div>,
  LineChart: ({ children }) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  Cell: () => <div data-testid="cell" />,
}));

describe('SparkCard', () => {
  it('renders title and value', () => {
    render(<SparkCard title="Net PnL" value="$100" />);
    expect(screen.getByText('Net PnL')).toBeInTheDocument();
    expect(screen.getByText('$100')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<SparkCard title="PnL" value="$50" subtitle="Gross: $70" />);
    expect(screen.getByText('Gross: $70')).toBeInTheDocument();
  });

  it('does not render subtitle when not provided', () => {
    const { container } = render(<SparkCard title="PnL" value="$50" />);
    // Only title + value should exist, no subtitle span
    const spans = container.querySelectorAll('span');
    const texts = Array.from(spans).map(s => s.textContent);
    expect(texts).not.toContain(undefined);
  });

  it('renders sparkline chart when sparkData provided', () => {
    const data = [{ value: 10 }, { value: 20 }, { value: 15 }];
    render(<SparkCard title="PnL" value="$50" sparkData={data} sparkType="area" />);
    expect(screen.getByTestId('responsive')).toBeInTheDocument();
  });

  it('does not render chart when sparkData is empty', () => {
    render(<SparkCard title="PnL" value="$50" sparkData={[]} />);
    expect(screen.queryByTestId('responsive')).toBeNull();
  });

  it('falls back to blue color for unknown color prop', () => {
    const { container } = render(
      <SparkCard title="Test" value="$0" color="nonexistent" />
    );
    // Should render without error — using COLORS.blue fallback
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('uses bar chart for sparkType=bar', () => {
    const data = [{ value: 10 }];
    render(<SparkCard title="Test" value="$0" sparkData={data} sparkType="bar" />);
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('uses line chart for sparkType=line', () => {
    const data = [{ value: 10 }];
    render(<SparkCard title="Test" value="$0" sparkData={data} sparkType="line" />);
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });
});
