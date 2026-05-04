'use client';

// Market-order trade bar. Buy and Sell post to /api/portfolio/trade.

import { useState } from 'react';
import type { LivePriceMap } from '@/lib/types';
import { fmtCurrency, fmtPrice } from '@/lib/format';

interface TradeBarProps {
  selected: string | null;
  prices: LivePriceMap;
  onTrade: (side: 'buy' | 'sell', ticker: string, quantity: number) => Promise<void>;
}

export function TradeBar({ selected, prices, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState('');
  const [qty, setQty] = useState('1');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Auto-fill ticker when one is selected and the input is empty.
  const effectiveTicker = (ticker || selected || '').trim().toUpperCase();
  const live = effectiveTicker ? prices[effectiveTicker] : undefined;
  const qtyNum = Number(qty);
  const estCost = live && qtyNum > 0 ? live.price * qtyNum : null;

  async function go(side: 'buy' | 'sell') {
    setError(null);
    setSuccess(null);
    if (!effectiveTicker || !qtyNum || qtyNum <= 0) {
      setError('Enter a ticker and a positive quantity.');
      return;
    }
    setBusy(true);
    try {
      await onTrade(side, effectiveTicker, qtyNum);
      setSuccess(`${side.toUpperCase()} ${qtyNum} ${effectiveTicker}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trade failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" data-testid="trade-bar">
      <div className="panel-header">
        <span>Trade</span>
        {live && (
          <span className="text-slate-300 normal-case tracking-normal">
            {effectiveTicker} @ {fmtPrice(live.price)}
          </span>
        )}
      </div>
      <div className="p-2 grid grid-cols-[1fr_1fr_auto_auto] gap-2 items-center">
        <input
          aria-label="trade-ticker"
          className="input"
          placeholder={selected || 'TICKER'}
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          maxLength={5}
        />
        <input
          aria-label="trade-quantity"
          className="input"
          inputMode="decimal"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />
        <button
          type="button"
          className="btn btn-buy"
          disabled={busy}
          onClick={() => go('buy')}
        >
          BUY
        </button>
        <button
          type="button"
          className="btn btn-sell"
          disabled={busy}
          onClick={() => go('sell')}
        >
          SELL
        </button>
      </div>
      <div className="px-2 pb-2 text-[11px] flex items-center justify-between">
        <span className="text-slate-500">
          {estCost != null ? `Est. cost ${fmtCurrency(estCost)}` : 'Market order, instant fill'}
        </span>
        {error && <span className="text-down" role="alert">{error}</span>}
        {success && !error && (
          <span className="text-up" role="status">
            {success}
          </span>
        )}
      </div>
    </section>
  );
}
