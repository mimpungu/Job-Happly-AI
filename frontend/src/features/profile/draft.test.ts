import { describe, expect, it } from "vitest";

import type { Experience, ProfileDocument } from "@/types/profile";

import {
  addItem,
  confirmItem,
  describeChange,
  describePath,
  emptyDocument,
  hasContent,
  isDirty,
  missingFields,
  normalizePath,
  patchItem,
  pendingReview,
  removeItem,
  NEW_ITEMS,
} from "./draft";

const complete = (): Experience => ({
  ...NEW_ITEMS.experiences(),
  title: "Dev",
  company: "Acme",
  start: { year: 2020, month: null },
});

const avecExperience = (exp: Experience): ProfileDocument => ({
  ...emptyDocument(),
  experiences: [exp],
});

describe("missingFields", () => {
  it("liste les champs obligatoires manquants par type d'élément", () => {
    expect(missingFields("experiences", NEW_ITEMS.experiences())).toEqual([
      "intitulé",
      "entreprise",
      "date de début",
    ]);
    expect(missingFields("educations", NEW_ITEMS.educations())).toEqual([
      "diplôme",
      "établissement",
    ]);
    expect(missingFields("languages", NEW_ITEMS.languages())).toEqual(["langue", "niveau"]);
    expect(missingFields("skills", NEW_ITEMS.skills())).toEqual(["nom"]);
    expect(missingFields("experiences", complete())).toEqual([]);
  });

  it("une langue sans niveau reste incomplète même avec un texte d'origine", () => {
    const langue = { ...NEW_ITEMS.languages(), language_code: "en", level_text: "courant" };

    expect(missingFields("languages", langue)).toEqual(["niveau"]);
  });
});

describe("modifications du brouillon", () => {
  it("modifier un élément confirmé retire sa confirmation", () => {
    const doc = avecExperience({ ...complete(), validated: true });

    const apres = patchItem(doc, "experiences", 0, { company: "Autre" });

    expect(apres.experiences[0]?.company).toBe("Autre");
    expect(apres.experiences[0]?.validated).toBe(false);
  });

  it("confirmer ne retire pas la confirmation", () => {
    const apres = confirmItem(avecExperience(complete()), "experiences", 0);

    expect(apres.experiences[0]?.validated).toBe(true);
  });

  it("ne modifie pas le document d'origine (immutabilité)", () => {
    const doc = avecExperience(complete());

    patchItem(doc, "experiences", 0, { company: "Autre" });
    addItem(doc, "skills");
    removeItem(doc, "experiences", 0);

    expect(doc.experiences[0]?.company).toBe("Acme");
    expect(doc.skills).toHaveLength(0);
    expect(doc.experiences).toHaveLength(1);
  });

  it("ajoute un élément saisi à la main, non validé, sans identifiant", () => {
    const doc = addItem(emptyDocument(), "skills");

    expect(doc.skills[0]).toMatchObject({ id: null, origin: "manual", validated: false, name: "" });
  });

  it("retire le bon élément", () => {
    const a = { ...NEW_ITEMS.skills(), name: "A" };
    const b = { ...NEW_ITEMS.skills(), name: "B" };

    const doc = removeItem({ ...emptyDocument(), skills: [a, b] }, "skills", 0);

    expect(doc.skills.map((s) => s.name)).toEqual(["B"]);
  });
});

describe("état du brouillon", () => {
  it("détecte les modifications non enregistrées", () => {
    const saved = avecExperience(complete());

    expect(isDirty(saved, saved)).toBe(false);
    expect(isDirty(patchItem(saved, "experiences", 0, { title: "X" }), saved)).toBe(true);
  });

  it("un brouillon jamais enregistré est modifié dès qu'il a du contenu", () => {
    expect(hasContent(emptyDocument())).toBe(false);
    expect(hasContent(avecExperience(complete()))).toBe(true);
    expect(isDirty(emptyDocument(), null)).toBe(false);
  });

  it("compte les éléments restant à confirmer", () => {
    const doc: ProfileDocument = {
      ...emptyDocument(),
      experiences: [{ ...complete(), validated: true }, complete()],
      skills: [{ ...NEW_ITEMS.skills(), name: "Python" }],
    };

    expect(pendingReview(doc)).toBe(2);
  });
});

describe("chemins d'erreur", () => {
  it("normalise les deux notations du serveur", () => {
    expect(normalizePath("experiences.0.end")).toBe("experiences[0].end");
    expect(normalizePath("experiences[0].company")).toBe("experiences[0].company");
    expect(normalizePath("identity.email")).toBe("identity.email");
    expect(normalizePath("skills.12")).toBe("skills[12]");
  });

  it("décrit un chemin en français, numérotation à partir de 1", () => {
    expect(describePath("experiences[0].company")).toBe("Expérience 1 : entreprise");
    expect(describePath("languages[2].proficiency")).toBe("Langue 3 : niveau");
    expect(describePath("skills[1]")).toBe("Compétence 2");
    expect(describePath("identity.first_name")).toBe("Identité : prénom");
    expect(describePath("quelque.chose.d'inconnu")).toBe("quelque.chose.d'inconnu");
  });
});

describe("describeChange", () => {
  it("décrit les événements du profil par leur libellé", () => {
    expect(
      describeChange({
        entity_type: "profile",
        action: "validate",
        label: "Version 1 validée",
        changes: {},
      }),
    ).toBe("Version 1 validée");
  });

  it("décrit une modification avec les champs touchés", () => {
    expect(
      describeChange({
        entity_type: "skill",
        action: "update",
        label: "Python",
        changes: { validated: [false, true], level: [null, "expert"] },
      }),
    ).toBe("Modification — compétence « Python » (confirmation, niveau)");
  });

  it("décrit un ajout et une suppression sans lister les champs", () => {
    expect(
      describeChange({
        entity_type: "skill",
        action: "create",
        label: "Docker",
        changes: { name: [null, "Docker"] },
      }),
    ).toBe("Ajout — compétence « Docker »");
    expect(
      describeChange({ entity_type: "skill", action: "delete", label: "COBOL", changes: {} }),
    ).toBe("Suppression — compétence « COBOL »");
  });

  it("n'affiche pas de nom pour l'identité ou les préférences", () => {
    expect(
      describeChange({
        entity_type: "identity",
        action: "update",
        label: "identity",
        changes: { first_name: [null, "M"] },
      }),
    ).toBe("Modification — identité (prénom)");
  });
});
