"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { addManualOffer } from "@/services/jobs";
import type { ManualOfferResult } from "@/types/jobs";

import { offersKey } from "./use-offers";

const MIN_DESCRIPTION = 20;

/** Validation côté client, répétée côté serveur : l'adresse doit être en https. */
export function adresseValide(valeur: string): boolean {
  try {
    const url = new URL(valeur.trim());
    return url.protocol === "https:" && url.username === "" && url.password === "";
  } catch {
    return false;
  }
}

const VIDE = { title: "", company_name: "", location: "", application_url: "", description: "" };

export function ManualOfferDialog() {
  const client = useQueryClient();
  const [ouvert, setOuvert] = useState(false);
  const [champs, setChamps] = useState(VIDE);
  const [resultat, setResultat] = useState<ManualOfferResult | null>(null);
  const maj = (cle: keyof typeof VIDE, valeur: string) =>
    setChamps((c) => ({ ...c, [cle]: valeur }));

  const ajouter = useMutation({
    mutationFn: () =>
      addManualOffer({
        title: champs.title.trim(),
        company_name: champs.company_name.trim() || null,
        location: champs.location.trim() || null,
        application_url: champs.application_url.trim(),
        description: champs.description.trim(),
      }),
    onSuccess: (r) => {
      void client.invalidateQueries({ queryKey: offersKey });
      setResultat(r);
      if (!r.already_known) setChamps(VIDE);
    },
  });

  const urlOk = champs.application_url === "" || adresseValide(champs.application_url);
  const complet =
    champs.title.trim().length >= 2 &&
    adresseValide(champs.application_url) &&
    champs.description.trim().length >= MIN_DESCRIPTION;

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    if (complet) ajouter.mutate();
  };
  const fermer = () => {
    setOuvert(false);
    setResultat(null);
    ajouter.reset();
  };

  return (
    <>
      <Button variant="secondary" onClick={() => setOuvert(true)}>
        Ajouter une offre
      </Button>
      <Dialog open={ouvert} onOpenChange={(o) => (o ? setOuvert(true) : fermer())}>
        <DialogContent
          title="Ajouter une offre"
          description="Ouvrez l'offre dans votre navigateur, puis copiez-en l'adresse et le texte ici. Aucune requête n'est envoyée au site d'origine."
        >
          {resultat ? (
            <div className="flex flex-col gap-4">
              <p role="status" className="text-sm text-foreground">
                {resultat.already_known
                  ? "Cette offre était déjà enregistrée : aucun doublon n'a été créé."
                  : "Offre ajoutée. Elle apparaît dans la recherche et reçoit un score si votre profil est validé."}
              </p>
              <div className="flex justify-end gap-3">
                <Link
                  href={`/jobs/${resultat.offer_id}`}
                  className={buttonVariants({ variant: "secondary" })}
                  onClick={fermer}
                >
                  Voir l&apos;offre
                </Link>
                <Button onClick={fermer}>Fermer</Button>
              </div>
            </div>
          ) : (
            <form onSubmit={soumettre} className="flex flex-col gap-4">
              <Field label="Intitulé du poste">
                {(c) => (
                  <Input
                    {...c}
                    value={champs.title}
                    maxLength={300}
                    autoFocus
                    onChange={(e) => maj("title", e.target.value)}
                  />
                )}
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Entreprise (facultatif)">
                  {(c) => (
                    <Input
                      {...c}
                      value={champs.company_name}
                      maxLength={300}
                      onChange={(e) => maj("company_name", e.target.value)}
                    />
                  )}
                </Field>
                <Field label="Lieu (facultatif)" hint="Ex. Paris, France">
                  {(c) => (
                    <Input
                      {...c}
                      value={champs.location}
                      maxLength={300}
                      onChange={(e) => maj("location", e.target.value)}
                    />
                  )}
                </Field>
              </div>
              <Field
                label="Adresse de l'offre"
                hint="Commence par https://"
                error={urlOk ? undefined : "Saisissez une adresse en https://."}
              >
                {(c) => (
                  <Input
                    {...c}
                    type="url"
                    value={champs.application_url}
                    maxLength={2000}
                    onChange={(e) => maj("application_url", e.target.value)}
                  />
                )}
              </Field>
              <Field
                label="Texte de l'offre"
                hint={`Collez la description complète (au moins ${MIN_DESCRIPTION} caractères).`}
                error={ajouter.isError ? ajouter.error.message : undefined}
              >
                {(c) => (
                  <Textarea
                    {...c}
                    rows={8}
                    value={champs.description}
                    maxLength={50000}
                    onChange={(e) => maj("description", e.target.value)}
                  />
                )}
              </Field>
              <div className="flex justify-end gap-3">
                <DialogClose asChild>
                  <Button variant="secondary">Annuler</Button>
                </DialogClose>
                <Button type="submit" loading={ajouter.isPending} disabled={!complet}>
                  Ajouter
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
