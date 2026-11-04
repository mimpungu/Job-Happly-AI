import { describe, expect, it } from "vitest";

import { LOCALES } from "./config";
import en from "./messages/en.json";
import fr from "./messages/fr.json";

function cles(objet: Record<string, unknown>, prefixe = ""): string[] {
  return Object.entries(objet).flatMap(([cle, valeur]) =>
    typeof valeur === "object" && valeur !== null
      ? cles(valeur as Record<string, unknown>, `${prefixe}${cle}.`)
      : [`${prefixe}${cle}`],
  );
}

describe("fichiers de traduction", () => {
  it("déclarent exactement les mêmes clés dans toutes les langues", () => {
    expect(LOCALES).toEqual(["fr", "en"]);
    expect(cles(en).sort()).toEqual(cles(fr).sort());
  });

  it("n'ont aucune traduction vide", () => {
    for (const messages of [fr, en]) {
      const vides = cles(messages).filter((cle) => {
        const valeur = cle
          .split(".")
          .reduce<unknown>((acc, partie) => (acc as Record<string, unknown>)[partie], messages);
        return typeof valeur !== "string" || valeur.trim() === "";
      });
      expect(vides).toEqual([]);
    }
  });
});
