import Link from "next/link";

import { Panel } from "@/components/ui/card";

/**
 * Stockage, sauvegarde et import (TASK-017-24). Informatif : l'application ne lance aucune
 * sauvegarde elle-même, elle indique honnêtement où sont les données et comment les sauvegarder.
 */
export function StorageBackupPanel() {
  return (
    <Panel title="Stockage, sauvegarde et import">
      <div className="flex flex-col gap-3 text-sm text-foreground-muted">
        <p>
          <strong className="text-foreground">Stockage.</strong> Vos données restent sur cette
          machine : la base PostgreSQL locale et le dossier des fichiers (CV importés, PDF et LaTeX
          générés). Rien n&apos;est envoyé à un service tiers sans votre accord.
        </p>
        <p>
          <strong className="text-foreground">Sauvegarde.</strong> Elle se fait hors de
          l&apos;application, base et fichiers ensemble, avec{" "}
          <code className="rounded bg-background-secondary px-1">
            infrastructure/scripts/backup.sh
          </code>{" "}
          (restauration avec{" "}
          <code className="rounded bg-background-secondary px-1">restore.sh</code>
          ). Faites aussi une copie hors de cette machine. La procédure complète est dans{" "}
          <code className="rounded bg-background-secondary px-1">
            docs/operations/BACKUP_RESTORE.md
          </code>
          .
        </p>
        <p>
          <strong className="text-foreground">Export.</strong> « Mes données » ci-dessus produit un
          ZIP lisible : un fichier par table et vos PDF générés.
        </p>
        <p>
          <strong className="text-foreground">Import.</strong> Un CV (PDF, DOCX ou texte)
          s&apos;importe depuis l&apos;
          <Link href="/cv-studio" className="underline">
            Espace CV
          </Link>
          ; vos offres peuvent être ajoutées à la main ou collectées depuis les sources ci-dessus.
        </p>
      </div>
    </Panel>
  );
}
