import { formatNumber } from "@/lib/regional";
export const formatPercentValue = (valeur: number): string =>
  `${formatNumber(valeur, { maximumFractionDigits: 1 })} %`;

export function formatMoney(montant: string, devise: string | null): string {
  const valeur = Number(montant);
  if (devise) {
    return formatNumber(valeur, { style: "currency", currency: devise });
  }
  return formatNumber(valeur, { maximumFractionDigits: 2 });
}
