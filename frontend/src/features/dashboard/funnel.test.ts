import { describe, expect, it } from "vitest";

import { biggestDrop, funnelStages, niceTicks } from "./funnel";

const entonnoir = { offers: 100, tracked: 50, sent: 40, responses: 10, offers_received: 5 };

describe("funnelStages", () => {
  it("calcule conversion et perte depuis l'étape précédente", () => {
    const etapes = funnelStages(entonnoir);

    expect(etapes.map((e) => e.label)).toEqual([
      "Offres",
      "Suivies",
      "Envoyées",
      "Réponses",
      "Offres reçues",
    ]);
    expect(etapes[0]).toMatchObject({
      value: 100,
      previous: null,
      conversion: null,
      dropOff: null,
    });
    expect(etapes[1]).toMatchObject({ conversion: 50, dropOff: 50 });
    expect(etapes[2]).toMatchObject({ conversion: 80, dropOff: 20 });
    expect(etapes[3]).toMatchObject({ conversion: 25, dropOff: 75 });
  });

  it("n'invente aucune conversion quand l'étape précédente est vide", () => {
    const etapes = funnelStages({
      offers: 3,
      tracked: 0,
      sent: 0,
      responses: 0,
      offers_received: 0,
    });

    expect(etapes[2]).toMatchObject({ previous: 0, conversion: null, dropOff: null });
    expect(etapes[1]).toMatchObject({ conversion: 0, dropOff: 100 });
  });
});

describe("biggestDrop", () => {
  it("désigne le passage qui perd le plus, en valeur absolue", () => {
    // 100→50 : −50 ; 50→40 : −10 ; 40→10 : −30 ; 10→5 : −5
    expect(biggestDrop(funnelStages(entonnoir))?.label).toBe("Suivies");
  });

  it("ne propose rien quand rien n'est perdu ou quand tout est vide", () => {
    expect(
      biggestDrop(
        funnelStages({ offers: 4, tracked: 4, sent: 4, responses: 4, offers_received: 4 }),
      ),
    ).toBeNull();
    expect(
      biggestDrop(
        funnelStages({ offers: 0, tracked: 0, sent: 0, responses: 0, offers_received: 0 }),
      ),
    ).toBeNull();
  });
});

describe("niceTicks", () => {
  it("couvre toujours le maximum avec des valeurs rondes", () => {
    for (const max of [1, 7, 12, 99, 232, 46_200]) {
      const ticks = niceTicks(max);
      expect(ticks[0]).toBe(0);
      expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(max);
      expect(ticks.length).toBeLessThanOrEqual(7);
    }
  });

  it("choisit un pas lisible", () => {
    expect(niceTicks(46_200)).toEqual([0, 20_000, 40_000, 60_000]);
    expect(niceTicks(12)).toEqual([0, 5, 10, 15]);
  });

  it("gère un entonnoir vide", () => {
    expect(niceTicks(0)).toEqual([0, 1]);
  });
});
