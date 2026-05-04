import { defineConfig, devices } from '@playwright/test';

// BASE_URL is set by docker-compose.test.yml. When running locally outside
// docker (e.g., against `uv run uvicorn ...` on host), pass BASE_URL=http://localhost:8000.
const baseURL = process.env.BASE_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './specs',
  // Each spec stands up to a fresh container with `--reset-each` semantics
  // (see ./specs/_fixtures/reset.ts). Run serially so no two specs race for
  // the same singleton DB.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  outputDir: 'test-results',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
