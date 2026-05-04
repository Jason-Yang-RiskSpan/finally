'use client';

// Watchlist grid. Each row computes daily change % from the session_open
// included in the SSE payload — no separate fetch.

import { useState } from 'react';
import { Sparkline } from './Sparkline';
import { useFlashClass } from '@/hooks/useFlashClass';
import { fmtPct, fmtPrice, pnlColor } from '@/lib/format';
import type { LivePrice, LivePriceMap } from '@/lib/types';

interface WatchlistProps {
  tickers: string[];
  prices: LivePriceMap;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void> | void;
  onRemove: (ticker: string) => Promise<void> | void;
}

interface WatchlistRowProps {
  ticker: string;
  live: LivePrice | undefined;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}

function WatchlistRow({
  ticker,
  live,
  selected,
  onSelect,
  onRemove,
}: WatchlistRowProps) {
  const flashClass = useFlashClass(live?.flash ?? null, live?.flashKey ?? 0);
  const dailyPct =
    live && live.session_open
      ? ((live.price - live.session_open) / live.session_open) * 100
      : null;

  return (
    <tr
      className={`cursor-pointer hover:bg-bg-elev/60 ${
        selected ? 'bg-bg-elev' : ''
      }`}
      onClick={onSelect}
      data-testid={`watchlist-row-${ticker}`}
      data-selected={selected ? 'true' : 'false'}
    >
      <td className="px-2 py-1.5 font-bold text-accent-yellow">{ticker}</td>
      <td className="px-2 py-1.5">
        <span
          className={`price-cell px-1 rounded ${flashClass}`}
          data-testid={`price-${ticker}`}
          data-flash={live?.flash ?? ''}
        >
          {fmtPrice(live?.price)}
        </span>
      </td>
      <td
        className={`px-2 py-1.5 ${dailyPct == null ? 'text-slate-500' : pnlColor(dailyPct)}`}
        data-testid={`daily-pct-${ticker}`}
      >
        {dailyPct == null ? '—' : fmtPct(dailyPct)}
      </td>
      <td className="px-2 py-1.5">
        <Sparkline values={live?.history ?? []} color="auto" />
      </td>
      <td className="px-2 py-1.5 text-right">
        <button
          aria-label={`remove-${ticker}`}
          className="text-slate-500 hover:text-down text-xs"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          ✕
        </button>
      </td>
    </tr>
  );
}

export function Watchlist({
  tickers,
  prices,
  selected,
  onSelect,
  onAdd,
  onRemove,
}: WatchlistProps) {
  const [newTicker, setNewTicker] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    setBusy(true);
    setError(null);
    try {
      await onAdd(t);
      setNewTicker('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel flex flex-col" data-testid="watchlist">
      <div className="panel-header">
        <span>Watchlist</span>
        <span className="text-slate-500 normal-case tracking-normal">
          {tickers.length}
        </span>
      </div>
      <div className="overflow-auto flex-1">
        <table className="w-full text-xs">
          <thead className="text-[10px] uppercase tracking-widest text-slate-500">
            <tr className="border-b border-bg-border">
              <th className="px-2 py-1 text-left">Tkr</th>
              <th className="px-2 py-1 text-left">Price</th>
              <th className="px-2 py-1 text-left">Day %</th>
              <th className="px-2 py-1 text-left">Trend</th>
              <th className="px-2 py-1 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {tickers.map((t) => (
              <WatchlistRow
                key={t}
                ticker={t}
                live={prices[t]}
                selected={selected === t}
                onSelect={() => onSelect(t)}
                onRemove={() => void onRemove(t)}
              />
            ))}
            {tickers.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-slate-500 py-4">
                  No tickers yet. Add one below.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <form onSubmit={submit} className="flex gap-2 p-2 border-t border-bg-border">
        <input
          aria-label="add-ticker"
          className="input flex-1"
          placeholder="Add ticker (e.g. PYPL)"
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value)}
          maxLength={5}
        />
        <button type="submit" className="btn btn-submit" disabled={busy}>
          Add
        </button>
      </form>
      {error && (
        <div className="px-2 pb-2 text-xs text-down" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}
