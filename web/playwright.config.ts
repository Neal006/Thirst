import { defineConfig, devices } from '@playwright/test'

/** The live Amplify site. Override with E2E_BASE_URL (for example http://127.0.0.1:4173 after `vite preview`). */
const LIVE_URL = 'https://main.dzxkrtlc7xqfx.amplifyapp.com'

const baseURL = (process.env.E2E_BASE_URL ?? LIVE_URL).replace(/\/+$/, '')

const PHONE_VIEWPORT = { width: 360, height: 740 } as const

// The suite is read-only against the live site: see e2e/fixtures.ts for the guard that fails a test
// that sends anything other than GET or POST /plan.
export default defineConfig({
  testDir: './e2e',
  outputDir: './e2e/.out/results',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 3,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: './e2e/.out/report' }],
    ['json', { outputFile: './e2e/.out/results.json' }],
  ],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'en-IN',
    timezoneId: 'Asia/Kolkata',
  },
  projects: [
    {
      name: 'desktop-chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
      testIgnore: /mobile\.spec\.ts/,
    },
    {
      name: 'phone-360',
      use: {
        ...devices['Pixel 5'],
        viewport: PHONE_VIEWPORT,
      },
    },
  ],
})
