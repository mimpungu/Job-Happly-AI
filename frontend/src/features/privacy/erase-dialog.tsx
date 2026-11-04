"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toaster";

import { useErase } from "./use-privacy";

const MOT = "SUPPRIMER";

/** Suppression définitive : le bouton de confirmation n'est actif qu'une fois le mot saisi. */
export function EraseDialog({
  scope,
  label,
  triggerLabel,
}: {
  scope: string;
  label: string;
  triggerLabel: string;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState("");
  const effacer = useErase();

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    effacer.mutate(
      { scope, confirmation: saisie },
      {
        onSuccess: (r) => {
          toast.success(`${r.total_rows} ligne(s) supprimée(s).`);
          setOuvert(false);
          setSaisie("");
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <Dialog
      open={ouvert}
      onOpenChange={(o) => {
        setOuvert(o);
        if (!o) setSaisie("");
      }}
    >
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent
        title="Suppression définitive"
        description={`Vous allez supprimer : ${label}. Cette action est irréversible : pensez à exporter vos données avant.`}
      >
        <form onSubmit={soumettre} className="flex flex-col gap-4">
          <Field label={`Saisissez ${MOT} pour confirmer`}>
            {(c) => (
              <Input
                {...c}
                value={saisie}
                autoComplete="off"
                onChange={(e) => setSaisie(e.target.value)}
              />
            )}
          </Field>
          <div className="flex justify-end gap-3">
            <DialogClose asChild>
              <Button variant="ghost">Annuler</Button>
            </DialogClose>
            <Button
              type="submit"
              variant="danger"
              loading={effacer.isPending}
              disabled={saisie.trim() !== MOT}
            >
              Supprimer définitivement
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
