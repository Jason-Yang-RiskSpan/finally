'use client';

// Workstation page: composes header, watchlist, main chart, heatmap, P&L
// chart, positions table, trade bar, and the AI chat panel. All API state is
// local to this page. SSE is the source of truth for live prices; REST polls
// portfolio state every 5s as a backstop and after each trade.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Header } from '@/components/Header';
import { Watchlist } from '@/components/Watchlist';
import { MainChart } from '@/components/MainChart';
import { Heatmap } from '@/components/Heatmap';
import { PnlChart } from '@/components/PnlChart';
import { PositionsTable } from '@/components/PositionsTable';
import { TradeBar } from '@/components/TradeBar';
import { ChatPanel } from '@/components/ChatPanel';
import { usePriceStream } from '@/hooks/usePriceStream';
import { api } from '@/lib/api';
import type {
  ChatMessage,
  PortfolioResponse,
  PortfolioSnapshot,
  WatchlistItem,
} from '@/lib/types';

const POLL_INTERVAL_MS = 5000;

export default function WorkstationPage() {
  const { prices, status } = usePriceStream();

  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioResponse>({
    cash_balance: 10000,
    total_value: 10000,
    positions: [],
  });
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);

  const refreshPortfolio = useCallback(async () => {
    try {
      const p = await api.getPortfolio();
      setPortfolio(p);
    } catch {
      // Backend may not be up in dev; the empty defaults are acceptable.
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      const w = await api.getWatchlist();
      setWatchlist(w);
      setSelected((curr) =>
        curr ?? (w.length > 0 ? w[0].ticker : null),
      );
    } catch {
      // ignore
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const h = await api.getPortfolioHistory();
      setSnapshots(h);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    void refreshPortfolio();
    void refreshWatchlist();
    void refreshHistory();
    const t = setInterval(() => {
      void refreshPortfolio();
      void refreshHistory();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [refreshPortfolio, refreshWatchlist, refreshHistory]);

  // Live total value: cash + Σ(qty * livePrice). Falls back to API total if
  // we don't have a live price for a held ticker.
  const liveTotal = useMemo(() => {
    let total = portfolio.cash_balance;
    for (const p of portfolio.positions) {
      const live = prices[p.ticker]?.price;
      const last = live ?? p.current_price;
      total += (last ?? 0) * p.quantity;
    }
    return total;
  }, [portfolio, prices]);

  const liveUnrealizedPnl = useMemo(() => {
    let pnl = 0;
    for (const p of portfolio.positions) {
      const live = prices[p.ticker]?.price;
      const last = live ?? p.current_price;
      pnl += ((last ?? 0) - p.avg_cost) * p.quantity;
    }
    return pnl;
  }, [portfolio.positions, prices]);

  const tickers = useMemo(() => watchlist.map((w) => w.ticker), [watchlist]);

  const onSelect = useCallback((t: string) => setSelected(t), []);

  const onAddTicker = useCallback(
    async (t: string) => {
      await api.addWatchlist(t);
      await refreshWatchlist();
    },
    [refreshWatchlist],
  );

  const onRemoveTicker = useCallback(
    async (t: string) => {
      await api.removeWatchlist(t);
      setSelected((curr) => (curr === t ? null : curr));
      await refreshWatchlist();
    },
    [refreshWatchlist],
  );

  const onTrade = useCallback(
    async (side: 'buy' | 'sell', ticker: string, quantity: number) => {
      await api.trade({ side, ticker, quantity });
      await Promise.all([refreshPortfolio(), refreshHistory()]);
    },
    [refreshPortfolio, refreshHistory],
  );

  const onChat = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = { role: 'user', content: text };
      setChat((prev) => [...prev, userMsg]);
      setChatBusy(true);
      try {
        const res = await api.chat(text, [...chat, userMsg]);
        setChat((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.message,
            actions: res.actions ?? null,
          },
        ]);
        // Side effects from auto-executed actions
        await Promise.all([
          refreshPortfolio(),
          refreshWatchlist(),
          refreshHistory(),
        ]);
      } catch (err) {
        setChat((prev) => [
          ...prev,
          {
            role: 'assistant',
            content:
              err instanceof Error
                ? `Error: ${err.message}`
                : 'Error contacting assistant.',
          },
        ]);
      } finally {
        setChatBusy(false);
      }
    },
    [chat, refreshPortfolio, refreshWatchlist, refreshHistory],
  );

  const selectedLive = selected ? prices[selected] : undefined;

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        totalValue={liveTotal}
        cashBalance={portfolio.cash_balance}
        unrealizedPnl={liveUnrealizedPnl}
        connection={status}
      />

      <main className="flex-1 grid gap-3 p-3 grid-cols-12 grid-rows-[minmax(280px,1fr)_minmax(220px,1fr)_auto]">
        {/* Row 1 */}
        <div className="col-span-3 row-span-2 min-h-0">
          <Watchlist
            tickers={tickers}
            prices={prices}
            selected={selected}
            onSelect={onSelect}
            onAdd={onAddTicker}
            onRemove={onRemoveTicker}
          />
        </div>
        <div className="col-span-6 min-h-0">
          <MainChart ticker={selected} live={selectedLive} />
        </div>
        <div className="col-span-3 row-span-2 min-h-0 flex">
          <ChatPanel messages={chat} onSend={onChat} busy={chatBusy} />
        </div>

        {/* Row 2 */}
        <div className="col-span-3 min-h-0">
          <Heatmap
            positions={portfolio.positions}
            cashBalance={portfolio.cash_balance}
            totalValue={liveTotal}
          />
        </div>
        <div className="col-span-3 min-h-0">
          <PnlChart snapshots={snapshots} liveTotal={liveTotal} />
        </div>

        {/* Row 3 */}
        <div className="col-span-6 min-h-0">
          <PositionsTable
            positions={portfolio.positions}
            prices={prices}
            onSelect={onSelect}
          />
        </div>
        <div className="col-span-6 min-h-0">
          <TradeBar selected={selected} prices={prices} onTrade={onTrade} />
        </div>
      </main>
    </div>
  );
}
