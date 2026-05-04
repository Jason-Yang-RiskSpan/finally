// PLAN.md §12 + §9 — Chat: "watch pypl" → PYPL added to watchlist; chat shows
// executed.

import { expect, test } from '@playwright/test';
import { resetState, waitForPriceStream } from './_fixtures/reset';

test.describe('Chat — watchlist add (executed)', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('watch PYPL adds the ticker', async ({ page }) => {
    await page.goto('/');
    await waitForPriceStream(page);

    await page.getByLabel('chat-input').fill('watch pypl');
    await page.getByRole('button', { name: 'Send' }).click();

    const assistantMsg = page.getByTestId('chat-msg-assistant').last();
    await expect(assistantMsg).toBeVisible({ timeout: 15_000 });

    const action = assistantMsg.getByTestId('action-watchlist-0');
    await expect(action).toBeVisible();
    await expect(action).toHaveAttribute('data-status', 'executed');
    await expect(action).toContainText(/PYPL/i);

    // PYPL row appears in the watchlist.
    await expect(page.getByTestId('watchlist-row-PYPL')).toBeVisible({
      timeout: 10_000,
    });
  });
});
