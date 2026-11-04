import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "./api-client";

function repondre(statut: number, corps?: unknown) {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(corps === undefined ? null : JSON.stringify(corps), { status: statut }),
      ),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("renvoie le JSON d'une réponse réussie", async () => {
    repondre(200, { ok: true });

    expect(await apiFetch("/x")).toEqual({ ok: true });
  });

  it("renvoie undefined pour un 204", async () => {
    repondre(204);

    expect(await apiFetch("/x")).toBeUndefined();
  });

  it("remonte le message normalisé de l'API", async () => {
    repondre(409, { error: { code: "saved_search_duplicate", message: "Ce nom existe déjà." } });

    await expect(apiFetch("/x")).rejects.toMatchObject({
      status: 409,
      code: "saved_search_duplicate",
      message: "Ce nom existe déjà.",
    });
  });

  it("n'affiche pas une réponse d'erreur non conforme", async () => {
    repondre(500, "<html>trace secrète</html>");

    const erreur = await apiFetch("/x").catch((e: unknown) => e);

    expect(erreur).toBeInstanceOf(ApiError);
    expect((erreur as ApiError).message).toBe("Réponse inattendue du serveur.");
  });

  it("signale clairement un serveur injoignable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("n'ajoute Content-Type que pour un corps", async () => {
    repondre(200, {});
    await apiFetch("/x", { method: "POST", body: "{}" });
    await apiFetch("/y");

    const appels = vi.mocked(fetch).mock.calls;
    expect((appels[0]?.[1]?.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
    expect((appels[1]?.[1]?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("transporte le détail par champ d'une erreur de validation", async () => {
    repondre(422, {
      error: {
        code: "profile_incomplete",
        message: "Le profil est incomplet.",
        details: [{ field: "experiences[0].company", message: "Champ obligatoire." }],
      },
    });

    const erreur = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;

    expect(erreur.details).toEqual([
      { field: "experiences[0].company", message: "Champ obligatoire." },
    ]);
  });

  it("laisse le navigateur fixer le Content-Type d'un envoi de fichier", async () => {
    repondre(200, {});
    const formulaire = new FormData();
    formulaire.append("fichier", new Blob(["x"]), "cv.txt");

    await apiFetch("/x", { method: "POST", body: formulaire });

    const en_tetes = vi.mocked(fetch).mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(en_tetes["Content-Type"]).toBeUndefined();
  });
});
