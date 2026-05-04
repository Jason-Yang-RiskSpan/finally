// Tests the EventSource lifecycle: open, message, error → status transitions.
// We inject a stub EventSource via the hook factory option.

import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { usePriceStream } from '../usePriceStream';

class StubEventSource {
  static CLOSED = 2;
  static OPEN = 1;
  static CONNECTING = 0;
  url: string;
  readyState = StubEventSource.CONNECTING;
  listeners: Record<string, Array<(ev: any) => void>> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
  }
  addEventListener(name: string, fn: (ev: any) => void) {
    (this.listeners[name] ||= []).push(fn);
  }
  removeEventListener(name: string, fn: (ev: any) => void) {
    this.listeners[name] = (this.listeners[name] || []).filter((f) => f !== fn);
  }
  dispatch(name: string, ev: any) {
    (this.listeners[name] || []).forEach((fn) => fn(ev));
  }
  close() {
    this.readyState = StubEventSource.CLOSED;
    this.closed = true;
  }
}

// jsdom doesn't define EventSource constants used in the hook's error branch.
// @ts-expect-error attach to global
globalThis.EventSource = StubEventSource;

describe('usePriceStream lifecycle', () => {
  it('connecting → connected on open, applies messages', () => {
    let stub: StubEventSource | null = null;
    const factory = (u: string) => {
      stub = new StubEventSource(u);
      return stub as unknown as EventSource;
    };
    const { result } = renderHook(() =>
      usePriceStream({ eventSourceFactory: factory }),
    );
    expect(result.current.status).toBe('connecting');

    act(() => {
      stub!.readyState = StubEventSource.OPEN;
      stub!.dispatch('open', {});
    });
    expect(result.current.status).toBe('connected');

    act(() => {
      stub!.dispatch('message', {
        data: JSON.stringify({
          prices: [
            {
              ticker: 'AAPL',
              price: 200,
              session_open: 198,
              timestamp: 't',
              previous_price: 199,
            },
          ],
        }),
      });
    });
    expect(result.current.prices.AAPL.price).toBe(200);
    expect(result.current.prices.AAPL.flash).toBe('up');
  });

  it('error with non-CLOSED state shows connecting (auto-reconnect)', () => {
    let stub: StubEventSource | null = null;
    const factory = (u: string) => {
      stub = new StubEventSource(u);
      return stub as unknown as EventSource;
    };
    const { result } = renderHook(() =>
      usePriceStream({ eventSourceFactory: factory }),
    );
    act(() => {
      stub!.readyState = StubEventSource.OPEN;
      stub!.dispatch('open', {});
    });
    act(() => {
      stub!.readyState = StubEventSource.CONNECTING;
      stub!.dispatch('error', {});
    });
    expect(result.current.status).toBe('connecting');
  });

  it('error with CLOSED state shows disconnected', () => {
    let stub: StubEventSource | null = null;
    const factory = (u: string) => {
      stub = new StubEventSource(u);
      return stub as unknown as EventSource;
    };
    const { result } = renderHook(() =>
      usePriceStream({ eventSourceFactory: factory }),
    );
    act(() => {
      stub!.readyState = StubEventSource.CLOSED;
      stub!.dispatch('error', {});
    });
    expect(result.current.status).toBe('disconnected');
  });

  it('closes the EventSource on unmount', () => {
    let stub: StubEventSource | null = null;
    const factory = (u: string) => {
      stub = new StubEventSource(u);
      return stub as unknown as EventSource;
    };
    const { unmount } = renderHook(() =>
      usePriceStream({ eventSourceFactory: factory }),
    );
    unmount();
    expect(stub!.closed).toBe(true);
  });
});
