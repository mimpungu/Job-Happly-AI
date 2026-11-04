"use client";

import { Mail } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/cn";
import { downloadUrl } from "@/services/documents";
import type { CoverLetter } from "@/types/documents";

import { formatDate, formatSize } from "./format";
import { OfferSelect } from "./offer-select";
import { useGenerateLetter, useLetters } from "./use-documents";

function LetterCard({ letter }: { letter: CoverLetter }) {
  const derniere = letter.versions[letter.versions.length - 1];
  const audit = derniere?.audit;
  return (
    <li className="flex flex-col gap-3 py-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{letter.title}</span>
        <span className="text-foreground-muted">{formatDate(letter.created_at)}</span>
      </div>
      {derniere ? (
        <div className="flex flex-wrap items-center gap-2">
          <span>Version {derniere.version}</span>
          <span className="text-foreground-muted">{formatSize(derniere.size_bytes)}</span>
          {audit ? (
            <>
              <Badge variant={audit.passed ? "success" : "warning"}>
                Qualité {audit.score}/100
              </Badge>
              <span className="text-foreground-muted">{audit.word_count} mots</span>
              <Badge variant={audit.cv_coherent ? "success" : "danger"}>
                {audit.cv_coherent ? "Cohérente avec le CV" : "Incohérence avec le CV"}
              </Badge>
            </>
          ) : null}
        </div>
      ) : null}
      {audit && audit.issues.length > 0 ? (
        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer font-medium">
            Points à vérifier ({audit.issues.length})
          </summary>
          <ul className="mt-2 list-disc pl-5">
            {audit.issues.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        </details>
      ) : null}
      {derniere ? (
        <div className="flex flex-wrap gap-2">
          <a
            className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
            href={downloadUrl("cover-letters", letter.id, derniere.version, "pdf")}
            download
            aria-label={`Télécharger le PDF — ${letter.title}`}
          >
            PDF
          </a>
          <a
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
            href={downloadUrl("cover-letters", letter.id, derniere.version, "latex")}
            download
            aria-label={`Télécharger le source LaTeX — ${letter.title}`}
          >
            LaTeX
          </a>
        </div>
      ) : null}
    </li>
  );
}

/** Texte de la lettre qui vient d'être générée : seul le PDF est conservé ensuite (téléchargeable). */
function LetterPreview({ letter }: { letter: CoverLetter }) {
  const c = letter.content;
  if (!c) return null;
  return (
    <Panel title="Relire la lettre avant envoi">
      <div className="flex flex-col gap-3 whitespace-pre-line text-sm leading-relaxed">
        <p>
          <strong>{c.subject}</strong>
        </p>
        <p>{c.salutation}</p>
        <p>{c.introduction}</p>
        <p>{c.background_highlight}</p>
        <p>{c.added_value}</p>
        <p>{c.closing_and_call_to_action}</p>
        <p>{c.complimentary_close}</p>
        <p>{c.signature}</p>
      </div>
      <p className="mt-3 text-xs text-foreground-muted">
        Relisez-la : vous l&apos;envoyez vous-même, l&apos;application n&apos;envoie jamais rien. Ce
        texte n&apos;est affiché qu&apos;à la génération ; ensuite, le PDF fait foi.
      </p>
    </Panel>
  );
}

export function LettersPage() {
  const lettres = useLetters();
  const generer = useGenerateLetter();
  const [offre, setOffre] = useState("");
  const [langue, setLangue] = useState<"fr" | "en">("fr");
  const [destinataire, setDestinataire] = useState("");
  const [motivation, setMotivation] = useState("");
  const [generee, setGeneree] = useState<CoverLetter | null>(null);

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    if (!offre) return;
    generer.mutate(
      {
        offer_id: offre,
        language: langue,
        ...(destinataire.trim() ? { recipient_name: destinataire.trim() } : {}),
        ...(motivation.trim() ? { motivation: motivation.trim() } : {}),
      },
      {
        onSuccess: (lettre) => {
          setGeneree(lettre);
          toast.success("Lettre générée.");
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">Lettres de motivation</h1>

      <Panel title="Générer une lettre">
        <form onSubmit={soumettre} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field
              label="Offre ciblée"
              hint="La lettre n'utilise que les faits de votre profil validé et de l'offre."
            >
              {(c) => (
                <OfferSelect
                  id={c.id}
                  value={offre}
                  onChange={setOffre}
                  placeholder="Choisir une offre"
                  describedBy={c["aria-describedby"]}
                />
              )}
            </Field>
          </div>
          <Field label="Langue">
            {(c) => (
              <Select
                {...c}
                value={langue}
                options={[
                  { value: "fr", label: "Français" },
                  { value: "en", label: "Anglais" },
                ]}
                onChange={(e) => setLangue(e.target.value as "fr" | "en")}
              />
            )}
          </Field>
          <Field label="Destinataire (facultatif)">
            {(c) => (
              <Input
                {...c}
                maxLength={200}
                value={destinataire}
                onChange={(e) => setDestinataire(e.target.value)}
              />
            )}
          </Field>
          <div className="sm:col-span-2">
            <Field
              label="Votre motivation (facultatif)"
              hint="Votre texte est repris tel quel : il n'est jamais réécrit ni jugé."
            >
              {(c) => (
                <Textarea
                  {...c}
                  rows={4}
                  maxLength={1500}
                  value={motivation}
                  onChange={(e) => setMotivation(e.target.value)}
                />
              )}
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" loading={generer.isPending} disabled={!offre}>
              Générer la lettre
            </Button>
          </div>
        </form>
      </Panel>

      {generee ? <LetterPreview letter={generee} /> : null}

      <Panel title="Mes lettres">
        {lettres.isPending ? (
          <Skeleton className="h-32 w-full" role="status" aria-label="Chargement" />
        ) : lettres.isError ? (
          <EmptyState
            title="Impossible de charger vos lettres"
            description={lettres.error.message}
            action={<Button onClick={() => void lettres.refetch()}>Réessayer</Button>}
          />
        ) : lettres.data.length === 0 ? (
          <EmptyState
            icon={Mail}
            title="Aucune lettre"
            description="Choisissez une offre pour générer une lettre adaptée, à relire avant de l'envoyer vous-même."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {lettres.data.map((l) => (
              <LetterCard key={l.id} letter={l} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
