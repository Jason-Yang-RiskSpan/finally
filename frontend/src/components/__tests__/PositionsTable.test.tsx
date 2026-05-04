import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PositionsTable } from '../PositionsTable';
import type { LivePriceMap, Position } from '@/lib/types';

function pos(over: Partial<Position> = {}): Position {
  return {
    ticker: 'AAPL',
    quantity: 10,
    avg_cost: 100,
    current_price: 110,
    market_value: 1100,
    unrealized_pl: 100,
    unrealized_pl_percent: 10,
    ...over,
  };
}

describe('PositionsTable', () => {
  it('hides zero-quantity rows', () => {
    render(
      <PositionsTable
        positions={[
          pos({ ticker: 'AAPL', quantity: 5 }),
          pos({ ticker: 'GOOGL', quantity: 0 }),
        ]}
        prices={{}}
      />,
    );
    expect(screen.getByTestId('position-row-AAPL')).toBeInTheDocument();
    expect(screen.queryByTestId('position-row-GOOGL')).toBeNull();
  });

  it('uses the live price when available and recomputes P&L', () => {
    const prices: LivePriceMap = {
      AAPL: {
        price: 120,
        previous_price: 119,
        session_open: 100,
        timestamp: 't',
        flash: null,
        flashKey: 0,
        history: [120],
      },
    };
    render(
      <PositionsTable
        positions={[pos({ quantity: 10, avg_cost: 100, current_price: 110 })]}
        prices={prices}
      />,
    );
    const row = screen.getByTestId('position-row-AAPL');
    // P&L = (120 - 100) * 10 = +200
    expect(row).toHaveTextContent('+$200.00');
    expect(row).toHaveTextContent('+20.00%');
  });

  it('shows empty state when no positions', () => {
    render(<PositionsTable positions={[]} prices={{}} />);
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });
});
