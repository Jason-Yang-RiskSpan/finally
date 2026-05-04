// PLAN.md §12 — Buy 5 AAPL → cash decreases, position appears in positions
// table; sell all 5 → cash increases, position row disappears.

import { expect, test } from '@playwright/test';
import { getPortfolio, resetState, waitForPriceStream } from './_fixtures/reset';

const TICKER = 'AAPL';
const QTY = 5;

test.describe('Trade buy / sell', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('buy then full sell', async ({ page, request }) => {
    await page.goto('/');
    await waitForPriceStream(page, TICKER);

    const startingCash = (await getPortfolio(request)).cash_balance;

    // Use the trade bar.
    await page.getByLabel('trade-ticker').fill(TICKER);
    await page.getByLabel('trade-quantity').fill(String(QTY));
    await page.getByRole('button', { name: 'BUY' }).click();

    // Position row appears.
    const positionRow = page.getByTestId(`position-row-${TICKER}`);
    await expect(positionRow).toBeVisible({ timeout: 10_000 });

    // Cash strictly decreased.
    await expect.poll(
      async () => (await getPortfolio(request)).cash_balance,
      { timeout: 10_000, message: 'cash should decrease after buy' },
    ).toBeLessThan(startingCash);

    const cashAfterBuy = (await getPortfolio(request)).cash_balance;

    // Sell all 5 via the trade bar (ticker is auto-filled, but we pin it
    // explicitly to avoid relying on selection state).
    await page.getByLabel('trade-ticker').fill(TICKER);
    await page.getByLabel('trade-quantity').fill(String(QTY));
    await page.getByRole('button', { name: 'SELL' }).click();

    // Position row disappears (PLAN §7: zero-quantity rows are deleted).
    await expect(positionRow).toHaveCount(0, { timeout: 10_000 });

    // Cash returned (greater than post-buy; should be near starting cash).
    await expect.poll(
      async () => (await getPortfolio(request)).cash_balance,
      { timeout: 10_000, message: 'cash should rise after sell' },
    ).toBeGreaterThan(cashAfterBuy);
  });
});
