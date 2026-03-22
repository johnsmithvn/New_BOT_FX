import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { PremiumTooltip, BarLabel, PieLabel } from '../../src/charts/ChartPrimitives';

/* ─── PremiumTooltip ──────────────────────────────────────── */
describe('PremiumTooltip', () => {
  it('returns null when not active', () => {
    const { container } = render(
      <PremiumTooltip active={false} payload={[]} label="test" />
    );
    expect(container.firstChild).toBeNull();
  });

  it('returns null when payload is empty', () => {
    const { container } = render(
      <PremiumTooltip active={true} payload={[]} label="test" />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders tooltip with label and payload rows', () => {
    const payload = [
      { value: 100, name: 'PnL', color: '#22c55e' },
      { value: -50, name: 'Commission', color: '#ef4444' },
    ];
    const { container } = render(
      <PremiumTooltip active={true} payload={payload} label="2026-03-01" />
    );
    expect(screen.getByText('2026-03-01')).toBeInTheDocument();
    expect(screen.getByText('PnL')).toBeInTheDocument();
    expect(screen.getByText('Commission')).toBeInTheDocument();
  });

  it('applies profit class for positive value', () => {
    const payload = [{ value: 50, name: 'PnL', color: '#22c55e' }];
    const { container } = render(
      <PremiumTooltip active={true} payload={payload} label="test" />
    );
    const valueEl = container.querySelector('.tooltip-value');
    expect(valueEl.classList.contains('profit')).toBe(true);
  });

  it('applies loss class for negative value', () => {
    const payload = [{ value: -50, name: 'PnL', color: '#ef4444' }];
    const { container } = render(
      <PremiumTooltip active={true} payload={payload} label="test" />
    );
    const valueEl = container.querySelector('.tooltip-value');
    expect(valueEl.classList.contains('loss')).toBe(true);
  });

  it('applies neutral class for zero value', () => {
    const payload = [{ value: 0, name: 'PnL', color: '#ccc' }];
    const { container } = render(
      <PremiumTooltip active={true} payload={payload} label="test" />
    );
    const valueEl = container.querySelector('.tooltip-value');
    expect(valueEl.classList.contains('neutral')).toBe(true);
  });

  it('uses custom formatter', () => {
    const payload = [{ value: 42, name: 'PnL', color: '#22c55e' }];
    const formatter = (v) => `${v} pips`;
    render(
      <PremiumTooltip active={true} payload={payload} label="test" formatter={formatter} />
    );
    expect(screen.getByText('42 pips')).toBeInTheDocument();
  });

  it('shows total when showTotal is true', () => {
    const payload = [
      { value: 100, name: 'A', color: '#22c55e' },
      { value: -30, name: 'B', color: '#ef4444' },
    ];
    const { container } = render(
      <PremiumTooltip active={true} payload={payload} label="test" showTotal={true} />
    );
    const footer = container.querySelector('.tooltip-footer');
    expect(footer).toBeTruthy();
    // Total = 100 + (-30) = 70
    expect(footer.textContent).toContain('70.00');
  });
});

/* ─── BarLabel ─────────────────────────────────────────────── */
describe('BarLabel', () => {
  // BarLabel returns SVG <text> element, we test via render in <svg>
  it('returns null for value = 0', () => {
    const result = BarLabel({ x: 10, y: 20, width: 30, value: 0 });
    expect(result).toBeNull();
  });

  it('returns null for value = null', () => {
    const result = BarLabel({ x: 10, y: 20, width: 30, value: null });
    expect(result).toBeNull();
  });

  it('formats value >= 1000 as k', () => {
    const el = BarLabel({ x: 10, y: 20, width: 30, value: 1500 });
    // value/1000 = 1.5, toFixed(1) = "1.5"
    expect(el.props.children).toContain('1.5k');
  });

  it('formats small value with 1 decimal', () => {
    const el = BarLabel({ x: 10, y: 20, width: 30, value: 42.67 });
    expect(el.props.children).toContain('42.7');
  });

  it('positions above bar for positive values', () => {
    const el = BarLabel({ x: 10, y: 50, width: 30, value: 10 });
    expect(el.props.y).toBe(44); // y - 6
  });

  it('positions below bar for negative values', () => {
    const el = BarLabel({ x: 10, y: 50, width: 30, value: -10 });
    expect(el.props.y).toBe(66); // y + 16
  });
});

/* ─── PieLabel ─────────────────────────────────────────────── */
describe('PieLabel', () => {
  const baseProps = {
    cx: 100, cy: 100, midAngle: 90,
    innerRadius: 40, outerRadius: 60,
    percent: 0.5, value: 10, name: 'Wins',
  };

  it('returns null when percent < 0.05', () => {
    const result = PieLabel({ ...baseProps, percent: 0.04 });
    expect(result).toBeNull();
  });

  it('renders label text for visible slices', () => {
    const el = PieLabel(baseProps);
    expect(el).not.toBeNull();
    // Children is array: ['Wins', ' (', '50', '%)']
    const text = [].concat(el.props.children).join('');
    expect(text).toContain('Wins');
    expect(text).toContain('50%');
  });

  it('sets textAnchor based on x position relative to cx', () => {
    // midAngle=0 → x > cx → textAnchor = 'start'
    const el = PieLabel({ ...baseProps, midAngle: 0 });
    expect(el.props.textAnchor).toBe('start');
  });
});
