import { describe, expect, it } from 'vitest';
import { applyTicks } from '../usePriceStream';
import type { LivePriceMap } from '@/lib/types';

describe('applyTicks (sparkline accumulation)', () => {
  it('appends to history and flags flash direction', () => {
    let state: LivePriceMap = {};
    state = applyTicks(state, [
      {
        ticker: 'AAPL',
        price: 100,
        session_open: 100,
        timestamp: '2026-05-03T13:00:00Z',
        previous_price: null,
      },
    ]);
    expect(state.AAPL.history).toEqual([100]);
    expect(state.AAPL.flash).toBeNull();

    state = applyTicks(state, [
      {
        ticker: 'AAPL',
        price: 101,
        session_open: 100,
        timestamp: '2026-05-03T13:00:01Z',
        previous_price: 100,
      },
    ]);
    expect(state.AAPL.history).toEqual([100, 101]);
    expect(state.AAPL.flash).toBe('up');

    state = applyTicks(state, [
      {
        ticker: 'AAPL',
        price: 99.5,
        session_open: 100,
        timestamp: '2026-05-03T13:00:02Z',
        previous_price: 101,
      },
    ]);
    expect(state.AAPL.history).toEqual([100, 101, 99.5]);
    expect(state.AAPL.flash).toBe('down');
  });

  it('caps history length', () => {
    let state: LivePriceMap = {};
    for (let i = 0; i < 80; i++) {
      state = applyTicks(state, [
        {
          ticker: 'AAPL',
          price: 100 + i,
          session_open: 100,
          timestamp: 'ts',
          previous_price: 100 + i - 1,
        },
      ]);
    }
    expect(state.AAPL.history.length).toBeLessThanOrEqual(60);
    expect(state.AAPL.history[state.AAPL.history.length - 1]).toBe(179);
  });

  it('handles a batch of ticks for multiple tickers', () => {
    const state = applyTicks({}, [
      { ticker: 'AAPL', price: 1, session_open: 1, timestamp: 't' },
      { ticker: 'GOOGL', price: 2, session_open: 2, timestamp: 't' },
    ]);
    expect(Object.keys(state)).toEqual(['AAPL', 'GOOGL']);
  });
});
