import type { OfferSummary } from "@/types/jobs";

import { EMPLOYMENT_TYPES, REMOTE_TYPES } from "./filters";
import { formatDateParts, formatNumber, getTimeZone } from "@/lib/regional";

const NON_RENSEIGNE = "Non renseigné";

function libelle(
  liste: readonly { value: string; label: string }[],
  valeur: string | null,
): string {
  if (!valeur) return NON_RENSEIGNE;
  return liste.find((e) => e.value === valeur)?.label ?? valeur;
}

export const formatEmployment = (valeur: string | null) => libelle(EMPLOYMENT_TYPES, valeur);
export const formatRemote = (valeur: string | null) => libelle(REMOTE_TYPES, valeur);

/** Une absence de salaire n'est jamais affichée comme 0 : on dit qu'elle est inconnue. */
export function formatSalary(
  offre: Pick<OfferSummary, "salary_min" | "salary_max" | "salary_currency">,
): string {
  const { salary_min: min, salary_max: max, salary_currency: devise } = offre;
  if (min === null && max === null) return NON_RENSEIGNE;
  const nombre = (v: string) => formatNumber(Number(v), { maximumFractionDigits: 0 });
  const suffixe = devise ? ` ${devise}` : "";
  if (min !== null && max !== null && min !== max)
    return `${nombre(min)} – ${nombre(max)}${suffixe}`;
  return `${nombre((min ?? max) as string)}${suffixe}`;
}

/** Date au format de la langue choisie ; l'heure est ignorée car la source ne la garantit pas. */
export function formatDate(iso: string | null): string {
  if (!iso) return NON_RENSEIGNE;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return NON_RENSEIGNE;
  // Sans fuseau choisi, UTC : la source ne garantit pas l'heure, on évite de décaler le jour.
  return formatDateParts(date, { dateStyle: "medium", timeZone: getTimeZone() ?? "UTC" });
}
