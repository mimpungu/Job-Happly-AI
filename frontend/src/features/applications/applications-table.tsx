import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ApplicationItem } from "@/types/applications";

import { formatDay, isOverdue } from "./format";

export function ApplicationsTable({
  applications,
  now = new Date(),
}: {
  applications: readonly ApplicationItem[];
  /** Instant de référence pour signaler les relances échues (injecté pour les tests). */
  now?: Date;
}) {
  return (
    <Table aria-label="Candidatures">
      <TableHeader>
        <TableRow>
          <TableHead>Offre</TableHead>
          <TableHead>Statut</TableHead>
          <TableHead>Envoyée le</TableHead>
          <TableHead>Relance</TableHead>
          <TableHead>Mise à jour</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {applications.map((candidature) => (
          <TableRow key={candidature.id}>
            <TableCell className="min-w-56">
              <Link
                href={`/applications/${candidature.id}`}
                className="font-medium text-foreground underline-offset-4 hover:underline"
              >
                {candidature.offer?.title ?? "Offre introuvable"}
              </Link>
              <p className="text-foreground-muted">
                {candidature.offer?.company_name ?? "Entreprise inconnue"}
              </p>
            </TableCell>
            <TableCell>
              <StatusBadge status={candidature.status} />
            </TableCell>
            <TableCell className="whitespace-nowrap">{formatDay(candidature.applied_at)}</TableCell>
            <TableCell className="whitespace-nowrap">
              {candidature.follow_up_at ? (
                <span className="flex flex-col items-start gap-1">
                  {formatDay(candidature.follow_up_at)}
                  {isOverdue(candidature.follow_up_at, now) ? (
                    <Badge variant="warning">Échue</Badge>
                  ) : null}
                </span>
              ) : (
                "—"
              )}
            </TableCell>
            <TableCell className="whitespace-nowrap">{formatDay(candidature.updated_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
