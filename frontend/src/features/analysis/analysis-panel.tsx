"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Mobility, OfferAnalysis } from "@/types/analysis";

import { useAISummary, useOfferAnalysis } from "./use-analysis";

const LANGUES: Record<string, string> = {
  fr: "Français",
  en: "Anglais",
  de: "Allemand",
  es: "Espagnol",
  it: "Italien",
  pt: "Portugais",
  nl: "Néerlandais",
};

const VISA: Record<NonNullable<Mobility["visa"]>, string> = {
  sponsorship_offered: "Sponsoring de visa proposé",
  no_sponsorship: "Pas de sponsoring de visa",
  work_authorization_required: "Autorisation de travail exigée",
};

export function libelleExperience(a: OfferAnalysis): string | null {
  if (a.years_experience === null) return null;
  const annees = `${a.years_experience} an${a.years_experience > 1 ? "s" : ""}`;
  return a.years_mandatory ? `${annees} minimum` : `${annees} (souhaité)`;
}

function Liste({
  titre,
  elements,
  variante,
}: {
  titre: string;
  elements: string[];
  variante?: "accent" | "neutral";
}) {
  if (elements.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-sm font-medium text-foreground">{titre}</h3>
      <ul aria-label={titre} className="flex flex-wrap gap-2">
        {elements.map((e) => (
          <li key={e}>
            <Badge variant={variante ?? "neutral"}>{e}</Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ResumeIA({ offerId }: { offerId: string }) {
  const resume = useAISummary(offerId);
  return (
    <div className="flex flex-col gap-2 border-t border-border pt-3">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" loading={resume.isPending} onClick={() => resume.mutate()}>
          Résumé par IA
        </Button>
        <p className="text-xs text-foreground-muted">
          Facultatif. Seul le texte public de l&apos;offre est transmis, jamais votre CV.
        </p>
      </div>
      {resume.isError ? (
        <p role="alert" className="text-sm text-danger">
          {resume.error.message}{" "}
          <Link href="/ai-center" className="underline">
            Ouvrir le Centre IA
          </Link>
        </p>
      ) : null}
      {resume.isSuccess ? (
        <div role="status" className="flex flex-col gap-1 rounded-md border border-border p-3">
          <p className="text-xs text-foreground-muted">
            {resume.data.provider} · {resume.data.model}
            {resume.data.cache_hit ? " · déjà résumé (cache, sans coût)" : ""}
          </p>
          <p className="text-sm text-foreground">{resume.data.summary}</p>
          {resume.data.key_points.length > 0 ? (
            <ul className="list-disc pl-5 text-sm text-foreground-muted">
              {resume.data.key_points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Analyse d'une offre par règles : n'affiche que ce qui est écrit dans l'annonce. */
export function AnalysisPanel({ offerId }: { offerId: string }) {
  const requete = useOfferAnalysis(offerId);

  if (requete.isPending) return <Skeleton className="h-40 w-full" />;
  if (requete.isError) {
    return (
      <Panel title="Analyse de l'offre">
        <div className="flex flex-col items-start gap-3">
          <p role="alert" className="text-sm text-danger">
            {requete.error.message}
          </p>
          <Button variant="secondary" onClick={() => void requete.refetch()}>
            Réessayer
          </Button>
        </div>
      </Panel>
    );
  }
  const a = requete.data.analysis;
  const experience = libelleExperience(a);
  return (
    <Panel title="Analyse de l'offre">
      <div className="flex flex-col gap-4 text-sm">
        <p className="text-xs text-foreground-muted">
          Lue dans le texte de l&apos;annonce par des règles (sans IA, sans coût). Ce qui n&apos;y
          est pas écrit n&apos;est pas deviné.
        </p>
        {a.summary ? (
          <div className="flex flex-col gap-1">
            <h3 className="font-medium text-foreground">Extrait de l&apos;annonce</h3>
            <p className="text-foreground-muted">{a.summary}</p>
          </div>
        ) : null}
        {a.missions.length > 0 ? (
          <div className="flex flex-col gap-1">
            <h3 className="font-medium text-foreground">Missions</h3>
            <ul className="list-disc pl-5 text-foreground-muted">
              {a.missions.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <Liste titre="Compétences obligatoires" elements={a.mandatory_skills} variante="accent" />
        <Liste titre="Compétences attendues" elements={a.expected_skills} />
        <Liste titre="Compétences souhaitées" elements={a.desired_skills} />
        <Liste titre="Outils et technologies cités" elements={a.technologies} />
        {experience ? (
          <p>
            <span className="font-medium text-foreground">Expérience : </span>
            <span className="text-foreground-muted">{experience}</span>
          </p>
        ) : null}
        {a.languages.length > 0 ? (
          <div className="flex flex-col gap-1">
            <h3 className="font-medium text-foreground">Langues</h3>
            <ul className="text-foreground-muted">
              {a.languages.map((l) => (
                <li key={l.language}>
                  {LANGUES[l.language] ?? l.language}
                  {l.level ? ` — ${l.level}` : ""} ({l.mandatory ? "exigé" : "souhaité"})
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {!a.mobility.visa && !a.mobility.relocation_offered && !a.mobility.travel ? null : (
          <div className="flex flex-col gap-1">
            <h3 className="font-medium text-foreground">Mobilité et visa</h3>
            <ul className="text-foreground-muted">
              {a.mobility.visa ? <li>{VISA[a.mobility.visa]}</li> : null}
              {a.mobility.relocation_offered ? <li>Aide à la relocalisation mentionnée</li> : null}
              {a.mobility.travel ? <li>Déplacements : {a.mobility.travel}</li> : null}
            </ul>
          </div>
        )}
        {a.missing.length > 0 ? (
          <div className="flex flex-col gap-1">
            <h3 className="font-medium text-foreground">
              Informations que l&apos;offre ne donne pas
            </h3>
            <ul className="list-disc pl-5 text-foreground-muted">
              {a.missing.map((m) => (
                <li key={m.code}>{m.label}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <ResumeIA offerId={offerId} />
      </div>
    </Panel>
  );
}
