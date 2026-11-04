"use client";

import { BriefcaseBusiness, Funnel, MapPin, Search } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { OfferFilters } from "@/types/jobs";

import { DEFAULT_FILTERS, EMPLOYMENT_TYPES, REMOTE_TYPES } from "./filters";

const SCORES_MINIMAUX = [50, 60, 70, 80].map((n) => ({
  value: String(n),
  label: `${n} et plus`,
}));

export interface SearchFormProps {
  filters: OfferFilters;
  onSubmit: (filters: OfferFilters) => void;
  onSaveSearch?: (filters: OfferFilters) => void;
}

/** Nombre de critères actifs hors de la barre principale : affiché sur « Tous les filtres ». */
export function countAdvancedFilters(filters: OfferFilters): number {
  return (
    [
      filters.company,
      filters.country,
      filters.remoteType,
      filters.salaryMin,
      filters.language,
      filters.maxExperience,
      filters.titles,
      filters.minScore,
      filters.publishedSince,
    ].filter((valeur) => valeur.trim() !== "").length + (filters.multilingual ? 1 : 0)
  );
}

// Champs de la barre : fond transparent dans une pastille, séparés par un filet.
const champBarre =
  "h-12 w-full bg-transparent px-2 text-sm text-foreground placeholder:text-foreground-subtle";

/**
 * Barre de recherche (intitulé, contrat, ville) et fenêtre « Tous les filtres ». Les saisies
 * restent locales jusqu'à « Rechercher » : on n'interroge pas l'API à chaque frappe, et la
 * recherche affichée est toujours celle de l'URL.
 */
export function SearchForm({ filters, onSubmit, onSaveSearch }: SearchFormProps) {
  const [draft, setDraft] = useState(filters);
  const [ouvert, setOuvert] = useState(false);
  const maj = <K extends keyof OfferFilters>(cle: K, valeur: OfferFilters[K]) =>
    setDraft((courant) => ({ ...courant, [cle]: valeur }));

  const soumettre = (evenement: FormEvent) => {
    evenement.preventDefault();
    onSubmit({ ...draft, page: 1 });
  };
  const appliquer = (evenement: FormEvent) => {
    // La fenêtre est rendue dans un portail : sans cela, l'événement remonterait à la barre.
    evenement.preventDefault();
    evenement.stopPropagation();
    onSubmit({ ...draft, page: 1 });
    setOuvert(false);
  };
  const reinitialiser = () => {
    const vide = { ...DEFAULT_FILTERS, sort: draft.sort, state: draft.state };
    setDraft(vide);
    onSubmit(vide);
  };
  const salaireIncomplet = draft.salaryMin.trim() !== "" && !draft.salaryCurrency.trim();
  const actifs = countAdvancedFilters(filters);

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-3">
      <form
        aria-label="Recherche d'offres"
        onSubmit={soumettre}
        className="flex flex-col gap-1 rounded-xl bg-surface-elevated p-1 md:flex-row md:items-center md:gap-0 md:rounded-full md:pl-4 md:pr-1"
      >
        <label className="flex flex-[2] items-center gap-2 px-2 md:px-0">
          <Search className="size-5 shrink-0 text-foreground-muted" aria-hidden="true" />
          <input
            aria-label="Intitulé ou mot-clé"
            placeholder="Offre, entreprise ou mot-clé"
            className={champBarre}
            value={draft.text}
            maxLength={200}
            onChange={(e) => maj("text", e.target.value)}
          />
        </label>
        <label className="flex flex-1 items-center gap-2 border-t border-border px-2 md:border-l md:border-t-0 md:px-4">
          <BriefcaseBusiness className="size-5 shrink-0 text-foreground-muted" aria-hidden="true" />
          <select
            aria-label="Contrat"
            className={champBarre}
            value={draft.employmentType}
            onChange={(e) => maj("employmentType", e.target.value)}
          >
            <option value="">Contrat</option>
            {EMPLOYMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 items-center gap-2 border-t border-border px-2 md:border-l md:border-t-0 md:px-4">
          <MapPin className="size-5 shrink-0 text-foreground-muted" aria-hidden="true" />
          <input
            aria-label="Ville"
            placeholder="Ville, département…"
            className={champBarre}
            value={draft.city}
            maxLength={200}
            onChange={(e) => maj("city", e.target.value)}
          />
        </label>
        <Button type="submit" className="md:rounded-full">
          Rechercher
        </Button>
      </form>

      <div className="flex flex-wrap items-center gap-3">
        <Dialog open={ouvert} onOpenChange={setOuvert}>
          <DialogTrigger asChild>
            <Button variant="secondary">
              <Funnel className="size-4" aria-hidden="true" />
              Tous les filtres
              {actifs > 0 ? (
                <Badge
                  variant="accent"
                  aria-label={`${actifs} filtre${actifs > 1 ? "s" : ""} actif${actifs > 1 ? "s" : ""}`}
                >
                  {actifs}
                </Badge>
              ) : null}
            </Button>
          </DialogTrigger>
          <DialogContent
            title="Tous les filtres"
            description="Affinez la recherche. Les critères s'appliquent ensemble."
            className="max-h-[85vh] max-w-2xl overflow-y-auto"
          >
            <form aria-label="Filtres" onSubmit={appliquer} className="flex flex-col gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Entreprise" hint="Nom d'une entreprise déjà collectée.">
                  {(champ) => (
                    <Input
                      {...champ}
                      value={draft.company}
                      maxLength={200}
                      onChange={(e) => maj("company", e.target.value)}
                    />
                  )}
                </Field>
                <Field label="Pays" hint="Codes ISO séparés par des virgules, ex. FR, CA">
                  {(champ) => (
                    <Input
                      {...champ}
                      value={draft.country}
                      maxLength={100}
                      onChange={(e) => maj("country", e.target.value.toUpperCase())}
                    />
                  )}
                </Field>
                <Field label="Télétravail">
                  {({ id }) => (
                    <Select
                      id={id}
                      options={REMOTE_TYPES}
                      placeholder="Tous"
                      value={draft.remoteType}
                      onChange={(e) => maj("remoteType", e.target.value)}
                    />
                  )}
                </Field>
                <Field label="Publiée depuis le">
                  {(champ) => (
                    <Input
                      {...champ}
                      type="date"
                      value={draft.publishedSince}
                      onChange={(e) => maj("publishedSince", e.target.value)}
                    />
                  )}
                </Field>
                <Field label="Salaire minimum" hint="Les offres sans salaire connu sont exclues.">
                  {(champ) => (
                    <Input
                      {...champ}
                      type="number"
                      min={0}
                      inputMode="numeric"
                      value={draft.salaryMin}
                      onChange={(e) => maj("salaryMin", e.target.value)}
                    />
                  )}
                </Field>
                <Field
                  label="Devise"
                  error={
                    salaireIncomplet ? "La devise est obligatoire avec un salaire." : undefined
                  }
                >
                  {(champ) => (
                    <Input
                      {...champ}
                      value={draft.salaryCurrency}
                      maxLength={3}
                      onChange={(e) => maj("salaryCurrency", e.target.value.toUpperCase())}
                    />
                  )}
                </Field>
                <Field label="Langue de l'annonce" hint="Code ISO, ex. fr, en">
                  {(champ) => (
                    <Input
                      {...champ}
                      value={draft.language}
                      maxLength={2}
                      onChange={(e) => maj("language", e.target.value.toLowerCase())}
                    />
                  )}
                </Field>
                <Field
                  label="Expérience exigée (ans max.)"
                  hint="Les offres sans exigence connue restent affichées."
                >
                  {(champ) => (
                    <Input
                      {...champ}
                      type="number"
                      min={0}
                      max={40}
                      inputMode="numeric"
                      value={draft.maxExperience}
                      onChange={(e) => maj("maxExperience", e.target.value)}
                    />
                  )}
                </Field>
                <Field
                  label="Intitulés visés"
                  hint="Séparés par des virgules ; utilisés pour interroger les sources."
                >
                  {(champ) => (
                    <Input
                      {...champ}
                      value={draft.titles}
                      maxLength={500}
                      onChange={(e) => maj("titles", e.target.value)}
                    />
                  )}
                </Field>
                <Field label="Compatibilité minimale" hint="Nécessite un profil validé.">
                  {({ id }) => (
                    <Select
                      id={id}
                      options={SCORES_MINIMAUX}
                      placeholder="Toutes"
                      value={draft.minScore}
                      onChange={(e) => maj("minScore", e.target.value)}
                    />
                  )}
                </Field>
              </div>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={draft.multilingual}
                  onChange={(e) => maj("multilingual", e.target.checked)}
                />
                Inclure les équivalents français / anglais (ex. développeur ↔ developer)
              </label>
              <div className="flex flex-wrap justify-end gap-3">
                <Button variant="ghost" onClick={reinitialiser}>
                  Réinitialiser
                </Button>
                <Button type="submit" disabled={salaireIncomplet}>
                  Appliquer les filtres
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
        {onSaveSearch ? (
          <Button variant="ghost" onClick={() => onSaveSearch({ ...draft, page: 1 })}>
            Sauvegarder cette recherche
          </Button>
        ) : null}
        {actifs > 0 || draft.text || draft.city || draft.employmentType ? (
          <Button variant="ghost" onClick={reinitialiser}>
            Réinitialiser
          </Button>
        ) : null}
      </div>
    </div>
  );
}
