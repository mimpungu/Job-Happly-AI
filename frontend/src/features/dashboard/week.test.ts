import { describe, expect, it } from "vitest";

import { countInWeek, isSameDay, startOfWeek, weekDays, weeklyPercent } from "./week";

// Mercredi 4 novembre 2026, heure locale.
const mercredi = new Date(2026, 10, 4, 15, 30);

describe("semaine du lundi au dimanche", () => {
  it("commence le lundi, même un dimanche", () => {
    expect(startOfWeek(mercredi).getDate()).toBe(2);
    expect(startOfWeek(new Date(2026, 10, 8)).getDate()).toBe(2); // dimanche 8
    expect(startOfWeek(new Date(2026, 10, 9)).getDate()).toBe(9); // lundi suivant
  });

  it("liste sept jours consécutifs, et suit le décalage", () => {
    const jours = weekDays(mercredi);
    expect(jours.map((j) => j.getDate())).toEqual([2, 3, 4, 5, 6, 7, 8]);
    expect(weekDays(mercredi, -1)[0]?.getDate()).toBe(26); // 26 octobre
    expect(weekDays(mercredi, 1)[0]?.getDate()).toBe(9);
  });

  it("compare les jours sans tenir compte de l'heure", () => {
    expect(isSameDay(new Date(2026, 10, 4, 1), new Date(2026, 10, 4, 23))).toBe(true);
    expect(isSameDay(new Date(2026, 10, 4), new Date(2026, 10, 5))).toBe(false);
  });
});

describe("countInWeek", () => {
  const instants = [
    new Date(2026, 10, 2, 8).toISOString(), // lundi de la semaine
    new Date(2026, 10, 8, 23).toISOString(), // dimanche de la semaine
    new Date(2026, 10, 9, 8).toISOString(), // lundi suivant
    new Date(2026, 10, 1, 12).toISOString(), // dimanche précédent
    new Date(2026, 9, 28, 12).toISOString(), // semaine précédente
  ];

  it("compte la semaine courante et la précédente séparément", () => {
    expect(countInWeek(instants, mercredi)).toBe(2);
    expect(countInWeek(instants, mercredi, -1)).toBe(2);
    expect(countInWeek(instants, mercredi, 1)).toBe(1);
  });
});

describe("weeklyPercent", () => {
  it("n'existe pas sans semaine de référence", () => {
    expect(weeklyPercent(4, 0)).toBeNull();
  });

  it("mesure la variation réelle", () => {
    expect(weeklyPercent(4, 2)).toBe(100);
    expect(weeklyPercent(1, 3)).toBe(-66.7);
    expect(weeklyPercent(2, 2)).toBe(0);
  });
});
