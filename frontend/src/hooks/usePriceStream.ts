'use client';

// Native EventSource consumer. Maintains a per-ticker live-price map with:
//   - flash markers (driven by previous price comparison)
//   - rolling sparkline history (capped at SPARK_CAP)
//   - daily change % derived from session_open in the SSE payload
//
// The connection status reflects the underlying EventSource readyState. When
// the browser auto-reconnects, we surface 'connecting' so the header dot can
// turn yellow without us re-implementing exponential backoff.

import { useEffect, useRef, useState } from 'react';
import type { ConnectionStatus, LivePriceMap, PriceTick } from '@/lib/types';

const SPARK_CAP = 60;

export interface UsePriceStreamOptions {
  url?: string;
  // Inject a factory in tests.
  eventSourceFactory?: (url: string) => EventSource;
}

export interface UsePriceStreamResult {
  prices: LivePriceMap;
  status: ConnectionStatus;
  // Most-recent server timestamp seen (for debugging)
  lastEventAt: string | null;
}

function parsePayload(data: string): PriceTick[] {
  if (!data) return [];
  try {
    const parsed = JSON.parse(data);
    if (Array.isArray(parsed)) return parsed as PriceTick[];
    if (parsed && Array.isArray(parsed.prices)) return parsed.prices as PriceTick[];
    // Single tick fallback
    if (parsed && typeof parsed === 'object' && 'ticker' in parsed) {
      return [parsed as PriceTick];
    }
  } catch {
    // ignore malformed events
  }
  return [];
}

export function applyTicks(prev: LivePriceMap, ticks: PriceTick[]): LivePriceMap {
  if (ticks.length === 0) return prev;
  const next: LivePriceMap = { ...prev };
  for (const t of ticks) {
    if (!t || !t.ticker || typeof t.price !== 'number') continue;
    const existing = next[t.ticker];
    const previousPrice =
      typeof t.previous_price === 'number'
        ? t.previous_price
        : existing?.price ?? null;
    let flash: 'up' | 'down' | null = null;
    if (previousPrice != null && previousPrice !== t.price) {
      flash = t.price > previousPrice ? 'up' : 'down';
    }
    const history = existing?.history ? existing.history.slice(-(SPARK_CAP - 1)) : [];
    history.push(t.price);
    next[t.ticker] = {
      price: t.price,
      previous_price: previousPrice,
      session_open:
        typeof t.session_open === 'number'
          ? t.session_open
          : existing?.session_open ?? t.price,
      timestamp: t.timestamp,
      flash,
      flashKey: (existing?.flashKey ?? 0) + (flash ? 1 : 0),
      history,
    };
  }
  return next;
}

export function usePriceStream(opts: UsePriceStreamOptions = {}): UsePriceStreamResult {
  const url = opts.url ?? '/api/stream/prices';
  const [prices, setPrices] = useState<LivePriceMap>({});
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const factory =
      opts.eventSourceFactory ?? ((u: string) => new EventSource(u));
    const es = factory(url);
    esRef.current = es;
    setStatus('connecting');

    const onOpen = () => setStatus('connected');
    const onError = () => {
      // EventSource auto-reconnects; reflect that as 'connecting' unless the
      // connection is fully closed (readyState === 2).
      if (es.readyState === EventSource.CLOSED) {
        setStatus('disconnected');
      } else {
        setStatus('connecting');
      }
    };
    const onMessage = (ev: MessageEvent) => {
      const ticks = parsePayload(ev.data);
      if (ticks.length === 0) return;
      setLastEventAt(ticks[ticks.length - 1]?.timestamp ?? new Date().toISOString());
      setPrices((prev) => applyTicks(prev, ticks));
    };

    es.addEventListener('open', onOpen);
    es.addEventListener('error', onError);
    es.addEventListener('message', onMessage);

    return () => {
      es.removeEventListener('open', onOpen);
      es.removeEventListener('error', onError);
      es.removeEventListener('message', onMessage);
      es.close();
    };
    // We intentionally only re-run on url change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return { prices, status, lastEventAt };
}
