import { Ellipsis, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useId, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface DashCardProps {
  title: string;
  icon?: LucideIcon;
  /** Lien « plus » en haut à droite (les trois points de la maquette) ; absent s'il n'y a pas de cible. */
  moreHref?: string;
  moreLabel?: string;
  className?: string;
  children: ReactNode;
}

/** Carte arrondie du tableau de bord : titre (h2), icône, lien d'approfondissement. */
export function DashCard({
  title,
  icon: Icon,
  moreHref,
  moreLabel,
  className,
  children,
}: DashCardProps) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className={cn("rounded-xl border border-border bg-shell p-6", className)}
    >
      <header className="flex items-center justify-between gap-3">
        <h2 id={id} className="flex items-center gap-3 text-xl font-semibold text-foreground">
          {Icon ? <Icon className="size-6 text-foreground-muted" aria-hidden="true" /> : null}
          {title}
        </h2>
        {moreHref ? (
          <Link
            href={moreHref}
            aria-label={moreLabel}
            className="rounded-full p-1 text-foreground-muted hover:text-foreground"
          >
            <Ellipsis className="size-6" aria-hidden="true" />
          </Link>
        ) : null}
      </header>
      {children}
    </section>
  );
}
