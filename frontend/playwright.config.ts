import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:18100',
    trace: 'retain-on-failure',
    timezoneId: 'Europe/Prague',
    locale: 'en-GB',
  },
  projects: [
    // Sets up the instance through the UI and creates the admin the other tests use.
    { name: 'setup', testMatch: /setup\.spec\.ts/, use: { ...devices['Desktop Chrome'] } },
    {
      name: 'desktop',
      testIgnore: /(setup|captcha)\.spec\.ts/,
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 860 } },
    },
    {
      name: 'phone',
      testIgnore: /(setup|captcha)\.spec\.ts/,
      dependencies: ['setup'],
      use: { ...devices['Pixel 7'] },
    },
    // Turns on a captcha for the whole instance, so it waits until the other tests are done.
    {
      name: 'captcha',
      testMatch: /captcha\.spec\.ts/,
      dependencies: ['desktop', 'phone'],
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
