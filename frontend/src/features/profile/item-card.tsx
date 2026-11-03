"use client";

import { Check, Trash2 } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";

export interface ItemCardProps {
  title: string;
  origin: "imported" | "manual";
  validated: boolean;
  /** Champs obligatoires manquants : empêchent la confirmation. */
  missing: readonly string[];
  sourceText: string | null;
  onConfirm: () => void;
  onRemove: () => void;
  children: ReactNode;
}

/**
 * Carte d'un élément du profil : dit d'où il vient, s'il a été relu, et ce qu'il lui manque.
 * L'état est toujours exprimé par un texte, jamais par la seule couleur.
 */
export function ItemCard({
  title,
  origin,
  validated,
  missing,
  sourceText,
  onConfirm,
  onRemove,
  children,
}: ItemCardProps) {
  return (
    <li className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          {origin === "imported" ? <Badge>Importé</Badge> : <Badge>Saisi</Badge>}
          {validated ? (
            <Badge variant="success">Confirmé</Badge>
          ) : (
            <Badge variant="warning">À confirmer</Badge>
          )}
          {missing.length > 0 ? <Badge variant="danger">Incomplet</Badge> : null}
        </div>
        <div className="flex items-center gap-1">
          <IconButton size="sm" aria-label={`Retirer : ${title}`} onClick={onRemove}>
            <Trash2 className="size-4" aria-hidden="true" />
          </IconButton>
        </div>
      </div>

      {missing.length > 0 ? (
        <p className="text-xs text-foreground-muted">
          À renseigner pour confirmer : {missing.join(", ")}.
        </p>
      ) : null}

      {children}

      {/* Après les champs : on relit, puis on confirme (ordre naturel au clavier aussi). */}
      {validated ? null : (
        <div>
          <Button
            size="sm"
            variant="secondary"
            disabled={missing.length > 0}
            onClick={onConfirm}
            aria-label={`Confirmer : ${title}`}
          >
            <Check className="size-4" aria-hidden="true" />
            Confirmer
          </Button>
        </div>
      )}

      {sourceText ? (
        <details className="text-xs text-foreground-muted">
          <summary className="cursor-pointer text-foreground-muted hover:text-foreground">
            Voir l&apos;extrait du CV d&apos;origine
          </summary>
          {/* Texte brut : c'est une donnée issue d'un document, jamais du HTML. */}
          <pre className="mt-2 whitespace-pre-wrap rounded-md bg-background-secondary p-3 font-sans">
            {sourceText}
          </pre>
        </details>
      ) : null}
    </li>
  );
}
