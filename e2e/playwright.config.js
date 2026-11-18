// Browser tests against the real Vue frontend, FastAPI backend and MySQL (#55).
// MySQL must already be running (`docker compose up -d --wait mysql`); Playwright
// starts the backend and the frontend and waits until both answer.
import { defineConfig, devices } from '@playwright/test'
import { database } from './helpers/database.js'

const CI = Boolean(process.env.CI)
const BACKEND = 'http://127.0.0.1:8000'
const FRONTEND = 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.js',
  // The upload runs real CPU inference; give it room without fixed sleeps.
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: CI,
  // No retries: a journey that fails once must fail the job, not pass as flaky.
  retries: 0,
  reporter: [
    ['list'],
    ['junit', { outputFile: '../reports/e2e-junit.xml' }],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  use: {
    baseURL: FRONTEND,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // In CI the environment is installed once with CPU-only PyTorch; syncing
      // again would swap it for the default (CUDA) build.
      command: `uv run --project backend ${CI ? '--no-sync ' : ''}uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`,
      cwd: '..',
      url: `${BACKEND}/health`,
      timeout: 180_000,
      reuseExistingServer: !CI,
      stdout: 'pipe',
      env: { ...database, SESSION_COOKIE_SECURE: '0', PRELOAD_MODELS: '1' },
    },
    {
      // The built app, as deployed. The dev server can reload a page mid-test when it
      // discovers a lazily loaded view's dependencies. `preview` keeps the /api proxy.
      command: 'npm --prefix frontend run build && npm --prefix frontend run preview -- --host 127.0.0.1 --port 5173 --strictPort',
      cwd: '..',
      url: FRONTEND,
      timeout: 120_000,
      reuseExistingServer: !CI,
    },
  ],
})
