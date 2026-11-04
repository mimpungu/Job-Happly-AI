"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { toast } from "@/components/ui/toaster";

import { useDeleteApplication } from "./use-applications";

/**
 * Retire la candidature du suivi (ajoutée par erreur, par exemple). L'action est définitive pour
 * l'historique, les contacts et les documents associés ; l'offre, elle, reste dans la recherche.
 */
export function DeleteApplicationButton({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  const supprimer = useDeleteApplication();
  const [ouvert, setOuvert] = useState(false);

  return (
    <>
      <Button variant="ghost" onClick={() => setOuvert(true)}>
        <Trash2 className="size-4" aria-hidden="true" />
        Retirer du suivi
      </Button>
      <ConfirmDialog
        open={ouvert}
        onOpenChange={setOuvert}
        destructive
        title="Retirer cette candidature du suivi ?"
        description="Son historique, ses contacts et ses documents associés seront supprimés définitivement. L'offre reste disponible dans la recherche et pourra être suivie à nouveau."
        confirmLabel="Retirer du suivi"
        loading={supprimer.isPending}
        onConfirm={() =>
          supprimer.mutate(applicationId, {
            onSuccess: () => {
              setOuvert(false);
              toast.success("Candidature retirée du suivi.");
              router.push("/applications");
            },
            onError: (erreur) => {
              setOuvert(false);
              toast.error(erreur.message);
            },
          })
        }
      />
    </>
  );
}
