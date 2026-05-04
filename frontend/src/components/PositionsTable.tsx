'use client';

// Positions table. Backend deletes zero-quantity rows on full sells (PLAN §7),
// but we defensively filter here too so a transient state can't break the UI.

import type { LivePriceMap, Position } from '@/lib/types';
import { fmtCurrency, fmtPct, fmtPrice, fmtQty, pnlColor } from '@/lib/format';

interface PositionsTableProps {
  positions: Position[];
  prices: LivePriceMap;
  onSelect?: (ticker: string) => void;
}

export function PositionsTable({ positions, prices, onSelect }: PositionsTableProps) {
  const visible = positions.filter((p) => p.quantity > 0);

  return (
    <section className="panel flex flex-col" data-testid="positions-table">
      <div className="panel-header">
        <span>Positions</span>
        <span className="text-slate-500 normal-case tracking-normal">
          {visible.length}
        </span>
      </div>
      <div className="overflow-auto flex-1">
        <table className="w-full text-xs">
          <thead className="text-[10px] uppercase tracking-widest text-slate-500">
            <tr className="border-b border-bg-border">
              <th className="px-2 py-1 text-left">Tkr</th>
              <th className="px-2 py-1 text-right">Qty</th>
              <th className="px-2 py-1 text-right">Avg</th>
              <th className="px-2 py-1 text-right">Last</th>
              <th className="px-2 py-1 text-right">P&amp;L</th>
              <th className="px-2 py-1 text-right">%</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((p) => {
              // Prefer live price if available; otherwise the API's stored value.
              const live = prices[p.ticker]?.price;
              const last = live ?? p.current_price;
              const marketValue = last * p.quantity;
              const cost = p.avg_cost * p.quantity;
              const pnl = marketValue - cost;
              const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
              return (
                <tr
                  key={p.ticker}
                  className="hover:bg-bg-elev/60 cursor-pointer"
                  onClick={() => onSelect?.(p.ticker)}
                  data-testid={`position-row-${p.ticker}`}
                >
                  <td className="px-2 py-1.5 font-bold text-accent-yellow">
                    {p.ticker}
                  </td>
                  <td className="px-2 py-1.5 text-right">{fmtQty(p.quantity)}</td>
                  <td className="px-2 py-1.5 text-right">{fmtPrice(p.avg_cost)}</td>
                  <td className="px-2 py-1.5 text-right">{fmtPrice(last)}</td>
                  <td className={`px-2 py-1.5 text-right ${pnlColor(pnl)}`}>
                    {fmtCurrency(pnl, { sign: true })}
                  </td>
                  <td className={`px-2 py-1.5 text-right ${pnlColor(pnlPct)}`}>
                    {fmtPct(pnlPct)}
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center text-slate-500 py-6">
                  No open positions.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
