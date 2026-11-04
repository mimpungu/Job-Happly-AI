"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toaster";
import { createSavedSearch } from "@/services/jobs";
import type { OfferFilters } from "@/types/jobs";

export interface SaveSearchDialogProps {
  /** Critères à sauvegarder ; `null` = fenêtre fermée. */
  filters: OfferFilters | null;
  onClose: () => void;
}

export function SaveSearchDialog({ filters, onClose }: SaveSearchDialogProps) {
  const client = useQueryClient();
  const [nom, setNom] = useState("");
  const creer = useMutation({
    mutationFn: (criteres: OfferFilters) => createSavedSearch(nom.trim(), criteres),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["saved-searches"] });
      toast.success("Recherche sauvegardée.");
      setNom("");
      onClose();
    },
  });

  const soumettre = (evenement: FormEvent) => {
    evenement.preventDefault();
    if (filters && nom.trim()) creer.mutate(filters);
  };

  return (
    <Dialog open={filters !== null} onOpenChange={(ouvert) => !ouvert && onClose()}>
      <DialogContent
        title="Sauvegarder cette recherche"
        description="Les critères actuels seront mémorisés pour être relancés plus tard."
      >
        <form onSubmit={soumettre} className="flex flex-col gap-4">
          <Field
            label="Nom de la recherche"
            error={creer.isError ? creer.error.message : undefined}
          >
            {(champ) => (
              <Input
                {...champ}
                value={nom}
                maxLength={200}
                autoFocus
                onChange={(e) => setNom(e.target.value)}
              />
            )}
          </Field>
          <div className="flex justify-end gap-3">
            <DialogClose asChild>
              <Button variant="secondary">Annuler</Button>
            </DialogClose>
            <Button type="submit" loading={creer.isPending} disabled={!nom.trim()}>
              Sauvegarder
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
