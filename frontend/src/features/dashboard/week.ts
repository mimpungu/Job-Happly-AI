/** Semaine civile du lundi au dimanche, en heure locale (le navigateur de l'utilisateur). */

const JOUR_MS = 86_400_000;

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** Lundi de la semaine contenant `date`, plus `decalage` semaines. */
export function startOfWeek(date: Date, decalage = 0): Date {
  const debut = startOfDay(date);
  const depuisLundi = (debut.getDay() + 6) % 7;
  return new Date(
    debut.getFullYear(),
    debut.getMonth(),
    debut.getDate() - depuisLundi + decalage * 7,
  );
}

export function weekDays(date: Date, decalage = 0): Date[] {
  const lundi = startOfWeek(date, decalage);
  return Array.from(
    { length: 7 },
    (_, i) => new Date(lundi.getFullYear(), lundi.getMonth(), lundi.getDate() + i),
  );
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** Nombre d'instants ISO tombant dans la semaine de `reference` décalée de `decalage` semaines. */
export function countInWeek(instants: readonly string[], reference: Date, decalage = 0): number {
  const debut = startOfWeek(reference, decalage).getTime();
  const fin = debut + 7 * JOUR_MS;
  return instants.filter((iso) => {
    const t = new Date(iso).getTime();
    return t >= debut && t < fin;
  }).length;
}

/** Variation en % entre deux semaines ; `null` sans semaine de référence. */
export function weeklyPercent(courant: number, precedent: number): number | null {
  if (precedent <= 0) return null;
  return Math.round(((courant - precedent) / precedent) * 1000) / 10;
}
