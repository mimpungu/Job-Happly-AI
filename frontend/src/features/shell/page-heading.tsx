"use client";

import type { ReactNode } from "react";
import { useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

const sansAbonnement = () => () => {};

/**
 * Titre de page affiché dans l'en-tête de la coque, à gauche des actions. Il est rendu dans
 * l'emplacement `#page-heading` (absent côté serveur, d'où la lecture après hydratation).
 */
export function PageHeading({ title, subtitle }: { title: ReactNode; subtitle?: string }) {
  const emplacement = useSyncExternalStore(
    sansAbonnement,
    () => document.getElementById("page-heading"),
    () => null,
  );
  if (!emplacement) return null;
  return createPortal(
    <div className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold text-foreground sm:text-3xl xl:text-4xl">{title}</h1>
      {subtitle ? <p className="text-sm text-foreground-muted sm:text-base">{subtitle}</p> : null}
    </div>,
    emplacement,
  );
}
