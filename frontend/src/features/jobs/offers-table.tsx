"use client";

import { Bookmark, BookmarkCheck, EyeOff, Undo2 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { IconButton } from "@/components/ui/icon-button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScoreIndicator } from "@/features/matching/score-indicator";
import type { OfferState, OfferSummary } from "@/types/jobs";

import { formatDate, formatEmployment, formatRemote, formatSalary } from "./format";

export interface OffersTableProps {
  offers: readonly OfferSummary[];
  onChangeState: (offerId: string, state: OfferState | null) => void;
  /** Désactive les actions pendant une écriture en cours. */
  busy?: boolean;
}

export function OffersTable({ offers, onChangeState, busy = false }: OffersTableProps) {
  return (
    <Table aria-label="Résultats de la recherche">
      <TableHeader>
        <TableRow>
          <TableHead>Offre</TableHead>
          <TableHead>Compatibilité</TableHead>
          <TableHead>Lieu</TableHead>
          <TableHead>Contrat</TableHead>
          <TableHead>Télétravail</TableHead>
          <TableHead>Salaire</TableHead>
          <TableHead>Publiée</TableHead>
          <TableHead>Sources</TableHead>
          <TableHead>
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {offers.map((offre) => (
          <TableRow key={offre.id}>
            <TableCell className="min-w-56">
              <Link
                href={`/jobs/${offre.id}`}
                className="font-medium text-foreground underline-offset-4 hover:underline"
              >
                {offre.title}
              </Link>
              <p className="text-foreground-muted">{offre.company_name ?? "Entreprise inconnue"}</p>
              {offre.state === "saved" ? <Badge variant="accent">Sauvegardée</Badge> : null}
              {offre.state === "ignored" ? <Badge>Ignorée</Badge> : null}
            </TableCell>
            <TableCell>
              <ScoreIndicator score={offre.match_score} reliability={offre.match_reliability} />
            </TableCell>
            <TableCell>{offre.location ?? "Non renseigné"}</TableCell>
            <TableCell>{formatEmployment(offre.employment_type)}</TableCell>
            <TableCell>{formatRemote(offre.remote_type)}</TableCell>
            <TableCell className="whitespace-nowrap">{formatSalary(offre)}</TableCell>
            <TableCell className="whitespace-nowrap">{formatDate(offre.published_at)}</TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {offre.source_keys.map((cle) => (
                  <Badge key={cle}>{cle}</Badge>
                ))}
              </div>
            </TableCell>
            <TableCell>
              <div className="flex gap-1">
                <IconButton
                  size="sm"
                  disabled={busy}
                  aria-label={
                    offre.state === "saved"
                      ? `Retirer des offres sauvegardées : ${offre.title}`
                      : `Sauvegarder l'offre : ${offre.title}`
                  }
                  onClick={() => onChangeState(offre.id, offre.state === "saved" ? null : "saved")}
                >
                  {offre.state === "saved" ? (
                    <BookmarkCheck className="size-4" aria-hidden="true" />
                  ) : (
                    <Bookmark className="size-4" aria-hidden="true" />
                  )}
                </IconButton>
                <IconButton
                  size="sm"
                  disabled={busy}
                  aria-label={
                    offre.state === "ignored"
                      ? `Ne plus ignorer l'offre : ${offre.title}`
                      : `Ignorer l'offre : ${offre.title}`
                  }
                  onClick={() =>
                    onChangeState(offre.id, offre.state === "ignored" ? null : "ignored")
                  }
                >
                  {offre.state === "ignored" ? (
                    <Undo2 className="size-4" aria-hidden="true" />
                  ) : (
                    <EyeOff className="size-4" aria-hidden="true" />
                  )}
                </IconButton>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
