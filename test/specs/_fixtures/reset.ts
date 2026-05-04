// Best-effort state reset for hermetic specs.
//
// PLAN.md does not expose an admin reset endpoint. To keep specs hermetic
// without rebuilding the container per spec, we:
//   1. Sell down every open position to zero (cash is returned, modulo any
//      drift between buy and sell — the simulator only moves prices a few
//      basis points per tick so the residual is small).
//   2. Remove every watchlist ticker that is NOT in the default seed list,
//      restoring the watchlist to the 10 seed tickers.
//
// We deliberately do not assert exact cash after reset — the simulator's
// price drift would make that brittle. Specs that need a precise cash
// number should record the value at the start of the test and assert
// against deltas.

import { APIRequestContext, expect } from '@playwright/test';

export const DEFAULT_WATCHLIST = [
  'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA',
  'NVDA', 'META', 'JPM', 'V', 'NFLX',
];

interface Position {
  ticker: string;
  quantity: number;
}

interface PortfolioResponse {
  cash_balance: number;
  total_value: number;
  positions: Position[];
}

interface WatchlistItem {
  ticker: string;
}

interface WatchlistResponse {
  items: WatchlistItem[];
}

export async function getPortfolio(req: APIRequestContext): Promise<PortfolioResponse> {
  const r = await req.get('/api/portfolio');
  expect(r.ok(), `GET /api/portfolio -> ${r.status()}`).toBeTruthy();
  return (await r.json()) as PortfolioResponse;
}

export async function getWatchlist(req: APIRequestContext): Promise<string[]> {
  const r = await req.get('/api/watchlist');
  expect(r.ok(), `GET /api/watchlist -> ${r.status()}`).toBeTruthy();
  const body = (await r.json()) as WatchlistResponse | WatchlistItem[];
  const items = Array.isArray(body) ? body : body.items ?? [];
  return items.map((i) => i.ticker);
}

export async function resetState(req: APIRequestContext): Promise<void> {
  // Sell down all positions.
  const portfolio = await getPortfolio(req);
  for (const p of portfolio.positions) {
    if (p.quantity > 0) {
      const r = await req.post('/api/portfolio/trade', {
        data: { ticker: p.ticker, quantity: p.quantity, side: 'sell' },
      });
      // Allow a 400 here — if the price source has rejected the ticker for
      // some reason the position will drop on the next valuation; not worth
      // failing the suite over.
      if (!r.ok()) {
        // eslint-disable-next-line no-console
        console.warn(`[reset] sell ${p.ticker} x${p.quantity} -> ${r.status()}`);
      }
    }
  }

  // Restore watchlist to default seed.
  const watchlist = await getWatchlist(req);
  const defaults = new Set(DEFAULT_WATCHLIST);
  for (const ticker of watchlist) {
    if (!defaults.has(ticker)) {
      const r = await req.delete(`/api/watchlist/${encodeURIComponent(ticker)}`);
      if (!r.ok() && r.status() !== 404) {
        // eslint-disable-next-line no-console
        console.warn(`[reset] remove ${ticker} -> ${r.status()}`);
      }
    }
  }
  for (const ticker of defaults) {
    if (!watchlist.includes(ticker)) {
      const r = await req.post('/api/watchlist', { data: { ticker } });
      if (!r.ok() && r.status() !== 400) {
        // eslint-disable-next-line no-console
        console.warn(`[reset] add ${ticker} -> ${r.status()}`);
      }
    }
  }
}

// Wait until at least one of the given tickers has a price visible in the UI.
// Used to confirm the SSE stream has started flowing.
export async function waitForPriceStream(
  page: import('@playwright/test').Page,
  ticker: string = 'AAPL',
  timeout: number = 10_000,
): Promise<void> {
  const cell = page.getByTestId(`price-${ticker}`);
  await expect(cell).toBeVisible({ timeout });
  // Wait until the cell has a numeric value (not "—" placeholder).
  await expect.poll(
    async () => (await cell.textContent())?.trim() ?? '',
    { timeout, message: `price-${ticker} did not populate` },
  ).toMatch(/\d+\.\d+/);
}
