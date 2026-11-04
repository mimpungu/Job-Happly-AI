export const formatPercentValue = (valeur: number): string =>
  `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(valeur)} %`;

export function formatMoney(montant: string, devise: string | null): string {
  const valeur = Number(montant);
  if (devise) {
    return new Intl.NumberFormat("fr-FR", { style: "currency", currency: devise }).format(valeur);
  }
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(valeur);
}
