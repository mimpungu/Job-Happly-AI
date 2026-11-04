import { describe, expect, it } from "vitest";

import { isActive, NAVIGATION_ITEMS } from "./navigation";

describe("navigation", () => {
  it("contient les 9 sections de la spécification, sans doublon de route", () => {
    expect(NAVIGATION_ITEMS).toHaveLength(9);
    expect(new Set(NAVIGATION_ITEMS.map((i) => i.href)).size).toBe(9);
  });

  it("active une entrée pour sa route et ses sous-routes uniquement", () => {
    expect(isActive("/jobs", "/jobs")).toBe(true);
    expect(isActive("/jobs/123", "/jobs")).toBe(true);
    expect(isActive("/jobs-archive", "/jobs")).toBe(false);
    expect(isActive("/saved-jobs", "/jobs")).toBe(false);
  });
});
