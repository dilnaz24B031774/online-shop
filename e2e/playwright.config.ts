import { defineConfig, devices } from '@playwright/test';

/**
 * Before running the tests start the shop as usual:
 *   Terminal 1: python3 manage.py runserver      (backend, http://127.0.0.1:8000)
 *   Terminal 2: cd frontend && npm start         (website, http://localhost:4200)
 * Use "localhost" (not 127.0.0.1) for the website: the backend allows CORS for both,
 * and the frontend calls the backend on the same host name it was opened with.
 */
export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.ts',

  // All tests use the same "admin" account (one cart on the server) -> run one by one.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },

  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:4200',
    locale: 'en-US',               // the site starts in English
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    launchOptions: { slowMo: process.argv.includes('--headed') ? 400 : 0 },
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});