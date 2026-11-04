"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toaster";
import { ApiError } from "@/services/api-client";

import { useCreateApplication } from "./use-applications";

/** Crée la candidature de l'offre (une offre = une candidature) puis ouvre sa fiche. */
export function TrackApplicationButton({ offerId }: { offerId: string }) {
  const router = useRouter();
  const creer = useCreateApplication();

  return (
    <Button
      variant="secondary"
      loading={creer.isPending}
      onClick={() =>
        creer.mutate(offerId, {
          onSuccess: (candidature) => {
            toast.success("Candidature créée.");
            router.push(`/applications/${candidature.id}`);
          },
          onError: (erreur) =>
            toast.error(
              erreur instanceof ApiError && erreur.code === "duplicate_application"
                ? "Cette offre est déjà suivie : retrouvez-la dans Candidatures."
                : erreur.message,
            ),
        })
      }
    >
      Suivre cette candidature
    </Button>
  );
}
