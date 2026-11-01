// End-to-end tests run against the offline single-file build (no network needed).
// Uses your installed Playwright browsers, or set CHROMIUM_PATH to any Chromium binary.
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: 'test/e2e',
  timeout: 60_000,
  workers: 1, // software WebGL in containers makes parallel browsers flaky
  use: {
    viewport: { width: 1280, height: 860 },
    colorScheme: 'dark',
    launchOptions: {
      executablePath: process.env.CHROMIUM_PATH || undefined,
      // software WebGL so the tests also run in CI containers without a GPU
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
  },
});
