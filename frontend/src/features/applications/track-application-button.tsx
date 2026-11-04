"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { toast } from "@/components/ui/toaster";
import { ApiError } from "@/services/api-client";

import { useCreateApplication } from "./use-applications";

/**
 * Crée la candidature de l'offre (une offre = une candidature) puis ouvre sa fiche.
 * Une confirmation précède toujours l'ajout : un clic par erreur ne crée rien.
 */
export function TrackApplicationButton({ offerId }: { offerId: string }) {
  const router = useRouter();
  const creer = useCreateApplication();
  const [ouvert, setOuvert] = useState(false);

  const confirmer = () =>
    creer.mutate(offerId, {
      onSuccess: (candidature) => {
        setOuvert(false);
        toast.success("Candidature créée.");
        router.push(`/applications/${candidature.id}`);
      },
      onError: (erreur) => {
        setOuvert(false);
        toast.error(
          erreur instanceof ApiError && erreur.code === "duplicate_application"
            ? "Cette offre est déjà suivie : retrouvez-la dans Candidatures."
            : erreur.message,
        );
      },
    });

  return (
    <>
      <Button variant="secondary" onClick={() => setOuvert(true)}>
        Suivre cette candidature
      </Button>
      <ConfirmDialog
        open={ouvert}
        onOpenChange={setOuvert}
        title="Suivre cette offre ?"
        description="L'offre sera ajoutée à vos candidatures au statut « À postuler ». Rien n'est envoyé à l'employeur, et vous pourrez la retirer du suivi depuis sa fiche."
        confirmLabel="Ajouter au suivi"
        loading={creer.isPending}
        onConfirm={confirmer}
      />
    </>
  );
}
