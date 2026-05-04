// PLAN.md §12 — Portfolio visualization.
// Heatmap renders cash tile on a fresh user (100% cash).
// After a buy, both cash tile and position tile coexist.
// P&L chart has at least the t=0 point (seeded at startup per PLAN §7).

import { expect, test } from '@playwright/test';
import { resetState, waitForPriceStream } from './_fixtures/reset';

test.describe('Portfolio visualization', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('heatmap and P&L chart render', async ({ page }) => {
    await page.goto('/');
    await waitForPriceStream(page);

    // Fresh user: cash tile is present, no position tiles.
    const heatmap = page.getByTestId('heatmap');
    await expect(heatmap).toBeVisible();
    await expect(heatmap.getByTestId('heat-tile-CASH')).toBeVisible();

    // P&L chart is mounted. At minimum, the seeded snapshot is present, but
    // the chart only renders a line when there are 2+ points; we assert the
    // panel itself is mounted and shows the formatted total in the header.
    const pnl = page.getByTestId('pnl-chart');
    await expect(pnl).toBeVisible();
    await expect(pnl).toContainText('$');

    // Buy 1 AAPL via the trade bar so we have a coexisting position tile.
    await page.getByLabel('trade-ticker').fill('AAPL');
    await page.getByLabel('trade-quantity').fill('1');
    await page.getByRole('button', { name: 'BUY' }).click();

    // Position tile and cash tile coexist.
    await expect(heatmap.getByTestId('heat-tile-AAPL')).toBeVisible({
      timeout: 10_000,
    });
    await expect(heatmap.getByTestId('heat-tile-CASH')).toBeVisible();
  });
});
