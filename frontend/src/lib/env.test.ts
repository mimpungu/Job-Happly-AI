import { afterEach, describe, expect, it, vi } from "vitest";

describe("env", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("utilise l'API locale par défaut", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.resetModules();
    delete process.env.NEXT_PUBLIC_API_URL;

    const { env } = await import("./env");

    expect(env.apiUrl).toBe("http://127.0.0.1:8000");
  });

  it("rejette une URL invalide", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "pas-une-url");

    await expect(import("./env")).rejects.toThrow("NEXT_PUBLIC_API_URL invalide");
  });
});
