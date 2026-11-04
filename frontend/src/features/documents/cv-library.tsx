"use client";

import { FileText } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/cn";
import { downloadUrl } from "@/services/documents";
import type {
  AiRewriteMeta,
  LengthTarget,
  ResumeDocument,
  ResumeStyle,
  RewriteMode,
} from "@/types/documents";

import { formatDate, formatSize } from "./format";
import { OfferSelect } from "./offer-select";
import { useGenerateResume, useResumes } from "./use-documents";
import { TaskCostNote } from "@/features/ai/task-cost-note";

const STYLES: { value: ResumeStyle; label: string }[] = [
  { value: "classic", label: "Classique" },
  { value: "modern", label: "Moderne" },
  { value: "compact", label: "Compact" },
];
const LENGTHS: { value: LengthTarget; label: string }[] = [
  { value: "auto", label: "Automatique" },
  { value: "one_page", label: "Une page" },
  { value: "two_pages", label: "Deux pages" },
];
const REWRITES: { value: RewriteMode; label: string }[] = [
  { value: "none", label: "Sans IA : mes réalisations telles quelles" },
  { value: "local", label: "Reformuler avec un modèle local (rien ne quitte ma machine)" },
  {
    value: "ai",
    label: "Reformuler avec l'IA (selon mes réglages et ma politique de confidentialité)",
  },
];

function RewriteNotice({ meta }: { meta: AiRewriteMeta | null | undefined }) {
  if (!meta || meta.status === "not_requested") return null;
  if (meta.status === "unavailable") {
    return (
      <p role="status" className="text-sm text-foreground-muted">
        <Badge variant="warning">Reformulation indisponible</Badge> {meta.reason} Vos réalisations
        d&apos;origine ont été conservées.
      </p>
    );
  }
  return (
    <p className="text-sm text-foreground-muted">
      <Badge variant="accent">Reformulation</Badge> {meta.rewritten} réalisation(s) reformulée(s)
      {meta.rejected > 0 ? `, ${meta.rejected} écartée(s) par le contrôle des faits` : ""}.
    </p>
  );
}

function ResumeCard({ document }: { document: ResumeDocument }) {
  const derniere = document.versions[document.versions.length - 1];
  return (
    <li className="flex flex-col gap-2 py-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{document.title}</span>
        <span className="text-foreground-muted">{formatDate(document.created_at)}</span>
      </div>
      {document.versions.map((v) => (
        <div key={v.id} className="flex flex-col gap-1 rounded-md border border-border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span>Version {v.version}</span>
            <span className="text-foreground-muted">{formatSize(v.size_bytes)}</span>
            {v.ats_report ? (
              <Badge variant={v.ats_report.passed ? "success" : "warning"}>
                ATS {v.ats_report.score}/100
              </Badge>
            ) : null}
            {v.ats_report ? (
              <span className="text-foreground-muted">{v.ats_report.page_count} page(s)</span>
            ) : null}
          </div>
          {v.ats_report && v.ats_report.keywords_missing.length > 0 ? (
            <p className="text-foreground-muted">
              Mots-clés de l&apos;offre absents de votre profil (jamais ajoutés) :{" "}
              {v.ats_report.keywords_missing.join(", ")}.
            </p>
          ) : null}
          <RewriteNotice meta={v.generation?.ai_rewrite} />
          <div className="flex flex-wrap gap-2">
            <a
              className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
              href={downloadUrl("resumes", document.id, v.version, "pdf")}
              download
              aria-label={`Télécharger le PDF — ${document.title}, version ${v.version}`}
            >
              PDF
            </a>
            <a
              className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
              href={downloadUrl("resumes", document.id, v.version, "latex")}
              download
              aria-label={`Télécharger le source LaTeX — ${document.title}, version ${v.version}`}
            >
              LaTeX
            </a>
          </div>
        </div>
      ))}
      {derniere ? null : <p className="text-foreground-muted">Aucune version.</p>}
    </li>
  );
}

export function CvLibrary() {
  const cvs = useResumes();
  const generer = useGenerateResume();
  const [offre, setOffre] = useState("");
  const [style, setStyle] = useState<ResumeStyle>("classic");
  const [longueur, setLongueur] = useState<LengthTarget>("auto");
  const [reecriture, setReecriture] = useState<RewriteMode>("none");

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    generer.mutate(
      {
        ...(offre ? { offer_id: offre } : {}),
        style,
        length_target: longueur,
        language: "fr",
        rewrite_mode: reecriture,
      },
      {
        onSuccess: () => toast.success("CV généré."),
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <Panel title="Générer un CV">
        <form onSubmit={soumettre} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field
              label="Offre ciblée"
              hint="Facultatif. Sans offre, le CV est général. Seuls des faits de votre profil validé sont utilisés."
            >
              {(c) => (
                <OfferSelect
                  id={c.id}
                  value={offre}
                  onChange={setOffre}
                  placeholder="CV général (aucune offre)"
                  describedBy={c["aria-describedby"]}
                />
              )}
            </Field>
          </div>
          <Field label="Style">
            {(c) => (
              <Select
                {...c}
                value={style}
                options={STYLES}
                onChange={(e) => setStyle(e.target.value as ResumeStyle)}
              />
            )}
          </Field>
          <Field label="Longueur">
            {(c) => (
              <Select
                {...c}
                value={longueur}
                options={LENGTHS}
                onChange={(e) => setLongueur(e.target.value as LengthTarget)}
              />
            )}
          </Field>
          <div className="sm:col-span-2">
            <Field label="Reformulation des réalisations">
              {(c) => (
                <Select
                  {...c}
                  value={reecriture}
                  options={REWRITES}
                  onChange={(e) => setReecriture(e.target.value as RewriteMode)}
                />
              )}
            </Field>
          </div>
          {reecriture === "ai" ? (
            <div className="sm:col-span-2">
              <TaskCostNote task="cv_rewrite" />
            </div>
          ) : null}
          <div className="sm:col-span-2">
            <Button type="submit" loading={generer.isPending}>
              Générer le CV
            </Button>
          </div>
        </form>
      </Panel>

      <Panel title="Mes CV">
        {cvs.isPending ? (
          <Skeleton className="h-32 w-full" role="status" aria-label="Chargement" />
        ) : cvs.isError ? (
          <EmptyState
            title="Impossible de charger vos CV"
            description={cvs.error.message}
            action={<Button onClick={() => void cvs.refetch()}>Réessayer</Button>}
          />
        ) : cvs.data.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Aucun CV généré"
            description="Validez votre profil maître puis générez votre premier CV, général ou ciblé sur une offre."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {cvs.data.map((d) => (
              <ResumeCard key={d.id} document={d} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
