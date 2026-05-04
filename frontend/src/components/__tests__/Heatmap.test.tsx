import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Heatmap, buildTiles } from '../Heatmap';
import type { Position } from '@/lib/types';

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

describe('Heatmap.buildTiles', () => {
  it('100% cash user: cash tile present and is the only tile', () => {
    const tiles = buildTiles([], 10000, 10000);
    expect(tiles).toHaveLength(1);
    expect(tiles[0].isCash).toBe(true);
    expect(tiles[0].value).toBe(10000);
  });

  it('mixed portfolio: one tile per position plus cash', () => {
    const tiles = buildTiles(
      [pos({ ticker: 'AAPL', market_value: 1100 }), pos({ ticker: 'GOOGL', market_value: 500 })],
      8400,
      10000,
    );
    expect(tiles.map((t) => t.key).sort()).toEqual(
      ['AAPL', 'CASH', 'GOOGL'].sort(),
    );
    const cash = tiles.find((t) => t.isCash);
    expect(cash?.value).toBe(8400);
  });

  it('no cash and positions: omits cash tile', () => {
    const tiles = buildTiles([pos({ market_value: 1000 })], 0, 1000);
    expect(tiles.find((t) => t.isCash)).toBeUndefined();
  });

  it('zero market value position is skipped', () => {
    const tiles = buildTiles(
      [pos({ ticker: 'ZERO', market_value: 0 })],
      1000,
      1000,
    );
    expect(tiles.find((t) => t.key === 'ZERO')).toBeUndefined();
    expect(tiles.find((t) => t.isCash)).toBeDefined();
  });
});

describe('Heatmap render', () => {
  it('renders cash tile for a 100%-cash user', () => {
    render(<Heatmap positions={[]} cashBalance={10000} totalValue={10000} />);
    expect(screen.getByTestId('heat-tile-CASH')).toBeInTheDocument();
  });

  it('renders both position tiles and the cash tile in a mixed portfolio', () => {
    render(
      <Heatmap
        positions={[
          pos({ ticker: 'AAPL', market_value: 1100 }),
          pos({ ticker: 'GOOGL', market_value: 500 }),
        ]}
        cashBalance={8400}
        totalValue={10000}
      />,
    );
    expect(screen.getByTestId('heat-tile-AAPL')).toBeInTheDocument();
    expect(screen.getByTestId('heat-tile-GOOGL')).toBeInTheDocument();
    expect(screen.getByTestId('heat-tile-CASH')).toBeInTheDocument();
  });
});
