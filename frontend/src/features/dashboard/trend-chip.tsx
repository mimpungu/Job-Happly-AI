import { cn } from "@/lib/cn";

/**
 * Variation en % par rapport à la période précédente. Sans période de référence (`percent`
 * nul), aucune variation n'est inventée : on le dit.
 */
export function TrendChip({
  percent,
  period,
  className,
}: {
  percent: number | null;
  /** Texte de la période, ex. « ce mois-ci ». */
  period: string;
  className?: string;
}) {
  if (percent === null) {
    return (
      <span className={cn("text-sm text-foreground-muted", className)}>Pas de comparaison</span>
    );
  }
  const signe = percent > 0 ? "+" : percent < 0 ? "−" : "";
  const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(
    Math.abs(percent),
  );
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <span
        className={cn(
          "rounded-full px-2.5 py-0.5 text-sm font-semibold",
          percent > 0 && "bg-success-soft text-on-success-soft",
          percent < 0 && "bg-danger-soft text-on-danger-soft",
          percent === 0 && "bg-surface text-foreground-muted",
        )}
      >
        <span className="sr-only">Variation par rapport à la période précédente : </span>
        {signe}
        {nombre} %
      </span>
      <span className="text-sm text-foreground-muted">{period}</span>
    </span>
  );
}
