"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toaster";
import type { ApplicationDetail } from "@/types/applications";

import { useAddContact } from "./use-applications";

const VIDE = { name: "", email: "", phone: "", role: "" };

/** Coordonnées du recruteur, saisies seulement lorsqu'elles sont connues. */
export function ContactsPanel({ application }: { application: ApplicationDetail }) {
  const ajouter = useAddContact(application.id);
  const [champs, setChamps] = useState(VIDE);
  const maj = (cle: keyof typeof VIDE, valeur: string) =>
    setChamps((c) => ({ ...c, [cle]: valeur }));

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    ajouter.mutate(
      {
        name: champs.name.trim(),
        email: champs.email.trim() || undefined,
        phone: champs.phone.trim() || undefined,
        role: champs.role.trim() || undefined,
      },
      {
        onSuccess: () => setChamps(VIDE),
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <Panel title="Contacts">
      <div className="flex flex-col gap-4">
        {application.contacts.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucun contact enregistré.</p>
        ) : (
          <ul className="flex flex-col gap-2" aria-label="Contacts de la candidature">
            {application.contacts.map((c) => (
              <li key={c.id} className="text-sm">
                <p className="font-medium text-foreground">
                  {c.name}
                  {c.role ? (
                    <span className="font-normal text-foreground-muted"> — {c.role}</span>
                  ) : null}
                </p>
                {c.email ? <p className="text-foreground-muted">{c.email}</p> : null}
                {c.phone ? <p className="text-foreground-muted">{c.phone}</p> : null}
              </li>
            ))}
          </ul>
        )}
        <form
          onSubmit={soumettre}
          className="grid gap-3 md:grid-cols-2"
          aria-label="Ajouter un contact"
        >
          <Field label="Nom">
            {(c) => (
              <Input
                {...c}
                value={champs.name}
                maxLength={200}
                onChange={(e) => maj("name", e.target.value)}
              />
            )}
          </Field>
          <Field label="Fonction (facultatif)">
            {(c) => (
              <Input
                {...c}
                value={champs.role}
                maxLength={200}
                onChange={(e) => maj("role", e.target.value)}
              />
            )}
          </Field>
          <Field label="E-mail (facultatif)">
            {(c) => (
              <Input
                {...c}
                type="email"
                value={champs.email}
                maxLength={320}
                onChange={(e) => maj("email", e.target.value)}
              />
            )}
          </Field>
          <Field label="Téléphone (facultatif)">
            {(c) => (
              <Input
                {...c}
                type="tel"
                value={champs.phone}
                maxLength={40}
                onChange={(e) => maj("phone", e.target.value)}
              />
            )}
          </Field>
          <div className="md:col-span-2">
            <Button
              type="submit"
              variant="secondary"
              disabled={!champs.name.trim()}
              loading={ajouter.isPending}
            >
              Ajouter le contact
            </Button>
          </div>
        </form>
      </div>
    </Panel>
  );
}
