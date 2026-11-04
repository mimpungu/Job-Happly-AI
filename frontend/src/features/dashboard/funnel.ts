import type { Funnel } from "@/types/applications";

export interface FunnelStage {
  key: keyof Funnel;
  label: string;
  value: number;
  /** Étape précédente de l'entonnoir (absente pour la première). */
  previous: number | null;
  /** Part conservée depuis l'étape précédente, en % ; `null` sans étape précédente ou à vide. */
  conversion: number | null;
  /** Part perdue depuis l'étape précédente, en % (valeur positive) ; même règle que ci-dessus. */
  dropOff: number | null;
  /** Page où traiter le passage vers cette étape. */
  href: string;
  action: string;
}

const STAGES: readonly { key: keyof Funnel; label: string; href: string; action: string }[] = [
  { key: "offers", label: "Offres", href: "/jobs", action: "Voir les offres" },
  { key: "tracked", label: "Suivies", href: "/jobs", action: "Suivre davantage d'offres" },
  {
    key: "sent",
    label: "Envoyées",
    href: "/applications?status=to_apply",
    action: "Voir les candidatures à envoyer",
  },
  {
    key: "responses",
    label: "Réponses",
    href: "/applications?status=sent",
    action: "Voir les candidatures sans réponse",
  },
  {
    key: "offers_received",
    label: "Offres reçues",
    href: "/applications?status=interview",
    action: "Voir les entretiens",
  },
];

export function funnelStages(funnel: Funnel): FunnelStage[] {
  return STAGES.map((etape, i) => {
    const valeur = funnel[etape.key];
    const cle = STAGES[i - 1]?.key;
    const precedent = cle === undefined ? null : funnel[cle];
    const aSource = precedent !== null && precedent > 0;
    return {
      ...etape,
      value: valeur,
      previous: precedent,
      conversion: aSource ? Math.round((valeur / precedent) * 100) : null,
      dropOff: aSource ? Math.round(((precedent - valeur) / precedent) * 100) : null,
    };
  });
}

/** Graduation « ronde » de l'axe : 0 et quelques valeurs entières couvrant `max`. */
export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0, 1];
  const brut = max / count;
  const puissance = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 5, 10].map((m) => m * puissance).find((p) => p >= brut) ?? brut;
  const ticks: number[] = [];
  for (let v = 0; v < max + pas; v += pas) {
    ticks.push(v);
    if (v >= max) break;
  }
  return ticks;
}

/** Passage le plus coûteux en valeur absolue ; `null` sans donnée exploitable. */
export function biggestDrop(stages: readonly FunnelStage[]): FunnelStage | null {
  let pire: FunnelStage | null = null;
  for (const etape of stages) {
    if (etape.previous === null || etape.previous <= 0) continue;
    const perte = etape.previous - etape.value;
    if (perte > 0 && (pire === null || perte > (pire.previous ?? 0) - pire.value)) pire = etape;
  }
  return pire;
}
