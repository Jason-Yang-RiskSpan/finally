import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Header } from '../Header';

describe('Header', () => {
  it('renders totals and connection status', () => {
    render(
      <Header
        totalValue={10523.45}
        cashBalance={8000}
        unrealizedPnl={523.45}
        connection="connected"
      />,
    );
    expect(screen.getByTestId('total-value')).toHaveTextContent('$10,523.45');
    expect(screen.getByTestId('cash-balance')).toHaveTextContent('$8,000.00');
    expect(screen.getByTestId('unrealized-pnl')).toHaveTextContent('+$523.45');
    const dot = screen.getByTestId('connection-status');
    expect(dot.getAttribute('data-status')).toBe('connected');
  });

  it('reflects connecting and disconnected states', () => {
    const { rerender } = render(
      <Header totalValue={0} cashBalance={0} unrealizedPnl={0} connection="connecting" />,
    );
    expect(screen.getByTestId('connection-status').getAttribute('data-status')).toBe(
      'connecting',
    );
    rerender(
      <Header totalValue={0} cashBalance={0} unrealizedPnl={0} connection="disconnected" />,
    );
    expect(screen.getByTestId('connection-status').getAttribute('data-status')).toBe(
      'disconnected',
    );
  });
});
