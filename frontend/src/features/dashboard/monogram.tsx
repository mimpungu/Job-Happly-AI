import { cn } from "@/lib/cn";

const TEINTES = ["bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4"] as const;

function initiales(nom: string): string {
  const mots = nom.trim().split(/\s+/).filter(Boolean);
  return ((mots[0]?.[0] ?? "?") + (mots.length > 1 ? (mots[1]?.[0] ?? "") : "")).toUpperCase();
}

/** Avatar de repli : initiales sur une teinte stable choisie d'après le nom. */
export function Monogram({ name, className }: { name: string; className?: string }) {
  const somme = [...name].reduce((total, c) => total + c.charCodeAt(0), 0);
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-14 shrink-0 items-center justify-center rounded-full text-lg font-semibold text-on-chart",
        TEINTES[somme % TEINTES.length],
        className,
      )}
    >
      {initiales(name)}
    </span>
  );
}
