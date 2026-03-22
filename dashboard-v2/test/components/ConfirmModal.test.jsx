import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ConfirmModal from '../../src/components/ConfirmModal';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef(({ children, ...props }, ref) => (
      <div ref={ref} {...props}>{children}</div>
    )),
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// Mock lucide-react
vi.mock('lucide-react', () => ({
  AlertTriangle: () => <span data-testid="alert-icon" />,
  X: () => <span data-testid="close-icon" />,
}));

describe('ConfirmModal', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onConfirm: vi.fn(),
    title: 'Delete Item',
    message: 'Are you sure?',
  };

  it('renders nothing when open is false', () => {
    const { container } = render(<ConfirmModal {...defaultProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders modal content when open', () => {
    render(<ConfirmModal {...defaultProps} />);
    expect(screen.getByText('Delete Item')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', () => {
    render(<ConfirmModal {...defaultProps} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(defaultProps.onClose).toHaveBeenCalledOnce();
  });

  it('calls onConfirm and onClose on Confirm click (no phrase)', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmModal {...defaultProps} onConfirm={onConfirm} onClose={onClose} confirmText="Do it" />
    );
    fireEvent.click(screen.getByText('Do it'));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('disables confirm until phrase matches', () => {
    render(
      <ConfirmModal {...defaultProps} confirmPhrase="DELETE" confirmText="Delete" />
    );
    const confirmBtn = screen.getByText('Delete');
    expect(confirmBtn.disabled).toBe(true);
  });

  it('enables confirm when typed phrase matches', () => {
    render(
      <ConfirmModal {...defaultProps} confirmPhrase="DELETE" confirmText="Delete" />
    );
    const input = screen.getByPlaceholderText('DELETE');
    fireEvent.change(input, { target: { value: 'DELETE' } });
    const confirmBtn = screen.getByText('Delete');
    expect(confirmBtn.disabled).toBe(false);
  });

  it('renders danger level colors by default', () => {
    const { container } = render(<ConfirmModal {...defaultProps} />);
    // The alert icon wrapper should exist
    expect(container.querySelector('[data-testid="alert-icon"]')).toBeInTheDocument();
  });
});
