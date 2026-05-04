// PLAN.md §12 — Fresh start.
// Default 10 watchlist tickers visible, $10,000 cash in header,
// prices begin streaming within ~5s.

import { expect, test } from '@playwright/test';
import { DEFAULT_WATCHLIST, resetState, waitForPriceStream } from './_fixtures/reset';

test.describe('Fresh start', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('default watchlist, $10k cash, prices stream', async ({ page }) => {
    await page.goto('/');

    // Cash balance shown in header.
    const cash = page.getByTestId('cash-balance');
    await expect(cash).toBeVisible();
    await expect(cash).toContainText('$10,000');

    // All ten default watchlist rows are present.
    for (const ticker of DEFAULT_WATCHLIST) {
      await expect(
        page.getByTestId(`watchlist-row-${ticker}`),
        `watchlist row for ${ticker}`,
      ).toBeVisible();
    }

    // Prices stream: one of the rows shows a numeric price within ~5s.
    await waitForPriceStream(page, 'AAPL', 5_000);

    // Connection indicator transitions to connected.
    await expect(page.getByTestId('connection-status'))
      .toHaveAttribute('data-status', 'connected', { timeout: 5_000 });
  });
});
