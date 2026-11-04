/**
 * Outils de recrutement (ATS) dont Happly AI sait lire les offres publiques.
 * Source unique des libellés : la liste suit les connecteurs du backend.
 */
export const ATS_LABELS: Record<string, string> = {
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
  workable: "Workable",
};

/** « Greenhouse, Lever, Ashby ou Workable » : pour les textes d'aide. */
export const SUPPORTED_ATS_TEXT = new Intl.ListFormat("fr", {
  style: "long",
  type: "disjunction",
}).format(Object.values(ATS_LABELS));

/** « Greenhouse, Lever, Ashby, Workable » : pour les énumérations. */
export const SUPPORTED_ATS_LIST = Object.values(ATS_LABELS).join(", ");

export function atsLabel(kind: string): string {
  return ATS_LABELS[kind] ?? kind;
}
