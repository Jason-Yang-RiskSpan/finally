import { describe, expect, it, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { Watchlist } from '../Watchlist';
import type { LivePriceMap } from '@/lib/types';

function makePrices(): LivePriceMap {
  return {
    AAPL: {
      price: 191.42,
      previous_price: 190.0,
      session_open: 188.0,
      timestamp: '2026-05-03T13:00:00Z',
      flash: 'up',
      flashKey: 1,
      history: [188, 189, 190, 191.42],
    },
    GOOGL: {
      price: 175.0,
      previous_price: 175.5,
      session_open: 176.0,
      timestamp: '2026-05-03T13:00:00Z',
      flash: 'down',
      flashKey: 1,
      history: [176, 175.8, 175.5, 175.0],
    },
  };
}

describe('Watchlist', () => {
  it('renders rows with ticker, price, and daily change %', () => {
    render(
      <Watchlist
        tickers={['AAPL', 'GOOGL']}
        prices={makePrices()}
        selected="AAPL"
        onSelect={() => {}}
        onAdd={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByTestId('watchlist-row-AAPL')).toBeInTheDocument();
    expect(screen.getByTestId('price-AAPL')).toHaveTextContent('191.42');
    // (191.42 - 188) / 188 = +1.82%
    expect(screen.getByTestId('daily-pct-AAPL')).toHaveTextContent('+1.82%');
    // GOOGL: (175 - 176) / 176 = -0.57%
    expect(screen.getByTestId('daily-pct-GOOGL')).toHaveTextContent('-0.57%');
  });

  it('applies flash-up class when flash is up and clears it after 500ms', () => {
    vi.useFakeTimers();
    try {
      render(
        <Watchlist
          tickers={['AAPL']}
          prices={makePrices()}
          selected={null}
          onSelect={() => {}}
          onAdd={() => {}}
          onRemove={() => {}}
        />,
      );
      const cell = screen.getByTestId('price-AAPL');
      expect(cell.className).toContain('flash-up');
      act(() => {
        vi.advanceTimersByTime(600);
      });
      expect(cell.className).not.toContain('flash-up');
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders sparkline with accumulated points', () => {
    render(
      <Watchlist
        tickers={['AAPL']}
        prices={makePrices()}
        selected={null}
        onSelect={() => {}}
        onAdd={() => {}}
        onRemove={() => {}}
      />,
    );
    const sparks = screen.getAllByTestId('sparkline');
    expect(sparks[0].getAttribute('data-points')).toBe('4');
  });
});
