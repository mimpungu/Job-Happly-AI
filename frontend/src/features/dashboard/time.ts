const RTF = new Intl.RelativeTimeFormat("fr", { numeric: "auto" });

/** « il y a 2 h », « hier »… ; l'instant de référence est injecté pour rester testable. */
export function formatRelative(iso: string, maintenant: Date = new Date()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const secondes = Math.round((t - maintenant.getTime()) / 1000);
  const absolu = Math.abs(secondes);
  if (absolu < 60) return "à l'instant";
  if (absolu < 3600) return RTF.format(Math.round(secondes / 60), "minute");
  if (absolu < 86_400) return RTF.format(Math.round(secondes / 3600), "hour");
  if (absolu < 30 * 86_400) return RTF.format(Math.round(secondes / 86_400), "day");
  return RTF.format(Math.round(secondes / (30 * 86_400)), "month");
}
