import { defineConfig, devices } from "@playwright/test";

import { STOCKAGE, URL_BASE } from "./e2e-fullstack/global-setup";

// Parcours de bout en bout : vrai navigateur, vraie API FastAPI, vraie base PostgreSQL, vrai pdfLaTeX.
// Tout reste sur 127.0.0.1 (ADR-0008) ; ports distincts des tests à API simulée.
const WEB = "http://127.0.0.1:3101";
const API = "http://127.0.0.1:8101";

export default defineConfig({
  testDir: "./e2e-fullstack",
  globalSetup: "./e2e-fullstack/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 90_000,
  reporter: [["list"]],
  use: { baseURL: WEB, trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Navigateur préinstallé quand le chemin est fourni (environnements sans `playwright install`).
        ...(process.env.HAPPLY_E2E_CHROMIUM
          ? { launchOptions: { executablePath: process.env.HAPPLY_E2E_CHROMIUM } }
          : {}),
      },
    },
  ],
  webServer: [
    {
      command: "uv run uvicorn app.main:app --host 127.0.0.1 --port 8101",
      cwd: "../backend",
      url: `${API}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        HAPPLY_DATABASE_URL: URL_BASE,
        HAPPLY_STORAGE_DIR: STOCKAGE,
        HAPPLY_CORS_ALLOWED_ORIGINS: JSON.stringify([WEB]),
        HAPPLY_LOG_LEVEL: "WARNING",
      },
    },
    {
      command: "pnpm exec next dev --hostname 127.0.0.1 --port 3101",
      url: WEB,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_URL: API },
    },
  ],
});
