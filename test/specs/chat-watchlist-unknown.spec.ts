// PLAN.md §12 + §9 — Chat: "watch zzzzz" → unknown_ticker; watchlist
// unchanged; chat shows rejection.

import { expect, test } from '@playwright/test';
import { getWatchlist, resetState, waitForPriceStream } from './_fixtures/reset';

test.describe('Chat — watchlist unknown ticker', () => {
  test.beforeEach(async ({ request }) => {
    await resetState(request);
  });

  test('watch ZZZZZ is rejected and watchlist is unchanged', async ({ page, request }) => {
    await page.goto('/');
    await waitForPriceStream(page);

    const before = (await getWatchlist(request)).slice().sort();

    await page.getByLabel('chat-input').fill('watch zzzzz');
    await page.getByRole('button', { name: 'Send' }).click();

    const assistantMsg = page.getByTestId('chat-msg-assistant').last();
    await expect(assistantMsg).toBeVisible({ timeout: 15_000 });

    const action = assistantMsg.getByTestId('action-watchlist-0');
    await expect(action).toBeVisible();
    await expect(action).toHaveAttribute('data-status', 'rejected');
    await expect(action).toContainText(/ZZZZZ/i);
    await expect(action).toContainText(/unknown/i);

    // Watchlist unchanged.
    const after = (await getWatchlist(request)).slice().sort();
    expect(after).toEqual(before);
    await expect(page.getByTestId('watchlist-row-ZZZZZ')).toHaveCount(0);
  });
});
