"use client";

import { FileText, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import { ApiError } from "@/services/api-client";
import type { ItemSection, ProfileDocument } from "@/types/profile";

import {
  addItem,
  confirmItem,
  describePath,
  emptyDocument,
  hasContent,
  isDirty,
  normalizePath,
  patchItem,
  pendingReview,
  removeItem,
} from "./draft";
import { ProfileTabs } from "./profile-tabs";
import type { SectionProps } from "./sections";
import {
  useImportCv,
  useNewVersion,
  useProfile,
  useSaveDraft,
  useValidateProfile,
  useVersion,
  useVersions,
} from "./use-profile";

interface Probleme {
  field: string;
  message: string;
}

function problemesDe(erreur: unknown): Probleme[] {
  if (!(erreur instanceof ApiError)) return [];
  return erreur.details.map((d) => ({ field: normalizePath(d.field), message: d.message }));
}

export function ProfileEditor() {
  const profil = useProfile();
  const enregistrer = useSaveDraft();
  const valider = useValidateProfile();
  const nouvelleVersion = useNewVersion();
  const importer = useImportCv();

  const [draft, setDraft] = useState<ProfileDocument | null>(null);
  const [problemes, setProblemes] = useState<Probleme[]>([]);
  const [avertissements, setAvertissements] = useState<string[]>([]);
  const [importEnAttente, setImportEnAttente] = useState<ProfileDocument | null>(null);
  const fichier = useRef<HTMLInputElement>(null);

  const serveur = profil.data ?? null;
  const cleServeur = serveur
    ? `${serveur.meta.id}:${serveur.meta.updated_at}:${serveur.meta.status}`
    : null;

  // Le brouillon local repart du serveur à chaque changement côté serveur (chargement, sauvegarde,
  // validation, nouvelle version). Ajustement d'état pendant le rendu plutôt que dans un effet :
  // pas de rendu intermédiaire avec un brouillon périmé. Les modifications en cours ne sont
  // jamais écrasées autrement.
  const [cleVue, setCleVue] = useState<string | null>(null);
  if (cleServeur !== cleVue) {
    setCleVue(cleServeur);
    if (serveur) setDraft(serveur.document);
  }

  // Consultation d'une ancienne version : lecture seule, le brouillon en cours n'est pas touché.
  const versions = useVersions();
  const [versionVue, setVersionVue] = useState<number | null>(null);
  const versionConsultee =
    versionVue !== null && serveur && versionVue !== serveur.meta.version ? versionVue : null;
  const ancienne = useVersion(versionConsultee);

  if (profil.isPending) {
    return (
      <div className="flex flex-col gap-4">
        {/* Le titre de la page existe dès le chargement : repère pour la navigation au clavier. */}
        <h1 className="text-2xl font-semibold text-foreground">Espace CV</h1>
        <div className="flex flex-col gap-4" role="status" aria-label="Chargement du profil">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }
  if (profil.isError) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold text-foreground">Espace CV</h1>
        <EmptyState
          icon={FileText}
          title="Impossible de charger le profil"
          description={profil.error.message}
          action={<Button onClick={() => void profil.refetch()}>Réessayer</Button>}
        />
      </div>
    );
  }

  const lectureSeule = serveur?.meta.status === "validated";
  const sale = draft ? isDirty(draft, serveur?.document ?? null) : false;
  const aRelire = draft ? pendingReview(draft) : 0;

  const lireCv = (fichierChoisi: File) => {
    importer.mutate(fichierChoisi, {
      onSuccess: (resultat) => {
        setAvertissements(resultat.warnings);
        if (draft && hasContent(draft)) {
          setImportEnAttente(resultat.proposed_document);
        } else {
          setDraft(resultat.proposed_document);
          setProblemes([]);
          toast.success("CV lu. Relisez chaque élément, puis enregistrez.");
        }
      },
      onError: (erreur) => toast.error(erreur.message),
    });
  };

  const choisirFichier = () => fichier.current?.click();
  const zoneImport = (
    <>
      <input
        ref={fichier}
        type="file"
        accept=".pdf,.docx,.txt"
        className="sr-only"
        aria-label="Fichier du CV à importer"
        onChange={(e) => {
          const choisi = e.target.files?.[0];
          if (choisi) lireCv(choisi);
          e.target.value = "";
        }}
      />
      <Button variant="secondary" loading={importer.isPending} onClick={choisirFichier}>
        <Upload className="size-4" aria-hidden="true" />
        Importer un CV
      </Button>
    </>
  );

  if (!draft) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold text-foreground">Espace CV</h1>
        <EmptyState
          icon={FileText}
          title="Aucun CV maître"
          description="Importez votre CV (PDF, DOCX ou TXT) : il est lu localement, rien n'est conservé, et vous relisez chaque information avant de la valider. Vous pouvez aussi tout saisir à la main."
          action={
            <div className="flex flex-wrap justify-center gap-3">
              {zoneImport}
              <Button variant="ghost" onClick={() => setDraft(emptyDocument())}>
                Saisir à la main
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  const section: SectionProps = {
    doc: draft,
    onChange: setDraft,
    patch: (nom, index, patch) =>
      setDraft((d) => (d ? patchItem(d, nom as ItemSection, index, patch as never) : d)),
    add: (nom) => setDraft((d) => (d ? addItem(d, nom as ItemSection) : d)),
    remove: (nom, index) => setDraft((d) => (d ? removeItem(d, nom as ItemSection, index) : d)),
    confirm: (nom, index) => setDraft((d) => (d ? confirmItem(d, nom as ItemSection, index) : d)),
  };

  const sauvegarder = () =>
    enregistrer.mutate(draft, {
      onSuccess: () => {
        setProblemes([]);
        toast.success("Brouillon enregistré.");
      },
      onError: (erreur) => {
        setProblemes(problemesDe(erreur));
        toast.error(erreur.message);
      },
    });

  const validerProfil = () =>
    valider.mutate(undefined, {
      onSuccess: () => {
        setProblemes([]);
        toast.success("Profil validé.");
      },
      onError: (erreur) => {
        setProblemes(problemesDe(erreur));
        toast.error(erreur.message);
      },
    });

  const creerVersion = () =>
    nouvelleVersion.mutate(undefined, {
      onSuccess: (stocke) =>
        toast.success(`Version ${stocke.meta.version} créée : vous pouvez la modifier.`),
      onError: (erreur) => toast.error(erreur.message),
    });

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-foreground">Espace CV</h1>
          <div className="flex flex-wrap items-center gap-2">
            {serveur ? (
              <Badge variant={lectureSeule ? "success" : "neutral"}>
                Version {serveur.meta.version} · {lectureSeule ? "validée" : "brouillon"}
              </Badge>
            ) : (
              <Badge>Non enregistré</Badge>
            )}
            {sale ? <Badge variant="warning">Modifications non enregistrées</Badge> : null}
            {aRelire > 0 && !lectureSeule ? (
              <Badge variant="warning">
                {aRelire} élément{aRelire > 1 ? "s" : ""} à confirmer
              </Badge>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          {versions.data && versions.data.length > 1 ? (
            <div className="w-56">
              <Field label="Version affichée">
                {({ id }) => (
                  <Select
                    id={id}
                    options={versions.data.map((v) => ({
                      value: String(v.version),
                      label: `Version ${v.version} · ${v.status === "validated" ? "validée" : "brouillon"}${v.version === serveur?.meta.version ? " (actuelle)" : ""}`,
                    }))}
                    value={String(versionConsultee ?? serveur?.meta.version ?? "")}
                    onChange={(e) => setVersionVue(Number(e.target.value))}
                  />
                )}
              </Field>
            </div>
          ) : null}
          {versionConsultee ? null : lectureSeule ? (
            <Button loading={nouvelleVersion.isPending} onClick={creerVersion}>
              Créer une nouvelle version
            </Button>
          ) : (
            <>
              {zoneImport}
              <Button
                variant="secondary"
                loading={enregistrer.isPending}
                disabled={!sale}
                onClick={sauvegarder}
              >
                Enregistrer
              </Button>
              <Button
                loading={valider.isPending}
                disabled={sale || !serveur}
                onClick={validerProfil}
                title={sale ? "Enregistrez d'abord vos modifications." : undefined}
              >
                Valider le profil
              </Button>
            </>
          )}
        </div>
      </header>

      {lectureSeule ? (
        <p className="rounded-lg border border-border bg-surface p-4 text-sm text-foreground-muted">
          Cette version est validée et ne peut pas être modifiée. Créez une nouvelle version pour la
          faire évoluer : la version actuelle est conservée.
        </p>
      ) : null}

      {avertissements.length > 0 ? (
        <div
          role="status"
          className="rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm text-foreground"
        >
          <ul className="list-disc pl-5">
            {avertissements.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {problemes.length > 0 ? (
        <div
          role="alert"
          className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-foreground"
        >
          <p className="mb-2 font-medium">
            Le profil ne peut pas être enregistré ou validé tel quel :
          </p>
          <ul className="list-disc pl-5">
            {problemes.map((p) => (
              <li key={`${p.field}-${p.message}`}>
                {describePath(p.field)} — {p.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {versionConsultee ? (
        <section
          aria-label={`Consultation de la version ${versionConsultee}`}
          className="flex flex-col gap-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4 text-sm">
            <p className="text-foreground">
              Vous consultez la version {versionConsultee} en lecture seule.
            </p>
            <Button variant="secondary" size="sm" onClick={() => setVersionVue(null)}>
              Revenir à la version actuelle
            </Button>
          </div>
          {ancienne.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : ancienne.isError ? (
            <p role="alert" className="text-sm text-danger">
              {ancienne.error.message}
            </p>
          ) : (
            <ProfileTabs
              doc={ancienne.data.document}
              readOnly
              onChange={() => undefined}
              section={{ ...section, doc: ancienne.data.document }}
            />
          )}
        </section>
      ) : (
        <ProfileTabs doc={draft} readOnly={lectureSeule} onChange={setDraft} section={section} />
      )}

      <ConfirmDialog
        open={importEnAttente !== null}
        onOpenChange={(ouvert) => !ouvert && setImportEnAttente(null)}
        title="Remplacer le brouillon par ce CV ?"
        description="Le contenu actuel du brouillon sera remplacé par les informations lues dans le CV. Rien n'est enregistré tant que vous n'avez pas cliqué sur « Enregistrer »."
        confirmLabel="Remplacer"
        destructive
        onConfirm={() => {
          if (importEnAttente) setDraft(importEnAttente);
          setImportEnAttente(null);
          setProblemes([]);
          toast.success("CV lu. Relisez chaque élément, puis enregistrez.");
        }}
      />
    </div>
  );
}
