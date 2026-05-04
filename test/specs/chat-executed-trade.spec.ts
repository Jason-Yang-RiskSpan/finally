// PLAN.md §12 + §9 — Chat: send "buy 5 aapl" → executed trade shown inline,
// position appears.

import { expect, test } from '@playwright/test';
import { resetState, waitForPriceStream } from './_fixtures/reset';

test.describe('Chat — executed trade', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('mock buy 5 AAPL is executed', async ({ page }) => {
    await page.goto('/');
    await waitForPriceStream(page, 'AAPL');

    await page.getByLabel('chat-input').fill('buy 5 aapl');
    await page.getByRole('button', { name: 'Send' }).click();

    // Assistant message appears.
    const assistantMsg = page.getByTestId('chat-msg-assistant').last();
    await expect(assistantMsg).toBeVisible({ timeout: 15_000 });

    // Inline action block shows an executed trade.
    const action = assistantMsg.getByTestId('action-trade-0');
    await expect(action).toBeVisible();
    await expect(action).toHaveAttribute('data-status', 'executed');
    await expect(action).toContainText(/AAPL/i);
    await expect(action).toContainText(/Executed/i);

    // Position row appears in the positions table.
    await expect(page.getByTestId('position-row-AAPL')).toBeVisible({
      timeout: 10_000,
    });
  });
});
