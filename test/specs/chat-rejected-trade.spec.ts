// PLAN.md §12 + §9 — Chat: send "buy 1000000 aapl" → mock returns
// insufficient_cash; chat shows rejection inline.

import { expect, test } from '@playwright/test';
import { resetState, waitForPriceStream } from './_fixtures/reset';

test.describe('Chat — rejected trade', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('mock buy 1,000,000 AAPL is rejected for insufficient cash', async ({ page }) => {
    await page.goto('/');
    await waitForPriceStream(page, 'AAPL');

    await page.getByLabel('chat-input').fill('buy 1000000 aapl');
    await page.getByRole('button', { name: 'Send' }).click();

    const assistantMsg = page.getByTestId('chat-msg-assistant').last();
    await expect(assistantMsg).toBeVisible({ timeout: 15_000 });

    const action = assistantMsg.getByTestId('action-trade-0');
    await expect(action).toBeVisible();
    await expect(action).toHaveAttribute('data-status', 'rejected');
    await expect(action).toContainText(/Rejected/i);
    await expect(action).toContainText(/insufficient/i);

    // No position row was created.
    await expect(page.getByTestId('position-row-AAPL')).toHaveCount(0);
  });
});
