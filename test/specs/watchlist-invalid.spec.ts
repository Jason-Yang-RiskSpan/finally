// PLAN.md §12 — Invalid ticker (`zzz123`) is rejected through the same path
// the UI uses. UI surfaces an error and no row is created.

import { expect, test } from '@playwright/test';
import { resetState, waitForPriceStream } from './_fixtures/reset';

const INVALID = 'zzz123';

test.describe('Watchlist add — invalid', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('rejects garbage ticker', async ({ page }) => {
    await page.goto('/');
    await waitForPriceStream(page);

    const input = page.getByLabel('add-ticker');
    // The input has maxLength=5, but the actual reject path is the backend's
    // syntactic + price-source probe. Either failure mode produces a UI error.
    await input.fill(INVALID);
    await page.getByRole('button', { name: 'Add' }).click();

    // An error alert should appear.
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 5_000 });

    // No watchlist row was created for the invalid input.
    // Check the upper-cased form (frontend uppercases before submit) too.
    await expect(
      page.getByTestId(`watchlist-row-${INVALID.toUpperCase()}`),
    ).toHaveCount(0);
    await expect(
      page.getByTestId(`watchlist-row-${INVALID}`),
    ).toHaveCount(0);
  });
});
