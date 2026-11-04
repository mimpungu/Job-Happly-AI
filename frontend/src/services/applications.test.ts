import { afterEach, describe, expect, it, vi } from "vitest";

import { EMPTY_FILTERS } from "@/features/applications/filters";

import {
  attachDocuments,
  changeStatus,
  confirmSubmission,
  filtersToQuery,
  listDocumentChoices,
  setFollowUp,
} from "./applications";

function simuler(reponses: Record<string, unknown> = {}) {
  const appels: { url: string; methode: string; corps?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      appels.push({
        url,
        methode: init?.method ?? "GET",
        corps: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      const cle = Object.keys(reponses).find((k) => url.includes(k));
      return new Response(JSON.stringify(cle ? reponses[cle] : {}));
    }),
  );
  return appels;
}

afterEach(() => vi.unstubAllGlobals());

describe("filtersToQuery", () => {
  it("n'envoie que les filtres renseignés, plus la pagination", () => {
    expect(filtersToQuery(EMPTY_FILTERS)).toBe("limit=25&offset=0");
  });

  it("traduit chaque filtre vers le paramètre de l'API", () => {
    const requete = new URLSearchParams(
      filtersToQuery({
        status: "sent",
        company: " Acme ",
        title: "Python",
        followUp: "due",
        page: 3,
      }),
    );
    expect(Object.fromEntries(requete)).toEqual({
      status: "sent",
      company: "Acme",
      title: "Python",
      follow_up_due: "true",
      limit: "25",
      offset: "50",
    });
    expect(
      new URLSearchParams(filtersToQuery({ ...EMPTY_FILTERS, followUp: "planned" })).get(
        "has_follow_up",
      ),
    ).toBe("true");
  });

  it("ne produit jamais de décalage négatif", () => {
    expect(filtersToQuery({ ...EMPTY_FILTERS, page: -4 })).toContain("offset=0");
  });
});

describe("écritures", () => {
  it("la confirmation d'envoi transmet la vraie date et la note, rien d'autre", async () => {
    const appels = simuler();
    await confirmSubmission("c 1", { notes: "Portail", appliedAt: "2026-11-03T08:00:00.000Z" });

    expect(appels[0]).toMatchObject({
      url: expect.stringContaining("/api/v1/applications/c%201/confirm-submission"),
      methode: "POST",
      corps: { notes: "Portail", applied_at: "2026-11-03T08:00:00.000Z" },
    });
    await confirmSubmission("c1", {});
    expect(appels[1]?.corps).toEqual({});
  });

  it("le changement de statut n'envoie la raison que si elle existe", async () => {
    const appels = simuler();
    await changeStatus("c1", "abandoned");
    await changeStatus("c1", "abandoned", "Poste pourvu");

    expect(appels[0]?.corps).toEqual({ target_status: "abandoned" });
    expect(appels[1]?.corps).toEqual({ target_status: "abandoned", reason: "Poste pourvu" });
  });

  it("annuler une relance envoie une date nulle", async () => {
    const appels = simuler();
    await setFollowUp("c1", null);
    expect(appels[0]).toMatchObject({ methode: "PATCH", corps: { follow_up_at: null } });
  });

  it("l'association distingue le CV et la lettre, l'absent restant nul", async () => {
    const appels = simuler();
    await attachDocuments("c1", { cvVersionId: "v1" });
    expect(appels[0]).toMatchObject({
      methode: "PUT",
      corps: { cv_version_id: "v1", letter_version_id: null },
    });
  });
});

describe("listDocumentChoices", () => {
  it("propose les versions du plus récent au plus ancien, CV puis lettres", async () => {
    simuler({
      "/resumes": [
        {
          id: "d1",
          title: "CV Python",
          versions: [
            { id: "v1", version: 1 },
            { id: "v2", version: 2 },
          ],
        },
      ],
      "/cover-letters": [{ id: "d2", title: "Lettre Acme", versions: [{ id: "v3", version: 1 }] }],
    });

    expect(await listDocumentChoices()).toEqual([
      { versionId: "v2", kind: "cv", label: "CV Python — v2" },
      { versionId: "v1", kind: "cv", label: "CV Python — v1" },
      { versionId: "v3", kind: "cover_letter", label: "Lettre Acme — v1" },
    ]);
  });
});
