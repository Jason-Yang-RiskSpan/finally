// PLAN.md §12 — Add a valid ticker via the UI; remove it; both reflect immediately.

import { expect, test } from '@playwright/test';
import { resetState, waitForPriceStream } from './_fixtures/reset';

const NEW_TICKER = 'PYPL';

test.describe('Watchlist add / remove', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('add then remove a valid ticker', async ({ page }) => {
    await page.goto('/');
    await waitForPriceStream(page);

    // Sanity: ticker is not present at start.
    await expect(page.getByTestId(`watchlist-row-${NEW_TICKER}`)).toHaveCount(0);

    // Add via the watchlist input form.
    const input = page.getByLabel('add-ticker');
    await input.fill(NEW_TICKER);
    await page.getByRole('button', { name: 'Add' }).click();

    // Row appears.
    await expect(
      page.getByTestId(`watchlist-row-${NEW_TICKER}`),
    ).toBeVisible();

    // Price for the new ticker streams in.
    await waitForPriceStream(page, NEW_TICKER, 10_000);

    // Remove via the per-row × button.
    await page.getByLabel(`remove-${NEW_TICKER}`).click();

    await expect(
      page.getByTestId(`watchlist-row-${NEW_TICKER}`),
    ).toHaveCount(0, { timeout: 5_000 });
  });
});
