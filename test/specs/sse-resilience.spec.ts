// PLAN.md §12 — SSE resilience.
// Use page.context().setOffline(true) to drop the network, verify the
// connection-status indicator transitions away from "connected", then
// reconnect and verify prices continue to update.

import { expect, test } from '@playwright/test';
import { resetState, waitForPriceStream } from './_fixtures/reset';

test.describe('SSE resilience', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('reconnects and resumes price updates after offline', async ({ page, context }) => {
    await page.goto('/');
    await waitForPriceStream(page, 'AAPL');

    const status = page.getByTestId('connection-status');
    await expect(status).toHaveAttribute('data-status', 'connected', {
      timeout: 5_000,
    });

    // Drop the network. EventSource sees the underlying socket close and
    // surfaces an error → hook moves to "connecting" or "disconnected".
    await context.setOffline(true);

    await expect.poll(
      async () => await status.getAttribute('data-status'),
      { timeout: 10_000, message: 'connection should leave "connected" while offline' },
    ).not.toBe('connected');

    // Capture the latest price text for AAPL while offline.
    const priceCell = page.getByTestId('price-AAPL');
    const offlinePrice = (await priceCell.textContent())?.trim() ?? '';

    // Restore the network. Native EventSource auto-reconnects (server emits
    // retry: 3000). The status dot should return to "connected".
    await context.setOffline(false);

    await expect(status).toHaveAttribute('data-status', 'connected', {
      timeout: 20_000,
    });

    // And prices should continue to update — the cell text changes again.
    await expect.poll(
      async () => (await priceCell.textContent())?.trim() ?? '',
      {
        timeout: 20_000,
        message: 'price should change again after reconnect',
      },
    ).not.toBe(offlinePrice);
  });
});
