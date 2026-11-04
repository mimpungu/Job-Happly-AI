"use client";

import { ExternalLink } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { statusLabel } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { getApplicationUrl } from "@/services/applications";
import type { ApplicationDetail } from "@/types/applications";

import { isoToLocalInput, localInputToIso } from "./format";
import { useChangeStatus, useConfirmSubmission } from "./use-applications";

/** Ouverture de l'annonce, changement de statut et confirmation d'envoi. */
export function StatusActions({ application }: { application: ApplicationDetail }) {
  const [cible, setCible] = useState("");
  const [ouverture, setOuverture] = useState(false);
  const changer = useChangeStatus(application.id);

  const ouvrirAnnonce = async () => {
    setOuverture(true);
    try {
      // Le serveur ne renvoie qu'un lien http(s) nu ; l'utilisateur candidate lui-même sur le site.
      const { application_url: url } = await getApplicationUrl(application.id);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (erreur) {
      toast.error(erreur instanceof Error ? erreur.message : "Lien indisponible.");
    } finally {
      setOuverture(false);
    }
  };

  const options = application.allowed_transitions.map((s) => ({
    value: s,
    label: statusLabel(s),
  }));

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Button variant="secondary" loading={ouverture} onClick={() => void ouvrirAnnonce()}>
        <ExternalLink className="size-4" aria-hidden="true" />
        Ouvrir l&apos;annonce
      </Button>

      {application.can_confirm_submission ? (
        <ConfirmSubmissionDialog application={application} />
      ) : null}

      {options.length > 0 ? (
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!cible) return;
            changer.mutate(
              { target: cible as ApplicationDetail["status"] },
              {
                onSuccess: () => {
                  toast.success("Statut mis à jour.");
                  setCible("");
                },
                onError: (erreur) => toast.error(erreur.message),
              },
            );
          }}
        >
          <div className="w-56">
            <Field label="Changer le statut">
              {({ id }) => (
                <Select
                  id={id}
                  options={options}
                  placeholder="Choisir un statut"
                  value={cible}
                  onChange={(e) => setCible(e.target.value)}
                />
              )}
            </Field>
          </div>
          <Button type="submit" variant="secondary" disabled={!cible} loading={changer.isPending}>
            Appliquer
          </Button>
        </form>
      ) : null}
    </div>
  );
}

function ConfirmSubmissionDialog({ application }: { application: ApplicationDetail }) {
  const [ouvert, setOuvert] = useState(false);
  const [date, setDate] = useState(() => isoToLocalInput(new Date()));
  const [notes, setNotes] = useState("");
  const confirmer = useConfirmSubmission(application.id);

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    confirmer.mutate(
      { appliedAt: localInputToIso(date), notes: notes.trim() || undefined },
      {
        onSuccess: () => {
          toast.success("Envoi enregistré.");
          setOuvert(false);
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <>
      <Dialog open={ouvert} onOpenChange={setOuvert}>
        <DialogTrigger asChild>
          <Button>J&apos;ai envoyé ma candidature</Button>
        </DialogTrigger>
        <DialogContent
          title="Confirmer l'envoi"
          description="Happly AI n'envoie jamais rien à votre place. Confirmez uniquement si vous avez déjà envoyé cette candidature vous-même, sur le site de l'employeur."
        >
          <form onSubmit={soumettre} className="flex flex-col gap-4">
            <Field label="Date et heure d'envoi" hint="Dans le passé ou maintenant.">
              {(c) => (
                <Input
                  {...c}
                  type="datetime-local"
                  value={date}
                  max={isoToLocalInput(new Date())}
                  required
                  onChange={(e) => setDate(e.target.value)}
                />
              )}
            </Field>
            <Field label="Note (facultatif)">
              {(c) => (
                <Textarea
                  {...c}
                  value={notes}
                  maxLength={1000}
                  onChange={(e) => setNotes(e.target.value)}
                />
              )}
            </Field>
            <div className="flex justify-end gap-3">
              <DialogClose asChild>
                <Button variant="ghost">Annuler</Button>
              </DialogClose>
              <Button type="submit" loading={confirmer.isPending}>
                Confirmer que je l&apos;ai envoyée
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
